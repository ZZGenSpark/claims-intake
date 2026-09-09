"""HTTP surface for the claims intake service.

This layer does three things and no more: it parses the request, it calls the
service, and it maps the outcome to a status code. It holds no rule logic. A rule
that appears here is a rule the service layer cannot be tested for.

Day 4 lab. Implement against `docs/api-contract.md` sections 5 and 6.
"""

from __future__ import annotations

from collections.abc import Mapping
from json import JSONDecodeError
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from claims.models import NotificationRequest
from claims.policy_client import (
    LookupFailureReason,
    PolicyClient,
    PolicyLookupFailed,
    StubPolicyClient,
)
from claims.repository import NotificationRepository
from claims.service import ValidationOutcome, submit_notification

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

# Pydantic error types mapped to the `issue` values callers may rely on (section 5).
_PARSE_ISSUE_BY_TYPE: Mapping[str, str] = {
    "missing": "required_field_missing",
    "extra_forbidden": "unexpected_field",
    "string_too_short": "empty_value",
    "literal_error": "value_not_in_vocabulary",
    "decimal_max_places": "invalid_scale",
    "greater_than": "not_greater_than_zero",
    "model_type": "wrong_type",
}

_LOOKUP_BY_REASON: Mapping[LookupFailureReason, tuple[int, str, str]] = {
    "unparsable": (
        502,
        "POLICY_MASTER_UNPARSABLE",
        "The policy master answered with a body that could not be parsed.",
    ),
    "unreachable": (
        503,
        "POLICY_MASTER_UNREACHABLE",
        "The policy master could not be reached.",
    ),
    "timeout": (
        504,
        "POLICY_MASTER_TIMEOUT",
        "The policy master did not answer in time.",
    ),
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
        try:
            body: Any = await request.json()
        except JSONDecodeError:
            return _uninterpretable_response(field="body", issue="invalid_json")
        try:
            notification = NotificationRequest.model_validate(body)
        except ValidationError as exc:
            return _uninterpretable_from_validation(exc)
        try:
            outcome = submit_notification(notification, client, store)
        except PolicyLookupFailed as exc:
            return _lookup_failure_response(exc)
        if outcome.passed:
            return _recorded_response(outcome)
        return _rule_failure_response(outcome)

    return app


def _envelope(status: int, code: str, message: str, detail: dict[str, Any]) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"code": code, "message": message, "detail": jsonable_encoder(detail)},
    )


def _uninterpretable_response(*, field: str, issue: str) -> JSONResponse:
    return _envelope(
        400,
        "UNINTERPRETABLE_REQUEST",
        "The request body could not be interpreted.",
        {"field": field, "issue": issue},
    )


def _uninterpretable_from_validation(exc: ValidationError) -> JSONResponse:
    first = exc.errors()[0]
    loc = first.get("loc", ())
    field = str(loc[-1]) if loc else "body"
    return _uninterpretable_response(field=field, issue=_parse_issue(first, field))


def _parse_issue(error: Mapping[str, Any], field: str) -> str:
    error_type = str(error.get("type", ""))
    mapped = _PARSE_ISSUE_BY_TYPE.get(error_type)
    if mapped is not None:
        return mapped
    if error_type == "value_error" and field == "loss_date":
        return "invalid_date"
    if error_type == "value_error" and field == "estimated_amount":
        return "invalid_scale"
    return "invalid_value"


def _lookup_failure_response(exc: PolicyLookupFailed) -> JSONResponse:
    status, code, message = _LOOKUP_BY_REASON[exc.reason]
    return _envelope(status, code, message, {"policy_number": exc.policy_number})


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
    return _envelope(RULE_STATUS[code], code, RULE_MESSAGE[code], detail)


app = create_app()
