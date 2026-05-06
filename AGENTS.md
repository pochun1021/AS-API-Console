# AGENTS.md

This file defines how Codex/agents must work in this repository.

## Instruction Priority
1. `docs/SPEC.md` (source of truth for product/API/data behavior)
2. `README.md` (project setup/status)
3. Other notes/tasks

If conflicts exist, follow the higher-priority document and report the conflict.

## Current Project Mode
- This repo is currently spec-first and docs-heavy.
- For behavior changes, update spec first, then other files.

## Protected Contract (Do Not Break)
- Auth identity source of truth: `account`, `name`, `email`, `department`, `sysid` from auth context.
- Role model is only `user` and `admin`.
- API paths must stay resource-oriented (no `/my/*`, no `/admin/*` route naming).
- Key status source of truth: `api_keys.status` (`active|revoked|expired`).
- Plaintext API key must only be returned at creation time; never from later query endpoints.

## Protected API Surface
- `POST /api/v1/api-keys/applications`
- `GET /api/v1/api-keys`
- `GET /api/v1/api-keys/{id}`
- `POST /api/v1/api-keys/{id}/revoke`
- `POST /api/v1/whitelists`
- `GET /api/v1/whitelists`
- `PATCH /api/v1/whitelists/{id}`
- `POST /api/v1/admins/{id}/grant-admin`
- `POST /api/v1/admins/{id}/revoke-admin`

## Required Workflow For Agents
1. Read relevant sections in `docs/SPEC.md` before proposing/implementing changes.
2. Check whether requested changes touch protected contract or protected API surface.
3. If yes, update `docs/SPEC.md` in the same task and keep acceptance criteria consistent.
4. Keep changes scoped; do not mix unrelated edits.
5. After any frontend code change, run `npm run build` in `frontend` and report the result.
6. Report what changed, which spec rules were affected, and any residual risk.

## Change Rules
- Terminology must stay consistent across files (`sysid`, `user/admin`, resource-oriented routes).
- Do not silently introduce new roles, duplicate status flags, or parallel auth truth sources.
- Do not revert unrelated local changes.
- If unexpected dirty changes are found, stop and ask for direction.

## Pre-Commit Checklist
- No leftover old terms: `subject_type`, `subject_id`, `/api/v1/my/`, `/api/v1/admin/`.
- `README.md` and `docs/SPEC.md` use consistent route/identity/role wording when touched.
- Acceptance criteria are updated when behavior or contract changes.
- If frontend files were modified, `npm run build` has been executed in `frontend` successfully.

## Commit Guidance
- Use focused commit messages like:
  - `spec: ...`
  - `docs: ...`
  - `chore: ...`
- Keep each commit single-purpose and traceable to a spec change.
