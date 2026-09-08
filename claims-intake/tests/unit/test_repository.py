"""Unit tests for recording notifications and detecting duplicates."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from claims.models import ClaimType, NotificationRequest
from claims.repository import NotificationRepository

CLAIM_REFERENCE = re.compile(r"^CLM-\d{4}-\d{6}$")
MakeNotification = Callable[..., NotificationRequest]


def _make_notification(
    policy_number: str = "MOT-4471",
    loss_date: date = date(2026, 4, 2),
    claim_type: ClaimType = "collision",
    estimated_amount: Decimal = Decimal("4200.00"),
    description: str | None = None,
) -> NotificationRequest:
    return NotificationRequest(
        policy_number=policy_number,
        loss_date=loss_date,
        claim_type=claim_type,
        estimated_amount=estimated_amount,
        description=description,
    )


@pytest.fixture
def repository() -> NotificationRepository:
    return NotificationRepository()


@pytest.fixture
def make_notification() -> MakeNotification:
    return _make_notification


def test_issue_claim_reference_matches_section_3_and_is_never_reissued(
    repository: NotificationRepository,
) -> None:
    year = str(datetime.now(UTC).date().year)
    first = repository.issue_claim_reference()
    second = repository.issue_claim_reference()
    assert CLAIM_REFERENCE.fullmatch(first)
    assert CLAIM_REFERENCE.fullmatch(second)
    assert first.startswith(f"CLM-{year}-")
    assert second.startswith(f"CLM-{year}-")
    assert first != second


def test_record_issues_unique_contract_references(
    repository: NotificationRepository,
    make_notification: MakeNotification,
) -> None:
    first = repository.record(make_notification())
    second = repository.record(make_notification(policy_number="MOT-4472"))
    year = str(datetime.now(UTC).date().year)
    for recorded in (first, second):
        assert CLAIM_REFERENCE.fullmatch(recorded.claim_reference)
        assert recorded.claim_reference.startswith(f"CLM-{year}-")
    assert first.claim_reference != second.claim_reference


@pytest.mark.parametrize(
    ("policy_number", "loss_date", "claim_type", "is_duplicate"),
    [
        pytest.param("MOT-4471", date(2026, 4, 2), "collision", True, id="all_three_match"),
        pytest.param("MOT-4471", date(2026, 4, 2), "theft", False, id="type_differs"),
        pytest.param("MOT-4471", date(2026, 4, 3), "collision", False, id="date_differs"),
        pytest.param("MOT-4472", date(2026, 4, 2), "collision", False, id="policy_differs"),
    ],
)
def test_find_matching_requires_all_three_fields(
    repository: NotificationRepository,
    make_notification: MakeNotification,
    policy_number: str,
    loss_date: date,
    claim_type: str,
    is_duplicate: bool,
) -> None:
    recorded = repository.record(make_notification())
    match = repository.find_matching(policy_number, loss_date, claim_type)
    if is_duplicate:
        assert match is not None
        assert match.claim_reference == recorded.claim_reference
    else:
        assert match is None


def test_rejected_notification_is_not_a_duplicate(
    repository: NotificationRepository,
    make_notification: MakeNotification,
) -> None:
    rejected = make_notification()
    assert (
        repository.find_matching(
            rejected.policy_number,
            rejected.loss_date,
            rejected.claim_type,
        )
        is None
    )
    recorded = repository.record(make_notification())
    stored = recorded.notification
    match = repository.find_matching(
        stored.policy_number,
        stored.loss_date,
        stored.claim_type,
    )
    assert match is not None
    assert match.claim_reference == recorded.claim_reference
