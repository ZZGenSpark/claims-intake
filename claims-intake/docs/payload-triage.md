# Payload Triage

Every payload in `data/fnol_edge.json` classified against `docs/api-contract.md` as you have completed it. The classification records what the contract says the service does, which is not always what the payload obviously violates.

Fill one row per payload. Where a payload is accepted, leave the rule, code, and status columns as `-`.

## Classification


| Payload | Outcome  | Rule | Code                      | Status |
| ------- | -------- | ---- | ------------------------- | ------ |
| EDGE-01 | accepted | -    | -                         | -      |
| EDGE-02 | accepted | -    | -                         | -      |
| EDGE-03 | accepted | -    | -                         | -      |
| EDGE-04 | rejected | V-7  | `POLICY_CANCELLED`        | 422    |
| EDGE-05 | rejected | V-2  | `LOSS_BEFORE_INCEPTION`   | 422    |
| EDGE-06 | rejected | V-4  | `AMOUNT_EXCEEDS_LIMIT`    | 422    |
| EDGE-07 | rejected | V-1  | `POLICY_NOT_FOUND`        | 422    |
| EDGE-08 | rejected | -    | `UNINTERPRETABLE_REQUEST` | 400    |
| EDGE-09 | rejected | V-5  | `TYPE_NOT_COVERED`        | 422    |
| EDGE-10 | rejected | V-7  | `POLICY_CANCELLED`        | 422    |
| EDGE-11 | rejected | V-5  | `TYPE_NOT_COVERED`        | 422    |
| EDGE-12 | rejected | -    | `UNINTERPRETABLE_REQUEST` | 400    |




## Decision log

Three payloads cannot be classified against the contract as it shipped, because the contract left a decision unmade. For each one, record the ambiguity, the decision, its authority, and the alternative you rejected.

A decision recorded here and nowhere else has not been made. Amend `docs/api-contract.md` so that a reader of the contract alone could not arrive at the other reading.

### Decision 1

**Payload.** EDGE-07 (case-sensitive policy number).

**The ambiguity.** The master holds `MOT-4471`. The payload
is `mot-4471`. V-1 and 2.2 never said whether the match is
case-sensitive.

**Decision.** Reject. V-1, `POLICY_NOT_FOUND`, 422.

**Authority.** Section 2.2: identifier as held in the policy
master. V-1: the number must exist.

**Rejected alternative.** Fold case and accept. That is not
the identifier the master holds.

**Contract amended.** 2.2 and 4.2 V-1: lookup is exact; case
is significant.

### Decision 2

**Payload.** EDGE-11 (invalid claim type).

**The ambiguity.** `flood` is a string and not in 2.3. 2.4's
400 list is JSON, missing field, wrong type, or extra field.
Open whether that is 400 or V-5.

**Decision.** Reject. V-5, `TYPE_NOT_COVERED`, 422.

**Authority.** Section 2.4: the 400 list is closed;
interpreted but not admissible is 422. Section 2.3:
admissibility of claim type is V-5.

**Rejected alternative.** `UNINTERPRETABLE_REQUEST` 400.
The field type is string; `flood` was interpreted.

**Contract amended.** 2.3 and 4.2 V-5: a `claim_type` outside
2.3 fails V-5. It is not a 400.

### Decision 3

**Payload.** EDGE-12 (three-decimal amount).

**The ambiguity.** 2.2 types the field as decimal, USD, two
decimal places. Three fractional digits could be accepted as
a decimal, or refused as the wrong type.

**Decision.** Reject. `UNINTERPRETABLE_REQUEST`, 400.

**Authority.** Section 2.2: USD, two decimal places. Section
2.4: wrong type is 400.

**Rejected alternative.** Parse at full scale and accept, or
round. The amount is under the limit either way; that records
millicents or changes the figure.

**Contract amended.** 2.2: `estimated_amount` is scale 2. A
different scale is the wrong type (2.4). Do not round.