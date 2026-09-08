"""Persistence for recorded notifications.

An in-memory store is sufficient for Week 1 and is deliberate rather than a
shortcut. The rules do not know where a notification is stored, so replacing this
with a database in a later week is a change to one module.

The duplicate check that `WI-0151` describes is a query against what has been
recorded, which is why it belongs here rather than in the rule table.

Day 2 assignment. Implement against `docs/api-contract.md` section 3.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from claims.models import NotificationRequest, RecordedNotification


class NotificationRepository:
    """Stores recorded notifications and issues claim references."""

    def __init__(self) -> None:
        self._recorded: list[RecordedNotification] = []
        self._next_sequence: int = 1

    def issue_claim_reference(self) -> str:
        """Return the next unused `CLM-YYYY-NNNNNN` (contract section 3).

        Year is the calendar year of issuance. The sequence is never reused, which
        is why this advances even if the caller never records the value.
        """
        year = datetime.now(UTC).date().year
        reference = f"CLM-{year}-{self._next_sequence:06d}"
        self._next_sequence += 1
        return reference

    def record(self, notification: NotificationRequest) -> RecordedNotification:
        """Write a notification and return it with its issued claim reference.

        Duplicate detection is `find_matching`, not this method: V-6 decides
        whether to write. This method only writes.
        """
        recorded = RecordedNotification(
            claim_reference=self.issue_claim_reference(),
            notification=notification,
        )
        self._recorded.append(recorded)
        return recorded

    def find_matching(
        self,
        policy_number: str,
        loss_date: date,
        claim_type: str,
    ) -> RecordedNotification | None:
        """Return an existing recorded notification matching all three values.

        `WI-0151` AC-1 fixes which fields constitute a match. AC-3 is the reason
        this searches recorded notifications only: a submission that was refused
        was never written, so there is nothing for a later one to duplicate.
        """
        for recorded in self._recorded:
            stored = recorded.notification
            if (
                stored.policy_number == policy_number
                and stored.loss_date == loss_date
                and stored.claim_type == claim_type
            ):
                return recorded
        return None
