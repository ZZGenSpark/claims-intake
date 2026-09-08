# Contract reconciliation (Day 2)

Every rejection `NotificationRequest`, `Policy`, and `RecordedNotification` can
produce was listed from the field constraints and validators, then looked up in
`docs/api-contract.md` section 6. Where section 6 or section 2.4 did not name
the cause, the contract was amended. This note records what was found, what was
added, and how the check was run.

## How the check was performed

1. Read `src/claims/models.py` and listed each `ValidationError` cause: missing
   required field, `extra="forbid"`, wrong JSON type, empty `policy_number`,
   `loss_date` not calendar `YYYY-MM-DD`, `claim_type` not in section 2.3,
   `estimated_amount` not scale 2, `estimated_amount` not greater than zero,
   `description` not a string, `Policy` field type/scale/vocabulary misses, and
   `claim_reference` not matching `CLM-YYYY-NNNNNN`.
2. For each cause, asked: does section 6 name a code and status for the HTTP
   response the service would return if this rejection reached the caller?
3. Model rejections never run a section 4 rule, so they must be
   `UNINTERPRETABLE_REQUEST` / 400. That code was already in section 6. The gap
   was section 2.4's closed list of causes, which did not name every rejection
   the models actually produce.
4. `RecordedNotification.claim_reference` is not a request-body rejection; it is
   an internal invariant from section 3. It does not need a section 6 row.

## What was found

| Model rejection | Section 6 before this check | Gap |
| --- | --- | --- |
| Invalid JSON / missing required / wrong type / extra field | `UNINTERPRETABLE_REQUEST` 400 | None. Already in 2.4. |
| `estimated_amount` not scale 2 | same code | Named in 2.2/2.4 already. |
| Empty `policy_number` or empty `claim_type` | same code | 2.4 did not list empty required strings. |
| `loss_date` not `YYYY-MM-DD` (wrong separator, datetime, impossible day) | same code | 2.2 stated the format; 2.4 did not list it as uninterpretable. |
| `estimated_amount` not greater than zero | same code | 2.2 required it; 2.4 did not list it. A zero amount is not a section 4 rule. |
| `claim_type` outside 2.3 (`flood`) | mapped to V-5 422 in 2.3/4.2 | Conflicted with 2.2 ("one of the values in 2.3") and with constraining the vocabulary on the model. |
| `Policy` type/scale/vocabulary / omitted `cancellation_date` | not a portal request | No section 6 row required. Built from the master, not from POST `/notifications`. |
| `claim_reference` outside `CLM-YYYY-NNNNNN` | not a portal request | Section 3 already fixes the format. |

No new error **code** was required. Every request-body rejection the models
produce is still `UNINTERPRETABLE_REQUEST`.

## What was added

- **2.3 / 2.4 / 4.2 / section 6:** a `claim_type` outside the vocabulary cannot
  be interpreted. It is 400, not V-5. V-5 compares a vocabulary value to the
  product's permitted subset (EDGE-09).
- **2.4 / section 6:** empty required strings, `loss_date` not `YYYY-MM-DD`, and
  `estimated_amount` not greater than zero are named as 400 causes.
- **`docs/payload-triage.md`:** EDGE-11 reclassified to
  `UNINTERPRETABLE_REQUEST` / 400. Decision 2 rewritten to that authority.

Repository refusals are not model rejections. V-6 remains
`DUPLICATE_NOTIFICATION` / 409 and is decided in the service, not in
`NotificationRepository.record`.
