"""Unit tests for section 4 rules, written from the contract and work items."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from claims.models import ClaimType, ErrorCode, NotificationRequest, Policy, RuleFailure, RuleId
from claims.service import evaluate_notification


def _policy(**changes: object) -> Policy:
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
    return Policy.model_validate(body)


def _notification(**changes: object) -> NotificationRequest:
    body: dict[str, object] = {
        "policy_number": "MOT-4471",
        "loss_date": date(2026, 4, 2),
        "claim_type": "collision",
        "estimated_amount": Decimal("4200.00"),
    }
    body.update(changes)
    return NotificationRequest.model_validate(body)


def _assert_rule_failure(result: RuleFailure | None, rule: str, code: str) -> None:
    assert result is not None
    assert result.rule == RuleId(rule)
    assert result.code == ErrorCode(code)


@pytest.mark.parametrize(
    ("loss_date", "expect_failure"),
    [
        pytest.param(date(2026, 2, 28), True, id="before_inception"),
        pytest.param(date(2026, 3, 1), False, id="on_inception"),
        pytest.param(date(2026, 3, 2), False, id="after_inception"),
    ],
)
def test_v2_loss_on_or_after_inception(loss_date: date, expect_failure: bool) -> None:
    result = evaluate_notification(_notification(loss_date=loss_date), _policy())
    if expect_failure:
        _assert_rule_failure(result, "V-2", "LOSS_BEFORE_INCEPTION")
    else:
        assert result is None


@pytest.mark.parametrize(
    ("loss_date", "expect_failure"),
    [
        pytest.param(date(2027, 2, 27), False, id="before_expiry"),
        pytest.param(date(2027, 2, 28), False, id="on_expiry"),
        pytest.param(date(2027, 3, 1), True, id="after_expiry"),
    ],
)
def test_v3_loss_on_or_before_expiry(loss_date: date, expect_failure: bool) -> None:
    result = evaluate_notification(_notification(loss_date=loss_date), _policy())
    if expect_failure:
        _assert_rule_failure(result, "V-3", "LOSS_AFTER_EXPIRY")
    else:
        assert result is None


@pytest.mark.parametrize(
    ("amount", "expect_failure"),
    [
        pytest.param(Decimal("49999.99"), False, id="under_limit"),
        pytest.param(Decimal("50000.00"), False, id="on_limit"),
        pytest.param(Decimal("50000.01"), True, id="over_limit"),
    ],
)
def test_v4_amount_within_limit(amount: Decimal, expect_failure: bool) -> None:
    result = evaluate_notification(
        _notification(estimated_amount=amount),
        _policy(),
    )
    if expect_failure:
        _assert_rule_failure(result, "V-4", "AMOUNT_EXCEEDS_LIMIT")
    else:
        assert result is None


@pytest.mark.parametrize(
    ("claim_type", "expect_failure"),
    [
        pytest.param("collision", False, id="type_in_subset"),
        pytest.param("glass", True, id="type_not_in_subset"),
    ],
)
def test_v5_claim_type_permitted(claim_type: ClaimType, expect_failure: bool) -> None:
    result = evaluate_notification(_notification(claim_type=claim_type), _policy())
    if expect_failure:
        _assert_rule_failure(result, "V-5", "TYPE_NOT_COVERED")
    else:
        assert result is None


@pytest.mark.parametrize(
    ("policy", "loss_date", "expect_failure"),
    [
        pytest.param(
            _policy(cancellation_date=date(2026, 6, 1)),
            date(2026, 5, 31),
            False,
            id="before_cancellation",
        ),
        pytest.param(
            _policy(cancellation_date=date(2026, 6, 1)),
            date(2026, 6, 1),
            True,
            id="on_cancellation",
        ),
        pytest.param(
            _policy(cancellation_date=date(2026, 6, 1)),
            date(2026, 6, 2),
            True,
            id="after_cancellation",
        ),
        pytest.param(
            _policy(cancellation_date=None),
            date(2026, 4, 2),
            False,
            id="cancellation_absent",
        ),
        pytest.param(
            _policy(
                cancellation_date=date(2026, 6, 1),
                expiry_date=date(2026, 5, 31),
            ),
            date(2026, 7, 1),
            True,
            id="cancelled_and_after_expiry",
        ),
    ],
)
def test_v7_loss_before_cancellation(
    policy: Policy,
    loss_date: date,
    expect_failure: bool,
) -> None:
    result = evaluate_notification(_notification(loss_date=loss_date), policy)
    if expect_failure:
        _assert_rule_failure(result, "V-7", "POLICY_CANCELLED")
    else:
        assert result is None


def test_evaluate_notification_stops_at_first_rule() -> None:
    result = evaluate_notification(
        _notification(
            loss_date=date(2026, 2, 28),
            estimated_amount=Decimal("50000.01"),
        ),
        _policy(),
    )
    _assert_rule_failure(result, "V-2", "LOSS_BEFORE_INCEPTION")
