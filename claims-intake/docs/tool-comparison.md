# Tool comparison

I did Day 4 in Cursor only. I compared Plan, Ask, and Agent on one slice:
`POST /notifications`, and where the 201 `claim_reference` comes from.

**Plan** wrote the status table first (400 vs 422 vs 5xx) so I did not mix
them. **Ask** is how I saw the bug: `submit_notification` throws away the
reference from `record()`, and the route looks it up again. **Agent** then
put `claim_reference` on the success result.

## Easy and Hard

Plan stops you starting code before the statuses are fixed. It also writes
a long commit list you may not follow.

Ask answers "why does 201 work if submit does not return a reference?"
without changing files. Agent, if it can write, "fixes" 201 by searching
the store. That hides the real bug.

Agent is good after you already know the change: add the field, update two
call sites. Agent is bad at finding that the field is missing.

## What I reach for

Plan when I might give a missing field the same status as an unknown policy.
Ask when the code looks fine and I do not know why. Agent when I already
know the edit.

If I can only keep one, I keep Ask and change `submit_notification` myself.
An Agent told to "ship the route" will ship a 201 that does not come from
submit. That is what happened here.