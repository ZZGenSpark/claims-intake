# Day 2 unit tests

Source: `tests/unit/test_models.py` and `tests/unit/test_repository.py`.

These tests pin the request boundary and the record store. They do not evaluate business rules (V-1 through V-7) or HTTP status codes.

Fixtures return a fresh object each time. Multiple inputs use `@pytest.mark.parametrize` with named cases.

---

## `tests/unit/test_models.py`

### `test_notification_request_accepts_well_formed_payload`

Parses a valid payload. `loss_date` is a `date`. `estimated_amount` is a `Decimal`.

| Case | What it covers |
| --- | --- |
| `all_fields` | All five fields present |
| `description_absent` | Optional `description` omitted; equivalent to null |
| `description_null` | `description: null` |
| `claim_type_outside_vocabulary` | `"flood"` still parses; V-5 is not the model's job |

### `test_notification_request_rejects_invalid_payload`

Raises `ValidationError`.

| Case | Constraint violated |
| --- | --- |
| `unknown_field` | Extra field |
| `misspelled_field` | Extra field (`polcy_number`) |
| `missing_policy_number` | Required field |
| `missing_loss_date` | Required field |
| `missing_claim_type` | Required field |
| `missing_estimated_amount` | Required field (EDGE-08) |
| `empty_policy_number` | Not empty |
| `empty_claim_type` | Not empty |
| `policy_number_not_string` | Wrong type |
| `loss_date_not_date` | Wrong type |
| `claim_type_not_string` | Wrong type |
| `estimated_amount_not_decimal` | Wrong type |
| `description_not_string` | Wrong type |
| `date_wrong_separator` | `YYYY-MM-DD` only |
| `date_not_iso` | `YYYY-MM-DD` only |
| `datetime_not_date` | Calendar date, not datetime |
| `impossible_day` | Unparseable date |
| `empty_date` | Unparseable date |
| `three_fractional_digits` | Scale 2 (EDGE-12) |
| `one_fractional_digit` | Scale 2 |
| `zero_fractional_digits` | Scale 2 |
| `zero_amount` | Greater than zero |
| `negative_amount` | Greater than zero |

### `test_realistic_payloads_model_boundary`

Each payload in `data/fnol_invalid.json` and `data/fnol_edge.json`. Asserts only whether the **model** accepts or rejects. Rule outcomes are noted here for later days, not asserted.

| Payload | Model | Survives to rules as |
| --- | --- | --- |
| INVALID-01 | accept | V-1 `POLICY_NOT_FOUND` |
| INVALID-02 | accept | V-2 `LOSS_BEFORE_INCEPTION` |
| INVALID-03 | accept | V-3 `LOSS_AFTER_EXPIRY` |
| INVALID-04 | accept | V-4 `AMOUNT_EXCEEDS_LIMIT` |
| INVALID-05 | accept | V-5 `TYPE_NOT_COVERED` |
| INVALID-06 | accept | V-6 `DUPLICATE_NOTIFICATION` |
| INVALID-07 | accept | V-7 `POLICY_CANCELLED` |
| EDGE-01 | accept | accepted |
| EDGE-02 | accept | accepted |
| EDGE-03 | accept | accepted |
| EDGE-04 | accept | V-7 |
| EDGE-05 | accept | V-2 |
| EDGE-06 | accept | V-4 |
| EDGE-07 | accept | V-1 |
| EDGE-08 | **reject** | never a rule |
| EDGE-09 | accept | V-5 |
| EDGE-10 | accept | V-7 |
| EDGE-11 | accept | V-5 (`flood` is a string) |
| EDGE-12 | **reject** | never a rule |

### `test_policy_types_from_master`

Builds `Policy` from `StubPolicyClient`. Dates are `date`. `limit` is `Decimal`.

| Case | Policy | `cancellation_date` |
| --- | --- | --- |
| `uncancelled` | MOT-4471 | `None` |
| `cancelled` | MOT-4496 | a `date` |

### `test_policy_rejects_invalid_field`

Raises `ValidationError`.

| Case | Constraint violated |
| --- | --- |
| `effective_date_wrong_type` | Must be a date |
| `expiry_date_wrong_type` | Must be a date |
| `cancellation_date_wrong_type` | Must be a date or `None` |
| `limit_wrong_type` | Must be a decimal |
| `limit_wrong_scale` | Scale 2 |

### `test_policy_rejects_missing_field`

Each required field omitted, including `cancellation_date`. `None` is allowed; omitting the field is not.

| Case |
| --- |
| `policy_number` |
| `product` |
| `effective_date` |
| `expiry_date` |
| `cancellation_date` |
| `limit` |
| `permitted_claim_types` |

### `test_rule_failure_carries_rule_and_code_separately`

`rule` and `code` are distinct fields. The object is immutable.

| Case | `rule` | `code` |
| --- | --- | --- |
| `inception` | V-2 | `LOSS_BEFORE_INCEPTION` |
| `duplicate` | V-6 | `DUPLICATE_NOTIFICATION` |

Not in this file: claim-reference format. `RecordedNotification` only holds the reference. Issuing it is the repository's job.

---

## `tests/unit/test_repository.py`

Fixtures: `repository` is a new store per test. `make_notification` builds a fresh `NotificationRequest` (`date` and `Decimal`, not strings).

### `test_record_issues_unique_contract_references`

Records two different notifications.

- Each `claim_reference` matches `CLM-YYYY-NNNNNN`
- `YYYY` is the calendar year of recording
- The two references are different

### `test_find_matching_requires_all_three_fields`

Records `(MOT-4471, 2026-04-02, collision)`, then probes. A duplicate is all three fields together. Two of three is not a duplicate.

| Case | Probe | Duplicate? |
| --- | --- | --- |
| `all_three_match` | same policy, date, type | yes |
| `type_differs` | same policy and date, type `theft` | no |
| `date_differs` | same policy and type, date `2026-04-03` | no |
| `policy_differs` | same date and type, policy `MOT-4472` | no |

### `test_rejected_notification_is_not_a_duplicate`

WI-0151 AC-3. A rejected submission is never written, so it cannot be duplicated.

1. Build a notification. Do not call `record`.
2. `find_matching` on those three fields returns `None`.
3. Record a resubmission with the same keys. It succeeds and is the first record.
