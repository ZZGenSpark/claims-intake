# Day 2 unit tests

Source: `tests/unit/test_models.py` and `tests/unit/test_repository.py`.

These tests pin the request boundary and the record store. They do not evaluate business rules (V-1 through V-7) or HTTP status codes.

Fixtures return a fresh object each time. Multiple inputs use `@pytest.mark.parametrize` with named cases.

---

## `tests/unit/test_models.py`

### `test_notification_request_accepts_section_2_2_body`

Parses a valid payload. `loss_date` is a `date`. `estimated_amount` is a `Decimal`.

| Case | What it covers |
| --- | --- |
| `all_fields` | All five fields present |
| `description_absent` | Optional `description` omitted; equivalent to null |
| `description_null` | `description: null` |
| `vocabulary_theft` | Section 2.3 value |
| `vocabulary_glass` | Section 2.3 value |
| `vocabulary_liability` | Section 2.3 value |
| `vocabulary_weather` | Section 2.3 value |

### `test_notification_request_rejects_uninterpretable_body`

Raises `ValidationError`. HTTP mapping is section 6 `UNINTERPRETABLE_REQUEST`.

| Case | Constraint violated |
| --- | --- |
| `unknown_field` | Extra field |
| `misspelled_field` | Extra field (`polcy_number`) |
| `missing_policy_number` | Required field |
| `missing_loss_date` | Required field |
| `missing_claim_type` | Required field |
| `missing_estimated_amount` | Required field (EDGE-08) |
| `empty_policy_number` | Not empty |
| `empty_claim_type` | Not empty / not in 2.3 |
| `claim_type_outside_section_2_3` | `"flood"` is not in 2.3 |
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
| EDGE-11 | **reject** | never a rule (`flood`) |
| EDGE-12 | **reject** | never a rule |

### `test_policy_cancellation_date_is_absent_or_a_date`

Builds `Policy` from `StubPolicyClient`. Dates are `date`. `limit` is `Decimal`. WI-0158 AC-3: uncancelled is `None`.

| Case | Policy | `cancellation_date` |
| --- | --- | --- |
| `uncancelled` | MOT-4471 | `None` |
| `cancelled` | MOT-4496 | a `date` |

### `test_policy_rejects_uninterpretable_field`

Raises `ValidationError`.

| Case | Constraint violated |
| --- | --- |
| `effective_date_wrong_type` | Must be a date |
| `expiry_date_wrong_type` | Must be a date |
| `cancellation_date_wrong_type` | Must be a date or `None` |
| `limit_wrong_type` | Must be a decimal |
| `limit_wrong_scale` | Scale 2 |
| `permitted_type_outside_2_3` | Same vocabulary as 2.3 |
| `unknown_field` | Extra field |

### `test_policy_rejects_omitted_required_field`

Each required field omitted, including `cancellation_date`. `None` is allowed; omitting the field is not.

### `test_recorded_notification_holds_section_3_reference`

Holds `CLM-2026-000317` and the original notification.

### `test_recorded_notification_rejects_reference_outside_section_3`

| Case | Constraint violated |
| --- | --- |
| `year_not_four_digits` | `CLM-YYYY-NNNNNN` |
| `sequence_not_six_digits` | `CLM-YYYY-NNNNNN` |
| `trailing_extra` | Exact pattern |
| `wrong_prefix_case` | `CLM` prefix |
| `empty` | Required |

### `test_rule_failure_separates_rule_id_from_error_code`

`rule` and `code` are distinct fields. The object is immutable.

| Case | `rule` | `code` |
| --- | --- | --- |
| `inception` | V-2 | `LOSS_BEFORE_INCEPTION` |
| `duplicate` | V-6 | `DUPLICATE_NOTIFICATION` |

Issuing a reference is the repository's job.

---

## `tests/unit/test_repository.py`

Fixtures: `repository` is a new store per test. `make_notification` builds a fresh `NotificationRequest` (`date` and `Decimal`, not strings).

### `test_issue_claim_reference_matches_section_3_and_is_never_reissued`

Calls `issue_claim_reference` twice without recording. Both match `CLM-YYYY-NNNNNN`. They differ.

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
