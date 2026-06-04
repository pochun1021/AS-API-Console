# External API Integration Document

> Source domain: `api.ascs.sinica.edu.tw`  
> Purpose: API key and team limit management for AI API service  
> Repo integration contract: no `models` field in outbound `/key/generate` requests  
> Repo key type: `llm_api`

---

## 1. Overview

This document describes the external API endpoints used for API key lifecycle management and team-level budget/rate-limit management.
It is intended for project maintenance, API integration review, and Codex-assisted development.

### Base URL

```text
https://api.ascs.sinica.edu.tw
```

### Common Notes

- All endpoints in this document are management APIs.
- Request and response examples are based on the provided external API specification and project-specific integration rules.
- This repo currently uses a narrower outbound contract than the broader upstream provider API: generated key requests omit `models` and send `key_type=llm_api`.
- In this repo, application create and renew both use `POST /key/generate`.
- In this repo, outbound `/key/generate` requests always include `team_id` from `PROVIDER_TEAM_ID`.
- `PATCH /main/api/v1/limit-strategy-config` maps to `POST /team/update` with the same `team_id`.
- Repo-facing key display format is environment-specific: `APP_ENV=prod` uses `sk-` / `sk-...XXXX`; `dev/test` uses `AS-` / `AS-...XXXX`.
- Sensitive fields such as `key`, `token`, generated API keys, and hashed keys must not be logged in plaintext.
- Recommended timeout: define explicitly in application code, for example `30s`.
- This repo uses `Authorization: Bearer {PROVIDER_MASTER_KEY}` for management API calls.

---

## 2. Endpoint Summary

| Endpoint | Method | Purpose |
|---|---:|---|
| `/key/generate` | `POST` | Generate a new API key based on provided configuration. |
| `/key/update` | `POST` | Update parameters of an existing API key. |
| `/key/block` | `POST` | Block a virtual key from making further requests. |
| `/key/delete` | `POST` | Delete one or more keys from the key management system. |
| `/team/update` | `POST` | Update team budget and rate limits that apply to keys associated with the team. |

---

## 3. Common Duration Format

The following fields may use duration strings:

- `duration`
- `budget_duration`

Supported examples:

```text
30s  # 30 seconds
30m  # 30 minutes
30h  # 30 hours
30d  # 30 days
1h   # 1 hour
```

---

## 4. API Details

## 4.1 Generate API Key

### Endpoint

```http
POST /key/generate
```

### Description

Generate an API key based on the provided data.

### Request Parameters

| Field | Type | Required | Description |
|---|---|---:|---|
| `team_id` | `string` | No | Team ID to associate with the generated API key. All keys with this `team_id` are constrained by team-level limits. |
| `duration` | `string` | No | Token validity duration. Example: `30s`, `30m`, `30h`, `30d`. |
| `key_alias` | `string` | No | User-defined key alias. |
| `max_budget` | `float` | No | Maximum budget for the generated key. |
| `rpm_limit` | `integer` | No | Requests per minute limit. |
| `tpm_limit` | `integer` | No | Tokens per minute limit. |
| `budget_duration` | `string` | No | Budget reset duration. If not set, budget is never reset. |
| `key_type` | `string` | No | Key type that determines default allowed routes. Options: `llm_api`, `management`, `read_only`, `default`. Defaults to `default`. |

### Repo-specific Generate Key Rules

- Do not send the `models` field in outbound requests.
- Always send `key_type` as `llm_api` unless the project requirement changes.
- In this repo, always send `team_id` from `PROVIDER_TEAM_ID`.
- Team-level TPM/RPM/budget policies may cap the generated key's effective limits.

### Request Body Example

```json
{
  "team_id": "string",
  "key_alias": "string",
  "duration": "string",
  "max_budget": 0,
  "tpm_limit": 0,
  "rpm_limit": 0,
  "budget_duration": "string",
  "key_type": "llm_api"
}
```

### Success Response

#### HTTP 200

```json
{
  "key_alias": "string",
  "duration": "string",
  "models": [],
  "spend": 0,
  "max_budget": 0,
  "user_id": "string",
  "team_id": "string",
  "agent_id": "string",
  "max_parallel_requests": 0,
  "metadata": {},
  "tpm_limit": 0,
  "rpm_limit": 0,
  "budget_duration": "string",
  "budget_limits": [
    {
      "budget_duration": "string",
      "max_budget": 0,
      "reset_at": "2026-06-02T07:32:16.032Z"
    }
  ],
  "blocked": true,
  "key": "string",
  "budget_id": "string",
  "key_name": "string",
  "expires": "2026-06-02T07:32:16.032Z",
  "token_id": "string",
  "organization_id": "string",
  "project_id": "string",
  "token": "string",
  "created_by": "string",
  "updated_by": "string",
  "created_at": "2026-06-02T07:32:16.032Z",
  "updated_at": "2026-06-02T07:32:16.032Z"
}
```

### Validation Error Response

#### HTTP 422

```json
{
  "detail": [
    {
      "loc": ["string", 0],
      "msg": "string",
      "type": "string"
    }
  ]
}
```

### Implementation Notes

- Treat `key` and `token` as secrets.
- Store generated keys securely.
- Do not expose generated keys to frontend logs, browser console, or client-side storage unless explicitly required and reviewed.
- Use `team_id` when generated keys should inherit team-level TPM/RPM/budget policies.

---

## 4.2 Update API Key

### Endpoint

```http
POST /key/update
```

### Description

Update an existing API key's parameters.

### Request Parameters

| Field | Type | Required | Description |
|---|---|---:|---|
| `key` | `string` | Yes | The API key to update. |
| `key_alias` | `string` | No | User-friendly key alias. |
| `tpm_limit` | `integer` | No | Tokens per minute limit. |
| `rpm_limit` | `integer` | No | Requests per minute limit. |
| `budget_duration` | `string` | No | Budget reset period. Example: `30d`, `1h`. |
| `max_budget` | `float` | No | Maximum budget for the key. |
| `duration` | `string` or `null` | No | Key validity duration. Use `null` to never expire. `-1` is deprecated. |

### Request Body Example

```json
{
  "key_alias": "string",
  "duration": "string",
  "max_budget": 0,
  "tpm_limit": 0,
  "rpm_limit": 0,
  "budget_duration": "string",
  "key": "string"
}
```

### Success Response

#### HTTP 200

```json
"string"
```

### Validation Error Response

#### HTTP 422

```json
{
  "detail": [
    {
      "loc": ["string", 0],
      "msg": "string",
      "type": "string"
    }
  ]
}
```

### Implementation Notes

- `key` is sensitive and should be masked in logs.
- Use `null` instead of `-1` when setting a key to never expire.
- Confirm whether partial update semantics apply; omitted fields are assumed unchanged unless the API behaves otherwise.

---

## 4.3 Block API Key

### Endpoint

```http
POST /key/block
```

### Description

Block a virtual key from making any requests.

### Request Parameters

| Field | Type | Required | Description |
|---|---|---:|---|
| `key` | `string` | Yes | Key to block. Can be either an unhashed key such as `sk-...` or the hashed key value. |

### Request Body Example

```json
{
  "key": "string"
}
```

### Success Response

#### HTTP 200

```json
{
  "token": "string",
  "key_name": "string",
  "key_alias": "string",
  "spend": 0,
  "max_budget": 0,
  "expires": "string",
  "models": [],
  "aliases": {},
  "config": {},
  "user_id": "string",
  "team_id": "string",
  "agent_id": "string",
  "project_id": "string",
  "max_parallel_requests": 0,
  "metadata": {},
  "tpm_limit": 0,
  "rpm_limit": 0,
  "budget_duration": "string",
  "budget_reset_at": "2026-06-02T08:03:27.812Z",
  "allowed_cache_controls": [],
  "allowed_routes": [],
  "permissions": {},
  "model_spend": {},
  "model_max_budget": {},
  "soft_budget_cooldown": false,
  "blocked": true,
  "org_id": "string",
  "created_at": "2026-06-02T08:03:27.812Z",
  "created_by": "string",
  "updated_at": "2026-06-02T08:03:27.812Z",
  "updated_by": "string",
  "last_active": "2026-06-02T08:03:27.812Z",
  "rotation_count": 0,
  "auto_rotate": false,
  "rotation_interval": "string",
  "last_rotation_at": "2026-06-02T08:03:27.812Z",
  "key_rotation_at": "2026-06-02T08:03:27.812Z"
}
```

### Validation Error Response

#### HTTP 422

```json
{
  "detail": [
    {
      "loc": ["string", 0],
      "msg": "string",
      "type": "string"
    }
  ]
}
```

### Implementation Notes

- Use this endpoint when a key is compromised, retired, or temporarily disabled.
- Confirm whether blocked keys can be unblocked through another endpoint.
- Log only masked key identifiers.

---

## 4.4 Delete API Key

### Endpoint

```http
POST /key/delete
```

### Description

Delete one or more keys from the key management system.

### Request Parameters

| Field | Type | Required | Description |
|---|---|---:|---|
| `keys` | `array[string]` | Conditional | List of keys or hashed keys to delete. Can be passed instead of `key_aliases`. |
| `key_aliases` | `array[string]` | Conditional | List of key aliases to delete. Can be passed instead of `keys`. |

At least one of `keys` or `key_aliases` should be provided.

### Request Body Example

```json
{
  "keys": [
    "sk-QWrxEynunsNpV1zT48HIrw",
    "837e17519f44683334df5291321d97b8bf1098cd490e49e215f6fea935aa28be"
  ],
  "key_aliases": [
    "alias1",
    "alias2"
  ]
}
```

### Success Response

#### HTTP 200

The provided API note describes the returned data as `deleted_keys`, but the response schema also shows `code 200` as a string. Confirm the actual production response shape before implementation.

Expected logical return shape:

```json
{
  "deleted_keys": [
    "sk-QWrxEynunsNpV1zT48HIrw",
    "837e17519f44683334df5291321d97b8bf1098cd490e49e215f6fea935aa28be"
  ]
}
```

Documented response shape:

```json
"string"
```

### Validation Error Response

#### HTTP 422

```json
{
  "detail": [
    {
      "loc": ["string", 0],
      "msg": "string",
      "type": "string"
    }
  ]
}
```

### Implementation Notes

- Delete is a destructive operation. Require confirmation at the application layer before calling this endpoint.
- Prefer deletion by hashed key or alias when possible to avoid handling plaintext secrets.
- Mask values in `keys` and `key_aliases` in logs.
- Confirm whether deleted keys can be recovered.

---

## 4.5 Update Team Budget and Rate Limits

### Endpoint

```http
POST /team/update
```

### Description

Update team-level budget and rate limits. These limits apply as the maximum allowed limits for all keys associated with the specified `team_id`.

### Request Parameters

| Field | Type | Required | Description |
|---|---|---:|---|
| `team_id` | `string` | Yes | Team ID to update. This field is required by the integration so the backend can identify which team should receive the new limits. |
| `tpm_limit` | `integer` | No | Team TPM limit. All keys with this `team_id` will have at most this tokens-per-minute limit. |
| `rpm_limit` | `integer` | No | Team RPM limit. All keys associated with this `team_id` will have at most this requests-per-minute limit. |
| `max_budget` | `float` | No | Maximum budget allocated to the team. All keys for this `team_id` will have at most this budget. |
| `budget_duration` | `string` | No | Duration of the budget for the team. Example: `30d`, `1h`. |

### Request Body Example

```json
{
  "team_id": "string",
  "tpm_limit": 0,
  "rpm_limit": 0,
  "max_budget": 0,
  "budget_duration": "string"
}
```

### Success Response

#### HTTP 200

```json
"string"
```

### Validation Error Response

#### HTTP 422

```json
{
  "detail": [
    {
      "loc": ["string", 0],
      "msg": "string",
      "type": "string"
    }
  ]
}
```

### Implementation Notes

- Use `/team/update` when the system needs one shared TPM/RPM/budget policy for every key under the same team.
- In this repo, `PATCH /main/api/v1/limit-strategy-config` must sync to `/team/update` with `team_id`, `tpm_limit`, `rpm_limit`, `max_budget`, and `budget_duration`.
- Team limits are maximum caps. Individual keys may still have lower limits if set directly on the key.
- After updating team limits, newly generated keys using the same `team_id` should be treated as constrained by the team policy.
- Confirm whether existing keys immediately inherit updated team limits or only after key update/new key generation.

---

## 5. Error Handling

| HTTP Status | Meaning | Recommended Handling |
|---:|---|---|
| `200` | Success | Parse response body and update local state. |
| `422` | Validation error | Check request body fields, types, and required values. Surface a clear error message to backend logs. |

### Standard Error Shape

```json
{
  "detail": [
    {
      "loc": ["string", 0],
      "msg": "string",
      "type": "string"
    }
  ]
}
```

---

## 6. Security Checklist

- Do not commit API keys, tokens, generated secrets, or hashed keys to Git.
- Use environment variables or a secret manager.
- Mask secrets in application logs.
- Avoid returning management API secrets to frontend unless absolutely necessary.
- Restrict access to management endpoints in backend services.
- Define timeout, retry, and failure handling explicitly.
- Add audit logs for key generation, update, block, delete, and team limit update events.
- Require explicit confirmation for destructive operations such as `/key/delete`.

---

## 7. Suggested Backend Environment Variables

```env
ASCS_API_BASE_URL=https://api.ascs.sinica.edu.tw
ASCS_API_TIMEOUT_SECONDS=30
ASCS_API_AUTH_TOKEN=<set-in-secret-manager>
```

---

## 8. Suggested Python Client Skeleton

```python
import os
from typing import Any

import requests

ASCS_API_BASE_URL = os.getenv("ASCS_API_BASE_URL", "https://api.ascs.sinica.edu.tw")
ASCS_API_TIMEOUT_SECONDS = int(os.getenv("ASCS_API_TIMEOUT_SECONDS", "30"))
ASCS_API_AUTH_TOKEN = os.getenv("ASCS_API_AUTH_TOKEN")


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if ASCS_API_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {ASCS_API_AUTH_TOKEN}"
    return headers


def generate_key(payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        f"{ASCS_API_BASE_URL}/key/generate",
        json=payload,
        headers=_headers(),
        timeout=ASCS_API_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def update_key(payload: dict[str, Any]) -> str:
    response = requests.post(
        f"{ASCS_API_BASE_URL}/key/update",
        json=payload,
        headers=_headers(),
        timeout=ASCS_API_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def block_key(key: str) -> dict[str, Any]:
    response = requests.post(
        f"{ASCS_API_BASE_URL}/key/block",
        json={"key": key},
        headers=_headers(),
        timeout=ASCS_API_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def delete_keys(
    keys: list[str] | None = None,
    key_aliases: list[str] | None = None,
) -> Any:
    if not keys and not key_aliases:
        raise ValueError("Either keys or key_aliases must be provided.")

    payload: dict[str, list[str]] = {}
    if keys:
        payload["keys"] = keys
    if key_aliases:
        payload["key_aliases"] = key_aliases

    response = requests.post(
        f"{ASCS_API_BASE_URL}/key/delete",
        json=payload,
        headers=_headers(),
        timeout=ASCS_API_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def update_team(payload: dict[str, Any]) -> str:
    response = requests.post(
        f"{ASCS_API_BASE_URL}/team/update",
        json=payload,
        headers=_headers(),
        timeout=ASCS_API_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()
```

---

## 9. Items To Confirm Before Production Use

- Required authentication method.
- Whether `POST` is the correct method for all endpoints.
- Whether generated `token` and `key` fields differ in usage.
- Whether `/key/update` returns only a string or a structured object in all cases.
- Whether `/key/delete` returns a string or a structured object containing `deleted_keys`.
- Whether deleted keys can be recovered.
- Whether blocked keys can be restored.
- Whether updated team limits apply immediately to existing keys or only to newly generated/updated keys.
- Team TPM/RPM limit inheritance behavior.
- Team budget override behavior when key-level limits are also configured.
- Actual model list available in production.
- Rate limit and budget semantics.
