"""Boundary models for the claims intake service.

Everything that enters the service is parsed into one of these before any rule
runs. A payload that reaches the rule layer has already been proven well formed,
which is what keeps a shape problem and a content problem from arriving at the
caller as the same status code.

Day 2 assignment. Implement these against `docs/api-contract.md` sections 2 and 3.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NotificationRequest(BaseModel):
    """A first notice of loss as submitted by the claims portal.

    Fields and their constraints are specified in contract section 2.2. The model
    is responsible for the shape of the request and for nothing else. Whether the
    policy exists, whether the loss falls inside the term, and whether the amount
    is within the limit are rules, and rules live in `service.py`.

    `policy_number` is declared so that the V-1 rule in `service.py` has something
    to read. Every other field, and every constraint on every field including this
    one, is Day 2's work.
    """
    model_config = ConfigDict(extra="forbid")
    policy_number: str = Field(min_length=1)
    loss_date: date
    claim_type: str = Field(min_length=1)
    estimated_amount: Decimal = Field(decimal_places=2)
    description: str | None = None

class Policy(BaseModel):
    """A policy as this service works with it.

    Built from the `PolicyRecord` the policy client returns. The fields the rules
    compare against are the reason this model exists.

    `cancellation_date` is `date | None` and has no default. An uncancelled
    policy carries `None` (WI-0158 AC-3). Comparing `loss_date` to it without
    first handling absence is a type error, so V-7 cannot be written as a
    comparison against a sentinel date.
    """

    model_config = ConfigDict(extra="forbid")

    policy_number: str = Field(min_length=1)
    product: str
    effective_date: date
    expiry_date: date
    cancellation_date: date | None
    limit: Decimal = Field(decimal_places=2)
    permitted_claim_types: tuple[str, ...]

    @field_validator("limit")
    @classmethod
    def limit_is_scale_2(cls, value: Decimal) -> Decimal:
        exponent = value.as_tuple().exponent
        if not isinstance(exponent, int) or exponent != -2:
            raise ValueError("limit must have exactly two decimal places")
        return value

class RecordedNotification(BaseModel):
    """A notification that passed every rule and was written.

    Carries the claim reference issued at the time it was recorded. Contract
    section 3 fixes the reference format.

    Day 2 assignment: declare the fields.
    """


@dataclass(frozen=True)
class RuleFailure:
    """A named rule refusal: the rule id and the stable contract code.

    These are kept as separate fields so a caller can branch on `code` and still
    report which rule produced it. The object is immutable so a later layer
    cannot rewrite the decision.
    """

    rule: str
    code: str
