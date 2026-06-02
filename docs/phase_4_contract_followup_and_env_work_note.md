# Phase 4 Contract Follow-up And Environment Work Note

## Summary

This round closed out the recent Phase 0-4 architecture and contract work, then completed a local environment bring-up so the current codebase can be backed up and resumed safely.

The main product-side result is that the repository now consistently reflects:

- LangGraph as the primary competitive-analysis workflow
- Custom runner as a legacy fallback
- survey/questionnaire as a follow-up sidecar flow
- structured `core / extensions / diagnostics` envelopes across report and workflow summary
- explicit `DomainPack`, `CapabilityMap`, and questionnaire follow-up contracts across backend and frontend

The main engineering-side result is that the project is now runnable on this machine with a clean Python 3.12 virtual environment and installed frontend dependencies.

## Code Areas Included In This Backup

- backend workflow and contract updates:
  - `backend/app/agents/*`
  - `backend/app/api/routes.py`
  - `backend/app/domain/*`
  - `backend/app/schemas/*`
  - `backend/app/services/survey_service.py`
- frontend contract and UI updates:
  - `frontend/src/App.tsx`
  - `frontend/src/api/types.ts`
  - `frontend/src/components/*`
  - `frontend/src/pages/SurveyWorkspacePage.tsx`
  - `frontend/src/lib/*`
- docs updates:
  - `docs/architecture.md`
  - `README.md`

## Environment Bring-up

The repository-local legacy `.venv` is Python 3.8, which is not compatible with the current codebase because the code now uses modern typing syntax such as `list[str]` and `str | None`.

To make the project runnable locally:

- frontend dependencies were installed with `npm.cmd install`
- a new Windows CPython 3.12 virtual environment was created at `./.venv-win312`
- backend dependencies were installed into `./.venv-win312`
- `langgraph` was aligned to a version that provides `StateGraph`
- `eval_type_backport` was installed to support the current runtime type evaluation path used by Pydantic

Environment-only paths are now ignored in `.gitignore`:

- `/.venv/`
- `/.venv312/`
- `/.venv-win312/`
- `/cis_demo.db`

## Small Compatibility Fixes Applied During Bring-up

These were minimal compatibility fixes needed to run the project on the current machine:

- `backend/app/database.py`
  - switched `Generator` import to `typing.Generator`
- `backend/app/schemas/models.py`
- `backend/app/schemas/agent_io.py`
- `backend/app/schemas/workflow_state.py`
- `backend/app/schemas/survey.py`
  - added `from __future__ import annotations`
- `backend/app/schemas/models.py`
  - adjusted one forward-reference annotation in `CapabilityMap`
- `frontend/src/types.tsx`
  - re-exported missing frontend types used by components

## Validation Result

Completed successfully:

- backend import/compile check:
  - `python -m compileall backend/app`
- frontend production build:
  - `npm.cmd run build`
- backend runtime health check:
  - `GET /health` returned `{"status":"ok"}`

Partially successful:

- backend targeted test run:
  - `python -m pytest backend/tests/test_schema_and_workflow.py -q`
  - result: `76 passed, 20 failed`

## Remaining Known Issues

The remaining failures are no longer environment-install issues. They are code/test alignment issues and should be handled as normal development follow-up:

- some `AnalystAgent` expectations in tests still assume older feature-tree behavior
- some tests still treat typed extension models as plain dictionaries
- some LangGraph tests still hit SQLite table lifecycle/setup issues during test execution

## Recommended Next Step

If work resumes later, the clean next step is:

1. fix the remaining backend test failures in `backend/tests/test_schema_and_workflow.py`
2. rerun the full backend suite on `./.venv-win312`
3. optionally standardize project docs and startup scripts to point to `./.venv-win312` until the old root `.venv` is retired
