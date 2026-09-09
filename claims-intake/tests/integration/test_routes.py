"""HTTP integration tests for accepted and refused notifications.

These tests exercise POST /notifications. They do not call submit_notification.
Fixtures live here so this module does not share store state with other tests.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from claims.api.routes import create_app
from claims.models import CLAIM_REFERENCE_PATTERN
from claims.policy_client import StubPolicyClient
from claims.repository import NotificationRepository

DATA = Path(__file__).resolve().parents[2] / "data"
CLAIM_REFERENCE = re.compile(CLAIM_REFERENCE_PATTERN)

_VALID: dict[str, dict[str, Any]] = {
    case["id"]: case["payload"]
    for case in json.loads((DATA / "fnol_valid.json").read_text())
}
_INVALID: dict[str, dict[str, Any]] = {
    case["id"]: case["payload"]
    for case in json.loads((DATA / "fnol_invalid.json").read_text())
}


@pytest.fixture
def client() -> TestClient:
    return TestClient(
        create_app(
            policy_client=StubPolicyClient(),
            repository=NotificationRepository(),
        )
    )


def test_accepted_notification_returns_201_with_claim_reference(client: TestClient) -> None:
    response = client.post("/notifications", json=_VALID["VALID-01"])
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "recorded"
    assert CLAIM_REFERENCE.fullmatch(body["claim_reference"])


@pytest.mark.parametrize(
    ("case_id", "status", "code", "rule", "detail_keys"),
    [
        pytest.param(
            "INVALID-01",
            422,
            "POLICY_NOT_FOUND",
            "V-1",
            ("policy_number",),
            id="v1",
        ),
        pytest.param(
            "INVALID-02",
            422,
            "LOSS_BEFORE_INCEPTION",
            "V-2",
            ("loss_date", "effective_date"),
            id="v2",
        ),
        pytest.param(
            "INVALID-03",
            422,
            "LOSS_AFTER_EXPIRY",
            "V-3",
            ("loss_date", "expiry_date"),
            id="v3",
        ),
        pytest.param(
            "INVALID-04",
            422,
            "AMOUNT_EXCEEDS_LIMIT",
            "V-4",
            ("estimated_amount", "limit"),
            id="v4",
        ),
        pytest.param(
            "INVALID-05",
            422,
            "TYPE_NOT_COVERED",
            "V-5",
            ("claim_type", "permitted_claim_types"),
            id="v5",
        ),
        pytest.param(
            "INVALID-07",
            422,
            "POLICY_CANCELLED",
            "V-7",
            ("loss_date", "cancellation_date"),
            id="v7",
        ),
    ],
)
def test_each_policy_rule_refusal_through_http(
    client: TestClient,
    case_id: str,
    status: int,
    code: str,
    rule: str,
    detail_keys: tuple[str, ...],
) -> None:
    payload = _INVALID[case_id]
    response = client.post("/notifications", json=payload)
    assert response.status_code == status
    body = response.json()
    assert body["code"] == code
    detail = body["detail"]
    assert detail["rule"] == rule
    for key in detail_keys:
        assert key in detail
    if "policy_number" in detail_keys:
        assert detail["policy_number"] == payload["policy_number"]
    if "loss_date" in detail_keys:
        assert detail["loss_date"] == payload["loss_date"]
    if "claim_type" in detail_keys:
        assert detail["claim_type"] == payload["claim_type"]


def test_duplicate_notification_returns_409_with_existing_reference(
    client: TestClient,
) -> None:
    first = client.post("/notifications", json=_VALID["VALID-01"])
    assert first.status_code == 201
    recorded = first.json()["claim_reference"]

    duplicate = client.post("/notifications", json=_INVALID["INVALID-06"])
    assert duplicate.status_code == 409
    body = duplicate.json()
    assert body["code"] == "DUPLICATE_NOTIFICATION"
    assert body["detail"]["rule"] == "V-6"
    assert body["detail"]["claim_reference"] == recorded
