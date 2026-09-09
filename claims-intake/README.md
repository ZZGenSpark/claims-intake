# Claims Intake Service

Accepts a first notice of loss, checks it against the policy master and the
rule table in `docs/api-contract.md`, and either records it and issues a claim
reference or refuses it with a specific code.

You are already inside the Linux workspace container. Dependencies are present.
There is no install step.

If `pwd` is `/workspaces/claims-intake`, work in the project directory:

```
cd claims-intake
```

## Run the service

```
uv run uvicorn claims.api.routes:app --host 0.0.0.0 --port 8000
```

Then `POST /notifications` with a JSON body as in `docs/api-contract.md`.
Synthetic examples live in `data/fnol_valid.json`.

## Run the tests

```
uv run pytest
uv run ruff check .
uv run mypy src tests
```

Unit tests call the service as functions. Integration tests go through HTTP.

## Build the image / (Step 3 Answer)

From `claims-intake/`:

```
docker buildx build --platform linux/amd64 -t claims-intake .
docker run --rm -p 8000:8000 claims-intake
```

`--platform linux/amd64` is not “how you turn Docker on.” It names the **CPU the
image must run on**.

This workspace is Linux on ARM (`uname -m` is `aarch64`). GitHub’s check runner
and typical deploy hosts are Linux on x86 (`linux/amd64`). A Docker image built
here with no platform flag is an ARM image. That image will not start on an
amd64 machine, even though the Dockerfile’s `FROM python:3.12-…` line is the
same. `FROM` chooses the distro and Python. `--platform` chooses the
architecture those layers are built for.

## Where things are


| Path                              | What it holds                                                     |
| --------------------------------- | ----------------------------------------------------------------- |
| `docs/api-contract.md`            | What the service accepts, returns, and refuses. The authority.    |
| `docs/requirements-brief.md`      | Work items and acceptance criteria.                               |
| `docs/payload-triage.md`          | Day 1 classification of the edge payloads.                        |
| `docs/contract-reconciliation.md` | Day 2 check of model rejections against section 6.                |
| `data/`                           | Synthetic policies and notification payloads.                     |
| `src/claims/`                     | The service.                                                      |
| `tests/`                          | Unit tests mirror `src/claims/`. Integration tests exercise HTTP. |




## Data

Everything in `data/` is synthetic. No real client data and no named clients.