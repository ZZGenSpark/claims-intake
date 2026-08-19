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
| EDGE-11 | rejected | -    | `UNINTERPRETABLE_REQUEST` | 400    |
| EDGE-12 | rejected | -    | `UNINTERPRETABLE_REQUEST` | 400    |




## Decision log

Three payloads cannot be classified against the contract as it shipped, because the contract left a decision unmade. For each one, record the ambiguity, the decision, its authority, and the alternative you rejected.

A decision recorded here and nowhere else has not been made. Amend `docs/api-contract.md` so that a reader of the contract alone could not arrive at the other reading.

### Decision 1

**Payload.** EDGE-04 (loss on the cancellation date).

**The ambiguity.** A
loss still inside the original term could be read as accepted. Once a
cancel rule exists, it was still open whether a loss *on*
`cancellation_date` is covered.

**Decision.** Reject. V-7, `POLICY_CANCELLED`, 422.

**Authority.** WI-0158 AC-1 and AC-2: cancellation starts at the
beginning of that date; a loss that day is not covered.

**Rejected alternative.** Accept because `loss_date` ≤ `expiry_date` and `loss_date` = `cancellation_date`

**Contract amended.** 4.2 V-7: `loss_date` < `cancellation_date`. Boundary note: a loss on the cancellation date is not covered. (Nothing Changed)

### Decision 2

**Payload.** EDGE-05 (before inception and above the limit).

**The ambiguity.** Two rules fail. The shipped 4.1 only spelled out
V-1's short circuit, so the caller could be given V-2, V-4, or both.

**Decision.** One code: the first failure in 4.1. That is V-2,
`LOSS_BEFORE_INCEPTION`, 422.

**Authority.** Section 4.1: one code, stop at the first failure. V-2
precedes V-4. 

**Rejected alternative.** Return `AMOUNT_EXCEEDS_LIMIT`, or a list of
codes. The caller sees one reason; the later rule is not evaluated.

**Contract amended.** 4.1: order V-1, V-7, V-2, V-3, V-4, V-5, V-6; first failure only. (Nothing Changed)

### Decision 3

**Payload.** EDGE-10 (after cancellation and after original expiry).

**The ambiguity.** Both V-3 and V-7 fail. Ascending IDs evaluate V-3
first and return `LOSS_AFTER_EXPIRY`.

**Decision.** `POLICY_CANCELLED`, 422. V-7 runs before V-3.

**Authority.** WI-0158 AC-4: tell the handler the policy was cancelled.
Expiry sends them to the wrong system.

**Rejected alternative.** `LOSS_AFTER_EXPIRY` from identifier order.
True that the date is after expiry; the wrong fact to report.

**Contract amended.** 4.1 evaluates V-7 before V-3. 4.2: when both  
would fail, return `POLICY_CANCELLED`. (Nothing Changed)