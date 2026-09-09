"""HTTP surface for the claims intake service.

This layer does three things and no more: it parses the request, it calls the
service, and it maps the outcome to a status code. It holds no rule logic. A rule
that appears here is a rule the service layer cannot be tested for.

Day 4 lab. Implement against `docs/api-contract.md` sections 5 and 6.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from claims.models import NotificationRequest
from claims.policy_client import PolicyClient, StubPolicyClient
from claims.repository import NotificationRepository
from claims.service import ValidationOutcome, submit_notification

# Contract section 6 for interpreted refusals (V-1 through V-7). Parse failures
# and PolicyLookupFailed are mapped in later commits; they are not in this table.
RULE_STATUS: Mapping[str, int] = {
    "DUPLICATE_NOTIFICATION": 409,
    "POLICY_NOT_FOUND": 422,
    "LOSS_BEFORE_INCEPTION": 422,
    "LOSS_AFTER_EXPIRY": 422,
    "AMOUNT_EXCEEDS_LIMIT": 422,
    "TYPE_NOT_COVERED": 422,
    "POLICY_CANCELLED": 422,
}

RULE_MESSAGE: Mapping[str, str] = {
    "POLICY_NOT_FOUND": "No policy exists with that number.",
    "LOSS_BEFORE_INCEPTION": "Loss date before policy inception.",
    "LOSS_AFTER_EXPIRY": "Loss date after policy expiry.",
    "AMOUNT_EXCEEDS_LIMIT": "Estimated amount exceeds the policy limit.",
    "TYPE_NOT_COVERED": "Claim type is not covered on this policy.",
    "DUPLICATE_NOTIFICATION": "A notification for this loss is already recorded.",
    "POLICY_CANCELLED": "Loss date is on or after policy cancellation.",
}


def create_app(
    *,
    policy_client: PolicyClient | None = None,
    repository: NotificationRepository | None = None,
) -> FastAPI:
    """Build the app with injectable dependencies so tests do not share state."""
    app = FastAPI(title="Claims Intake Service")
    client = policy_client if policy_client is not None else StubPolicyClient()
    store = repository if repository is not None else NotificationRepository()

    @app.post("/notifications")
    async def post_notification(request: Request) -> JSONResponse:
        # Manual parse: a FastAPI body parameter would return 422 on shape errors,
        # which section 6 already assigns to POLICY_NOT_FOUND.
        body: Any = await request.json()
        notification = NotificationRequest.model_validate(body)
        outcome = submit_notification(notification, client, store)
        if outcome.passed:
            return _recorded_response(outcome)
        return _rule_failure_response(outcome)

    return app


def _recorded_response(outcome: ValidationOutcome) -> JSONResponse:
    if outcome.claim_reference is None:
        raise RuntimeError("submit passed but issued no claim reference")
    return JSONResponse(
        status_code=201,
        content={
            "claim_reference": outcome.claim_reference,
            "status": "recorded",
        },
    )


def _rule_failure_response(outcome: ValidationOutcome) -> JSONResponse:
    code = outcome.code
    if code is None or code not in RULE_STATUS:
        raise RuntimeError(f"unmapped refusal code: {code!r}")
    detail: dict[str, Any] = dict(outcome.detail)
    if outcome.rule is not None:
        detail = {"rule": outcome.rule, **detail}
    return JSONResponse(
        status_code=RULE_STATUS[code],
        content={
            "code": code,
            "message": RULE_MESSAGE[code],
            "detail": jsonable_encoder(detail),
        },
    )


app = create_app()
