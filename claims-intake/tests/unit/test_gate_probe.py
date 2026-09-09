"""Deliberate failing check for pipeline step 8. Delete or revert after observing CI."""


def test_gate_probe_fails_on_purpose() -> None:
    assert False, "intentional failure to confirm the PR check goes red"
