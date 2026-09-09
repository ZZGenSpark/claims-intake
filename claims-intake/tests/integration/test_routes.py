"""HTTP integration tests for notification outcomes.

These tests exercise POST /notifications. They do not call submit_notification.
Each test builds its own app, policy client, and repository so order cannot leak.
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
from claims.policy_client import LookupFailureReason, StubPolicyClient
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
_EDGE: dict[str, dict[str, Any]] = {
    case["id"]: case["payload"]
    for case in json.loads((DATA / "fnol_edge.json").read_text())
}


def _http_client(*, fail_with: LookupFailureReason | None = None) -> TestClient:
    return TestClient(
        create_app(
            policy_client=StubPolicyClient(fail_with=fail_with),
            repository=NotificationRepository(),
        )
    )


@pytest.fixture
def client() -> TestClient:
    return _http_client()


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


def test_missing_required_field_returns_400(client: TestClient) -> None:
    response = client.post("/notifications", json=_EDGE["EDGE-08"])
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "UNINTERPRETABLE_REQUEST"
    assert body["detail"]["field"] == "estimated_amount"
    assert body["detail"]["issue"] == "required_field_missing"
    assert "rule" not in body["detail"]


def test_extra_field_returns_400(client: TestClient) -> None:
    payload = {**_VALID["VALID-01"], "handler_notes": "ignored would be a defect"}
    response = client.post("/notifications", json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "UNINTERPRETABLE_REQUEST"
    assert body["detail"]["field"] == "handler_notes"
    assert body["detail"]["issue"] == "unexpected_field"
    assert "rule" not in body["detail"]


@pytest.mark.parametrize(
    ("reason", "status", "code"),
    [
        pytest.param("timeout", 504, "POLICY_MASTER_TIMEOUT", id="timeout"),
        pytest.param("unreachable", 503, "POLICY_MASTER_UNREACHABLE", id="unreachable"),
        pytest.param("unparsable", 502, "POLICY_MASTER_UNPARSABLE", id="unparsable"),
    ],
)
def test_policy_lookup_failed_returns_distinct_5xx(
    reason: LookupFailureReason,
    status: int,
    code: str,
) -> None:
    http = _http_client(fail_with=reason)
    response = http.post("/notifications", json=_VALID["VALID-01"])
    assert response.status_code == status
    assert response.status_code >= 500
    body = response.json()
    assert body["code"] == code
    assert body["detail"] == {"policy_number": _VALID["VALID-01"]["policy_number"]}
    assert "rule" not in body["detail"]
