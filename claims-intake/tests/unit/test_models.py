"""Unit tests for the request, policy, and supporting value models."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from claims.models import ErrorCode, NotificationRequest, Policy, RuleFailure, RuleId
from claims.policy_client import PolicyRecord, StubPolicyClient

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
MODEL_REJECTS = frozenset({"EDGE-08", "EDGE-12"})

VALID: dict[str, object] = {
    "policy_number": "MOT-4471",
    "loss_date": "2026-04-02",
    "claim_type": "collision",
    "estimated_amount": "4200.00",
}


def _payload(**changes: object) -> dict[str, object]:
    body = dict(VALID)
    body.update(changes)
    return body


def _without(*keys: str) -> dict[str, object]:
    body = dict(VALID)
    for key in keys:
        del body[key]
    return body


def _policy_body(**changes: object) -> dict[str, object]:
    body: dict[str, object] = {
        "policy_number": "MOT-4471",
        "product": "personal_auto_standard",
        "effective_date": date(2026, 3, 1),
        "expiry_date": date(2027, 2, 28),
        "cancellation_date": None,
        "limit": Decimal("50000.00"),
        "permitted_claim_types": ("collision", "theft"),
    }
    body.update(changes)
    return body


def _policy_from_record(record: PolicyRecord) -> Policy:
    return Policy(
        policy_number=record.policy_number,
        product=record.product,
        effective_date=record.effective_date,
        expiry_date=record.expiry_date,
        cancellation_date=record.cancellation_date,
        limit=record.limit,
        permitted_claim_types=record.permitted_claim_types,
    )


def _realistic_cases() -> list[tuple[str, dict[str, Any], bool]]:
    cases: list[tuple[str, dict[str, Any], bool]] = []
    for name in ("fnol_invalid.json", "fnol_edge.json"):
        for item in json.loads((DATA_DIR / name).read_text()):
            payload_id = item["id"]
            cases.append((payload_id, item["payload"], payload_id not in MODEL_REJECTS))
    return cases


REALISTIC_CASES = _realistic_cases()


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(_payload(description="Rear ended at a junction."), id="all_fields"),
        pytest.param(_without(), id="description_absent"),
        pytest.param(_payload(description=None), id="description_null"),
        pytest.param(_payload(claim_type="flood"), id="claim_type_outside_vocabulary"),
    ],
)
def test_notification_request_accepts_well_formed_payload(payload: dict[str, object]) -> None:
    notification = NotificationRequest.model_validate(payload)
    assert notification.loss_date == date(2026, 4, 2)
    assert notification.estimated_amount == Decimal("4200.00")
    assert isinstance(notification.loss_date, date)
    assert isinstance(notification.estimated_amount, Decimal)


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(_payload(handler_notes="x"), id="unknown_field"),
        pytest.param(_payload(polcy_number="MOT-4471"), id="misspelled_field"),
        pytest.param(_without("policy_number"), id="missing_policy_number"),
        pytest.param(_without("loss_date"), id="missing_loss_date"),
        pytest.param(_without("claim_type"), id="missing_claim_type"),
        pytest.param(_without("estimated_amount"), id="missing_estimated_amount"),
        pytest.param(_payload(policy_number=""), id="empty_policy_number"),
        pytest.param(_payload(claim_type=""), id="empty_claim_type"),
        pytest.param(_payload(policy_number=4471), id="policy_number_not_string"),
        pytest.param(_payload(loss_date=True), id="loss_date_not_date"),
        pytest.param(_payload(claim_type=["collision"]), id="claim_type_not_string"),
        pytest.param(_payload(estimated_amount=True), id="estimated_amount_not_decimal"),
        pytest.param(_payload(description={"text": "x"}), id="description_not_string"),
        pytest.param(_payload(loss_date="2026/03/15"), id="date_wrong_separator"),
        pytest.param(_payload(loss_date="15-03-2026"), id="date_not_iso"),
        pytest.param(_payload(loss_date="2026-03-15T00:00:00"), id="datetime_not_date"),
        pytest.param(_payload(loss_date="2026-02-30"), id="impossible_day"),
        pytest.param(_payload(loss_date=""), id="empty_date"),
        pytest.param(_payload(estimated_amount="3499.999"), id="three_fractional_digits"),
        pytest.param(_payload(estimated_amount="4200.0"), id="one_fractional_digit"),
        pytest.param(_payload(estimated_amount="4200"), id="zero_fractional_digits"),
        pytest.param(_payload(estimated_amount="0.00"), id="zero_amount"),
        pytest.param(_payload(estimated_amount="-1.00"), id="negative_amount"),
    ],
)
def test_notification_request_rejects_invalid_payload(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        NotificationRequest.model_validate(payload)


@pytest.mark.parametrize(
    ("_payload_id", "payload", "should_accept"),
    REALISTIC_CASES,
    ids=[case[0] for case in REALISTIC_CASES],
)
def test_realistic_payloads_model_boundary(
    _payload_id: str,
    payload: dict[str, Any],
    should_accept: bool,
) -> None:
    if should_accept:
        NotificationRequest.model_validate(payload)
    else:
        with pytest.raises(ValidationError):
            NotificationRequest.model_validate(payload)


@pytest.mark.parametrize(
    ("policy_number", "expect_cancelled"),
    [
        pytest.param("MOT-4471", False, id="uncancelled"),
        pytest.param("MOT-4496", True, id="cancelled"),
    ],
)
def test_policy_types_from_master(
    policy_client: StubPolicyClient,
    policy_number: str,
    expect_cancelled: bool,
) -> None:
    policy = _policy_from_record(policy_client.get_policy(policy_number))
    assert isinstance(policy.effective_date, date)
    assert isinstance(policy.expiry_date, date)
    assert isinstance(policy.limit, Decimal)
    if expect_cancelled:
        assert isinstance(policy.cancellation_date, date)
    else:
        assert policy.cancellation_date is None


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(_policy_body(effective_date=True), id="effective_date_wrong_type"),
        pytest.param(_policy_body(expiry_date=True), id="expiry_date_wrong_type"),
        pytest.param(_policy_body(cancellation_date="not-a-date"), id="cancellation_date_wrong_type"),
        pytest.param(_policy_body(limit=True), id="limit_wrong_type"),
        pytest.param(_policy_body(limit=Decimal("50000")), id="limit_wrong_scale"),
    ],
)
def test_policy_rejects_invalid_field(body: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Policy.model_validate(body)


@pytest.mark.parametrize(
    "field",
    [
        "policy_number",
        "product",
        "effective_date",
        "expiry_date",
        "cancellation_date",
        "limit",
        "permitted_claim_types",
    ],
)
def test_policy_rejects_missing_field(field: str) -> None:
    body = _policy_body()
    del body[field]
    with pytest.raises(ValidationError):
        Policy.model_validate(body)


@pytest.mark.parametrize(
    ("rule", "code"),
    [
        pytest.param("V-2", "LOSS_BEFORE_INCEPTION", id="inception"),
        pytest.param("V-6", "DUPLICATE_NOTIFICATION", id="duplicate"),
    ],
)
def test_rule_failure_carries_rule_and_code_separately(rule: str, code: str) -> None:
    failure = RuleFailure(rule=RuleId(rule), code=ErrorCode(code))
    assert failure.rule == rule
    assert failure.code == code
    with pytest.raises(FrozenInstanceError):
        setattr(failure, "rule", "V-1")
