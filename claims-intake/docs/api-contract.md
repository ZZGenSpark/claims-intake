# Claims Intake Service: API Contract

Version 0.4. Owned by the claims intake team. Consumed by the claims portal team.

This document is the authority on what the service accepts, what it returns, and under what conditions it refuses. Where the code and this document disagree, the document is correct and the code is a defect.

Sections 1 through 3 are fixed. Do not edit them.

## 1. Purpose and scope

The claims intake service accepts a first notice of loss from the claims portal, validates it against the policy master and a table of business rules, and either records a notification and issues a claim reference or refuses the submission with a specific reason.

**In scope.** Accepting a notification, validating it, and recording it. Issuing a claim reference. Reporting the reason a notification was refused.

**Out of scope.** Adjusting, reserving, payment, and any decision about coverage beyond the rules in section 4. The service decides whether a notification is well formed and admissible. It does not decide whether the claim will be paid.

**The policy master is a dependency, not part of this service.** The service reads policy records from it and does not write to it. A policy that cannot be read is a condition this contract specifies, and it is specified separately from a policy that does not exist, because the two require different action from the caller.

**Compatibility.** Adding a field to a response is a compatible change and callers must ignore fields they do not recognize. Adding a new error code is a compatible change and callers must fall through to default handling for a code they do not recognize. Changing the meaning of an existing code, removing a field, or changing a status code for an existing condition is not compatible and does not happen without a version increment agreed with the portal team.

## 2. Request



### 2.1 Endpoint

```
POST /notifications
Content-Type: application/json
```



### 2.2 Body


| Field              | Type    | Required | Notes                                                         |
| ------------------ | ------- | -------- | ------------------------------------------------------------- |
| `policy_number`    | string  | yes      | Identifier as held in the policy master. Not empty.           |
| `loss_date`        | string  | yes      | Calendar date, `YYYY-MM-DD`.                                  |
| `claim_type`       | string  | yes      | One of the values in 2.3. Not empty.                          |
| `estimated_amount` | decimal | yes      | United States dollars, two decimal places. Greater than zero. |
| `description`      | string  | no       | Free text. Absent and `null` are equivalent.                  |


`policy_number` matching is exact; case is significant.

`estimated_amount` is a decimal of scale 2. A different scale is the wrong type (section 2.4). The service does not round or truncate.

The service rejects a body carrying a field not listed above. A misspelled field name is a defect in the caller's code, and accepting the payload with the field ignored would record a notification built from data the caller did not send.

### 2.3 Claim type vocabulary

`collision`, `theft`, `glass`, `liability`, `weather`.

Which of these are admissible on a given notification depends on the product the policy is written on. The vocabulary is the type of `claim_type`. A value not in this list cannot be interpreted. The permitted subset of that vocabulary is a property of the policy record and is evaluated by rule `V-5`.

### 2.4 Well formed against acceptable

A request that cannot be interpreted is refused with status `400`. This means the body was not valid JSON, a required field was absent, a field carried a value of the wrong type, a field was present that this contract does not define, a required string was empty, `loss_date` was not a calendar date `YYYY-MM-DD`, `estimated_amount` was not a decimal of scale 2, `estimated_amount` was not greater than zero, or `claim_type` was not one of the values in section 2.3. The caller's code is wrong. The service does not round or truncate.

A request that was interpreted and whose content is not admissible is refused with status `422`. The caller's data is wrong, and a person needs to see the reason.

This split is stated here once and holds without exception everywhere else in this document.

## 3. Success response

A notification that passes every rule in section 4 is recorded and the service responds:

```
201 Created
Content-Type: application/json

{
  "claim_reference": "CLM-2026-000317",
  "status": "recorded"
}
```

`**claim_reference**` matches the pattern `CLM-YYYY-NNNNNN`, where `YYYY` is the calendar year in which the notification was recorded and `NNNNNN` is a zero padded sequence. A claim reference is unique across all recorded notifications and is never reissued. It is the value the claims handler quotes and the value every downstream system keys on.

`**status**` is `recorded` on every success response this contract defines. It exists because the portal displays it and because a future state that is not `recorded` is foreseeable. Callers must not treat it as constant.

A refused notification is never recorded and no claim reference is issued. There is no partial outcome: either a notification exists with a reference, or nothing was written.

## 4. Validation



### 4.1 Evaluation order

A notification can fail several rules at once. The caller receives one
code. The service does not return a list of failures.

Rules are evaluated in this order, and evaluation stops at the first
failure. That rule's code is the only code returned:

V-1, V-7, V-2, V-3, V-4, V-5, V-6.

This is not ascending identifier order.

V-6 is evaluated last. The duplicate check is a lookup against recorded notifications and so records that can not pass the previous checks would not be recorded.

V-1 short circuits: if it fails, no later rule is evaluated.

V-7 applies only when the policy has a `cancellation_date`. When
`cancellation_date` is null, V-7 is skipped (WI-0158 AC-3) and
evaluation continues at V-2.

### 4.2 Rule table


| ID  | Condition                                                                                     | Code                     | Status |
| --- | --------------------------------------------------------------------------------------------- | ------------------------ | ------ |
| V-1 | `policy_number` exists in the policy master (exact, case-sensitive)                           | `POLICY_NOT_FOUND`       | 422    |
| V-2 | `loss_date` >= policy `effective_date`                                                        | `LOSS_BEFORE_INCEPTION`  | 422    |
| V-3 | `loss_date` <= policy `expiry_date`                                                           | `LOSS_AFTER_EXPIRY`      | 422    |
| V-4 | `estimated_amount` <= policy `limit`                                                          | `AMOUNT_EXCEEDS_LIMIT`   | 422    |
| V-5 | `claim_type` permitted on the policy's product                                                | `TYPE_NOT_COVERED`       | 422    |
| V-6 | recorded notification with the same `policy_number`,`loss_date`,`claim_type` can not be found | `DUPLICATE_NOTIFICATION` | 409    |
| V-7 | `loss_date` < policy `cancellation_date`                                                      | `POLICY_CANCELLED`       | 422    |


Boundaries are as written. A loss on the inception date is covered
(WI-0142, AC-3). An amount equal to the limit is within cover. A loss
on the cancellation date is not covered (WI-0158, AC-2): V-7 uses a
strict inequality, so `loss_date` < `cancellation_date` is required to
pass. When both V-3 and V-7 would fail, the order in 4.1 returns
`POLICY_CANCELLED`. V-1 lookup is exact; case is significant. A
`claim_type` outside section 2.3 never reaches V-5; it is
`UNINTERPRETABLE_REQUEST`. V-5 compares a vocabulary value to the
product's permitted subset. V-4 compares only a well-formed scale-2
amount greater than zero to the limit.

## 5. Error envelope

```
{
  "code": "LOSS_BEFORE_INCEPTION",
  "message": "Loss date precedes policy inception.",
  "detail": { }
}
```

`code`, `message`, and `detail` are always present. Status is not in
the body; section 6 maps `code` to a HTTP status.

`code` is stable. Callers branch on it. An unrecognized code uses the
caller's default path (section 1). `message` is not stable. It is for
display and may change without notice. Callers must not parse it or
branch on it.

`detail` keys vary by `code`. A caller may rely on a key only where
this section names it for that code, must not assume those keys on any
other code, and must ignore unrecognized keys. Adding a `detail` key is
compatible.

The three examples below are different handlers: a rule after the body
was interpreted, a body that never reached a rule, and a policy master
that did not answer. Their `detail` shapes are therefore different.

### Example 1. Rule failure

Interpreted body, refused by a section 4 rule. Rely on `rule` and the
compared fields. 

```
{
  "code": "LOSS_BEFORE_INCEPTION",
  "message": "Loss date before policy inception.",
  "detail": {
    "rule": "V-2",
    "loss_date": "2026-02-11",
    "effective_date": "2026-03-01"
  }
}
```



### Example 2. Request the service could not interpret

Section 2.4: the body could not be interpreted. No rule ran. Rely on
`field` and `issue`. Do not expect `rule` or policy dates.

```
{
  "code": "UNINTERPRETABLE_REQUEST",
  "message": "The request body could not be interpreted.",
  "detail": {
    "field": "estimated_amount",
    "issue": "required_field_missing"
  }
}
```



### Example 3. Policy master that did not answer

The master produced no usable answer. This is not `POLICY_NOT_FOUND`.
Callers tell timeout, unreachable, and unparsable apart by `code`
(section 6). `detail` carries `policy_number`. Do not expect `rule` or
a request `field`. The same request may succeed later.

```
{
  "code": "POLICY_MASTER_TIMEOUT",
  "message": "The policy master did not answer in time.",
  "detail": {
    "policy_number": "MOT-4471"
  }
}
```



## 6. Status code mapping


| Code                        | Status | Source                                      |
| --------------------------- | ------ | ------------------------------------------- |
| `UNINTERPRETABLE_REQUEST`   | 400    | Body could not be interpreted (section 2.4), including empty required strings, `claim_type` outside 2.3, `estimated_amount` not greater than zero, and `loss_date` not `YYYY-MM-DD` |
| `DUPLICATE_NOTIFICATION`    | 409    | V-6                                         |
| `POLICY_NOT_FOUND`          | 422    | V-1. Master answered; no match              |
| `LOSS_BEFORE_INCEPTION`     | 422    | V-2                                         |
| `LOSS_AFTER_EXPIRY`         | 422    | V-3                                         |
| `AMOUNT_EXCEEDS_LIMIT`      | 422    | V-4                                         |
| `TYPE_NOT_COVERED`          | 422    | V-5                                         |
| `POLICY_CANCELLED`          | 422    | V-7                                         |
| `POLICY_MASTER_UNPARSABLE`  | 502    | Master answered; body could not be parsed   |
| `POLICY_MASTER_UNREACHABLE` | 503    | Master could not be reached                 |
| `POLICY_MASTER_TIMEOUT`     | 504    | Master did not answer in time               |


