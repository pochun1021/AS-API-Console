# External API Integration Document

> Source domain: `api.ascs.sinica.edu.tw`  
> Purpose: API key management for AI API service  
> Default model: `["gemma-4-31B-it"]`  
> Default key type: `AI API`

---

## 1. Overview

This document describes the external API endpoints used for API key management.
It is intended for project maintenance, API integration review, and Codex-assisted development.

### Base URL

```text
https://api.ascs.sinica.edu.tw
```

### Common Notes

- All endpoints are related to API key lifecycle management.
- Request and response examples are based on the provided external API specification.
- Sensitive fields such as `key`, `token`, and generated API keys must not be logged in plaintext.
- Recommended timeout: define explicitly in application code, for example `30s`.
- Authentication method was not specified in the source file. Confirm whether these management APIs require Bearer Token, API Key, or another authorization mechanism before implementation.

---

## 2. Endpoint Summary

| Endpoint | Method | Purpose |
|---|---:|---|
| `/key/generate` | `POST` | Generate a new API key based on provided configuration. |
| `/key/update` | `POST` | Update parameters of an existing API key. |
| `/key/regenerate` | `POST` | Regenerate an existing API key and optionally update parameters. |
| `/key/block` | `POST` | Block a virtual key from making further requests. |

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
30d  # 30 days
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
| `duration` | `string` | No | Token validity duration. Example: `30s`, `30m`, `30h`, `30d`. |
| `key_alias` | `string` | No | User-defined key alias. |
| `models` | `array` | No | Model names the user is allowed to call. If empty, the key can call all models. |
| `max_budget` | `float` | No | Maximum budget for the generated key. |
| `rpm_limit` | `integer` | No | Requests per minute limit. |
| `tpm_limit` | `integer` | No | Tokens per minute limit. |
| `budget_duration` | `string` | No | Budget reset duration. If not set, budget is never reset. |
| `key_type` | `string` | No | Key type that determines default allowed routes. Options: `llm_api`, `management`, `read_only`, `default`. Defaults to `default`. |

### Request Body Example

```json
{
  "key_alias": "string",
  "duration": "string",
  "models": [],
  "max_budget": 0,
  "tpm_limit": 0,
  "rpm_limit": 0,
  "budget_duration": "string",
  "key_type": "default"
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

## 4.3 Regenerate API Key

### Endpoint

```http
POST /key/regenerate
```

### Description

Regenerate an existing API key while optionally updating its parameters.

### Request Parameters

| Field | Type | Required | Description |
|---|---|---:|---|
| `key` | `string` | Yes | Existing key to regenerate. The source file describes this as a path parameter. Confirm actual route format before implementation. |
| `models` | `array` | No | Model names the user is allowed to call. |
| `key_alias` | `string` | No | User-friendly key alias. |
| `max_budget` | `float` | No | Maximum budget for the key. |
| `budget_duration` | `string` | No | Budget reset period. Example: `30d`, `1h`. |
| `tpm_limit` | `integer` | No | Tokens per minute limit. |
| `rpm_limit` | `integer` | No | Requests per minute limit. |
| `duration` | `string` | No | Key validity duration. Example: `30d`, `1h`. |

### Request Body Example

```json
{
  "key_alias": "string",
  "duration": "string",
  "models": [],
  "max_budget": 0,
  "tpm_limit": 0,
  "rpm_limit": 0,
  "budget_duration": "string"
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
      "reset_at": "2026-06-02T08:03:28.049Z"
    }
  ],
  "blocked": true,
  "key": "string",
  "budget_id": "string",
  "key_name": "string",
  "expires": "2026-06-02T08:03:28.049Z",
  "token_id": "string",
  "organization_id": "string",
  "project_id": "string",
  "token": "string",
  "created_by": "string",
  "updated_by": "string",
  "created_at": "2026-06-02T08:03:28.049Z",
  "updated_at": "2026-06-02T08:03:28.049Z"
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

- Regeneration may invalidate the original key. Confirm behavior before use in production.
- Apply key rotation carefully to avoid service interruption.
- Store the new key/token securely after successful regeneration.

---

## 4.4 Block API Key

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

- Use this endpoint when a key is compromised, retired, or no longer authorized.
- Confirm whether blocked keys can be unblocked through another endpoint.
- Log only masked key identifiers.

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

- Do not commit API keys, tokens, or generated secrets to Git.
- Use environment variables or a secret manager.
- Mask secrets in application logs.
- Avoid returning management API secrets to frontend unless absolutely necessary.
- Restrict access to management endpoints in backend services.
- Define timeout, retry, and failure handling explicitly.
- Add audit logs for key generation, update, regeneration, and blocking events.

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
import requests

ASCS_API_BASE_URL = os.getenv("ASCS_API_BASE_URL", "https://api.ascs.sinica.edu.tw")
ASCS_API_TIMEOUT_SECONDS = int(os.getenv("ASCS_API_TIMEOUT_SECONDS", "30"))
ASCS_API_AUTH_TOKEN = os.getenv("ASCS_API_AUTH_TOKEN")


def _headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if ASCS_API_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {ASCS_API_AUTH_TOKEN}"
    return headers


def generate_key(payload: dict) -> dict:
    response = requests.post(
        f"{ASCS_API_BASE_URL}/key/generate",
        json=payload,
        headers=_headers(),
        timeout=ASCS_API_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def update_key(payload: dict) -> str:
    response = requests.post(
        f"{ASCS_API_BASE_URL}/key/update",
        json=payload,
        headers=_headers(),
        timeout=ASCS_API_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def regenerate_key(payload: dict) -> dict:
    response = requests.post(
        f"{ASCS_API_BASE_URL}/key/regenerate",
        json=payload,
        headers=_headers(),
        timeout=ASCS_API_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def block_key(key: str) -> dict:
    response = requests.post(
        f"{ASCS_API_BASE_URL}/key/block",
        json={"key": key},
        headers=_headers(),
        timeout=ASCS_API_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()
```

---

## 9. Items To Confirm Before Production Use

- Required authentication method.
- Whether `/key/regenerate` expects `key` in request body, query parameter, or path parameter.
- Whether `POST` is the correct method for all endpoints.
- Whether generated `token` and `key` fields differ in usage.
- Whether `/key/update` returns only a string or a structured object in all cases.
- Whether blocked keys can be restored.
- Actual model list available in production.
- Rate limit and budget semantics.
