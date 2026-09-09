# Agent decision log (Day 3)

Two changes produced during this assignment. Each decision cites a contract
section, a work-item criterion, or a failure that would have followed. Preference
is not a reason.

## Step 8. Gate observation

[Pull request #3](https://github.com/ZZGenSpark/claims-intake/pull/3)
(`3cde809`, `test_gate_probe.py`) failed the required `checks` jobs
(`pull_request` and `push`). The Merge button was disabled; GitHub
stated "Merging is blocked due to failing merge requirements." A
failing required check blocked the merge.

## Accepted. V-6 stays off `POLICY_RULES`

**What the agent produced.** A `POLICY_RULES` table of `(notification, policy)`
functions in section 4.1 order after V-1 (V-7, V-2, V-3, V-4, V-5), with
`evaluate_duplicate_notification` taking the repository and called only from
`submit_notification` after `evaluate_notification` returns `None`. A comment
on `POLICY_RULES` records that split.

**Decision.** Keep that placement.

**Reason.** Contract section 4.1 evaluates V-6 last because a notification that
failed an earlier rule is not recorded, so it cannot be a duplicate (WI-0151
AC-3). Instruction 4 and C3 require `evaluate_notification(notification, policy)`
with no I/O. Putting `repository.find_matching` inside `POLICY_RULES` would
make the decision table depend on the store. A later reader would then be
unable to test V-2–V-5 without a repository, and a refused submit could be
treated as a duplicate if anyone recorded before evaluation finished.

## Rejected. Add `policy_client` and `repository` to `evaluate_notification` tests

**What the agent produced.** After pytest reported `TypeError: missing
repository`, a proposed test change: call
`evaluate_notification(notification, policy_client, repository)` so the
calls matched the starter stub, and drop the in-memory `Policy` used for
boundary cases.

**Decision.** Do not change the tests. Change the stub signature instead so it
matches C3: `(notification, policy) -> RuleFailure | None`.

**Reason.** The Day 3 interface (C3) and the acceptance criterion
"`evaluate_notification` performs no I/O … and takes only a notification and
a policy" are the authority, not the unfinished starter. Aligning the tests
with the stub would have encoded a dependency the contract forbids.

A concrete failure that would have followed: V-5 cases used a policy whose
`permitted_claim_types` were only `collision` and `theft`, so `glass` is
`TYPE_NOT_COVERED`. `StubPolicyClient` policy `MOT-4471` permits `glass`.
Those tests would have asserted the wrong product subset, passed a V-5 miss,
and tomorrow’s HTTP mapping would have accepted a type the contract says to
refuse.
