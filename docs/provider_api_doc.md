# External API Integration Document

> Source domain: `api.ascs.sinica.edu.tw`  
> Purpose: API key management, model listing, spend log query, and team key bulk update for AI API service  
> Repo integration contract: no `/team/update`; team quota management is handled through `/team/key/bulk_update`  
> Repo key type: `llm_api`

---

## 1. Overview

This document describes the external API endpoints used by this project.
It is intended for project maintenance, API integration review, and Codex-assisted development.

### Base URL

```text
https://api.ascs.sinica.edu.tw
```

### Common Notes

- All management APIs should be called from backend services only.
- Sensitive fields such as `key`, `token`, generated API keys, and API key hashes must not be logged in plaintext.
- Recommended timeout: define explicitly in application code, for example `30s`.
- Authentication method was not specified in the source material. Confirm whether these management APIs require Bearer Token, API Key, or another authorization mechanism before implementation.
- This project does not use `/team/update`.
- Team-level key management is performed through `/team/key/bulk_update`.

---

## 2. Endpoint Summary

| Endpoint | Method | Purpose |
|---|---:|---|
| `/models` | `GET` | List available models. Compatible with OpenAI-style projects such as Aider. |
| `/spend/logs/v2` | `GET` | Retrieve paginated spend logs with filtering and sorting support. |
| `/key/generate` | `POST` | Generate a new API key based on provided configuration. |
| `/key/update` | `POST` | Update parameters of an existing API key. |
| `/key/block` | `POST` | Block a virtual key from making further requests. |
| `/key/delete` | `POST` | Delete one or more API keys from the key management system. |
| `/team/key/bulk_update` | `POST` | Apply one update payload to multiple keys within a team. |

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

## 4.1 List Models

### Endpoint

```http
GET /models
```

### Description

List available models.

This endpoint exists for compatibility with OpenAI-style projects such as Aider.

### Query Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---:|---|---|
| `return_wildcard_routes` | `boolean` | No | `false` | Whether to return wildcard routes. |
| `team_id` | `string` | No | `null` | Filter or resolve available models for a specific team. |
| `include_model_access_groups` | `boolean` | No | `false` | Include model access group information. |
| `only_model_access_groups` | `boolean` | No | `false` | Return only model access group data. |
| `include_metadata` | `boolean` | No | `false` | Include additional metadata in the response with fallback information. |
| `fallback_type` | `string` | No | `general` when `include_metadata=true` | Type of fallback metadata to include. Options include `general`, `context_window`, `content_policy`. |
| `scope` | `string` | No | `null` | Optional scope parameter. Currently accepts `expand`. When `scope=expand`, proxy admins, team admins, and org admins receive all proxy models as if they are proxy admins. |

### Example Request

```http
GET /models
```

### Example Request With Metadata

```http
GET /models?include_metadata=true&fallback_type=general
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

- Use this endpoint to populate model dropdowns or verify available models.
- For Aider/OpenAI-compatible tooling, this endpoint should be treated as the model discovery endpoint.
- When team-specific visibility matters, pass `team_id`.
- Avoid hardcoding model lists when this endpoint is available.

---

## 4.2 Get Spend Logs

### Endpoint

```http
GET /spend/logs/v2
```

### Description

Returns paginated spend log records with filtering, sorting, and pagination support.

The response contains:

- `data`
- `total`
- `page`
- `page_size`
- `total_pages`

Useful for:

- API usage monitoring
- Cost analysis
- User usage tracking
- Team usage tracking
- Error investigation
- Model usage statistics

### Query Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---:|---|---|
| `api_key` | `string` | No | `null` | Get spend logs based on API key. |
| `user_id` | `string` | No | `null` | Get spend logs based on user ID. |
| `request_id` | `string` | No | `null` | Get spend logs for a specific request ID. |
| `team_id` | `string` | No | `null` | Filter spend logs by team ID. |
| `min_spend` | `number` | No | `null` | Filter logs with spend greater than or equal to this value. |
| `max_spend` | `number` | No | `null` | Filter logs with spend less than or equal to this value. |
| `start_date` | `string` | No | `null` | Time from which to start viewing key spend. |
| `end_date` | `string` | No | `null` | Time until which to view key spend. |
| `page` | `integer` | No | `1` | Page number for pagination. Minimum: `1`. |
| `page_size` | `integer` | No | `50` | Number of items per page. Minimum: `1`, maximum: `100`. |
| `status_filter` | `string` | No | `null` | Filter logs by status, for example `success` or `failure`. |
| `model` | `string` | No | `null` | Filter logs by model. |
| `model_id` | `string` | No | `null` | Filter logs by model ID, also known as LiteLLM model deployment ID. |
| `key_alias` | `string` | No | `null` | Filter logs by key alias. |
| `end_user` | `string` | No | `null` | Filter logs by end user. |
| `error_code` | `string` | No | `null` | Filter logs by error code, for example `404` or `500`. |
| `error_message` | `string` | No | `null` | Filter logs by error message using partial string match. |
| `sort_by` | `string` | No | `startTime` | Sort field. Options: `spend`, `total_tokens`, `startTime`, `endTime`, `request_duration_ms`, `model`, `ttft_ms`. |
| `sort_order` | `string` | No | `desc` | Sort order. Options: `asc`, `desc`. |

### Example Request

```http
GET /spend/logs/v2?team_id=team_123&page=1&page_size=50
```

### Example Request By Key Alias

```http
GET /spend/logs/v2?key_alias=test-key&start_date=2026-06-01&end_date=2026-06-30
```

### Success Response

#### HTTP 200

```json
{
  "data": [],
  "total": 0,
  "page": 1,
  "page_size": 50,
  "total_pages": 0
}
```

### Response Fields

| Field | Type | Description |
|---|---|---|
| `data` | `array` | Spend log records. |
| `total` | `integer` | Total record count. |
| `page` | `integer` | Current page number. |
| `page_size` | `integer` | Number of records per page. |
| `total_pages` | `integer` | Total number of pages. |

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

- Use pagination when displaying usage history.
- Team administrators should filter using `team_id`.
- Key-level usage can be queried using `api_key` or `key_alias`.
- Support cost reporting by combining `start_date`, `end_date`, and `team_id`.
- Recommended default sorting:

```text
sort_by=startTime
sort_order=desc
```

---

## 4.3 Generate API Key

### Endpoint

```http
POST /key/generate
```

### Description

Generate an API key based on the provided data.

### Request Parameters

| Field | Type | Required | Description |
|---|---|---:|---|
| `team_id` | `string` | No | Team ID to associate with the generated API key. |
| `duration` | `string` | No | Token validity duration. Example: `30s`, `30m`, `30h`, `30d`. |
| `key_alias` | `string` | No | User-defined key alias. |
| `max_budget` | `float` | No | Maximum budget for the generated key. |
| `rpm_limit` | `integer` | No | Requests per minute limit. |
| `tpm_limit` | `integer` | No | Tokens per minute limit. |
| `max_parallel_requests` | `integer` | No | Rate limit a user based on the number of parallel requests. Raises HTTP `429` if the user's parallel requests exceed this value. |
| `budget_duration` | `string` | No | Budget reset duration. If not set, budget is never reset. |
| `key_type` | `string` | No | Key type that determines default allowed routes. Options: `llm_api`, `management`, `read_only`, `default`. Defaults to `default`. This repo sends `llm_api`. |

### Request Body Example

```json
{
  "team_id": "team_123",
  "key_alias": "my-api-key",
  "duration": "30d",
  "max_budget": 100,
  "tpm_limit": 50000,
  "rpm_limit": 500,
  "max_parallel_requests": 10,
  "budget_duration": "30d",
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
- This repo does not send the `models` field when generating keys.
- This repo sends `key_type=llm_api`.
- `team_id` should be supplied when creating team-owned keys.
- `max_parallel_requests` controls concurrent request limits and is separate from RPM and TPM.

---

## 4.4 Update API Key

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

## 4.5 Block API Key

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
- Confirm whether blocked keys can be restored through another endpoint.
- Log only masked key identifiers.

---

## 4.6 Delete API Key

### Endpoint

```http
POST /key/delete
```

### Description

Delete one or more keys from the key management system.

Keys can be deleted by raw key, hashed key, or key alias.

### Request Parameters

| Field | Type | Required | Description |
|---|---|---:|---|
| `keys` | `array[string]` | No | List of keys or hashed keys to delete. |
| `key_aliases` | `array[string]` | No | List of key aliases to delete. Can be passed instead of `keys`. |

### Rules

At least one of the following should be provided:

```text
keys
```

or

```text
key_aliases
```

### Request Body Example By Keys

```json
{
  "keys": [
    "sk-QWrxEynunsNpV1zT48HIrw",
    "837e17519f44683334df5291321d97b8bf1098cd490e49e215f6fea935aa28be"
  ]
}
```

### Request Body Example By Aliases

```json
{
  "key_aliases": [
    "alias1",
    "alias2"
  ]
}
```

### Request Body Schema

```json
{
  "keys": [
    "string"
  ],
  "key_aliases": [
    "string"
  ]
}
```

### Success Response

#### HTTP 200

```json
"string"
```

### Documented Return Shape

The API may return deleted key information in the following shape:

```json
{
  "deleted_keys": [
    "sk-QWrxEynunsNpV1zT48HIrw",
    "837e17519f44683334df5291321d97b8bf1098cd490e49e215f6fea935aa28be"
  ]
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

- Deleting a key is more destructive than blocking a key.
- Prefer `/key/block` when temporary deactivation is enough.
- Use `/key/delete` when a key should be removed from the key management system.
- Confirm whether deleted keys can be recovered before exposing this operation to administrators.
- Mask keys in logs.

---

## 4.7 Bulk Update Team Keys

### Endpoint

```http
POST /team/key/bulk_update
```

### Description

Apply one update payload to many keys inside a single team.

Pass `team_id` plus either `key_ids` or `all_keys_in_team=true`.
The `update_fields` payload is broadcast to every selected key.
Per-key failures are returned in `failed_updates` rather than aborting the batch.

This endpoint is useful when:

- Updating TPM/RPM limits for all team keys
- Applying budget changes across a team
- Enforcing new concurrency limits
- Managing large numbers of keys without updating them individually

### Permissions

Callable by:

- Proxy admins
- Team admins with `KEY_UPDATE` permission

### Request Parameters

| Field | Type | Required | Description |
|---|---|---:|---|
| `team_id` | `string` | Yes | Team ID containing the target keys. |
| `all_keys_in_team` | `boolean` | No | Apply updates to all keys in the team. |
| `key_ids` | `array[string]` | No | Specific key IDs to update. |
| `update_fields` | `object` | Yes | Configuration to apply to all selected keys. |

### Rules

One of the following must be provided:

```text
team_id + key_ids
```

or

```text
team_id + all_keys_in_team=true
```

### Update Fields

| Field | Type | Description |
|---|---|---|
| `max_budget` | `float` | Maximum budget allowed for each selected key. |
| `budget_duration` | `string` | Budget reset interval. |
| `tpm_limit` | `integer` | Tokens per minute limit. |
| `rpm_limit` | `integer` | Requests per minute limit. |
| `max_parallel_requests` | `integer` | Maximum concurrent requests allowed. |

### Request Body Example

```json
{
  "team_id": "string",
  "all_keys_in_team": false,
  "update_fields": {
    "max_budget": 0,
    "budget_duration": "string",
    "tpm_limit": 0,
    "rpm_limit": 0,
    "max_parallel_requests": 0
  }
}
```

### Request Body Example: Update All Keys

```json
{
  "team_id": "team_123",
  "all_keys_in_team": true,
  "update_fields": {
    "max_budget": 100,
    "budget_duration": "30d",
    "tpm_limit": 50000,
    "rpm_limit": 500,
    "max_parallel_requests": 10
  }
}
```

### Request Body Example: Selected Keys

```json
{
  "team_id": "team_123",
  "key_ids": [
    "key_001",
    "key_002"
  ],
  "update_fields": {
    "tpm_limit": 10000,
    "rpm_limit": 100,
    "max_parallel_requests": 5
  }
}
```

### Success Response

#### HTTP 200

```json
{
  "total_requested": 0,
  "successful_updates": [
    {
      "key": "string",
      "key_info": {
        "additionalProp1": {}
      }
    }
  ],
  "failed_updates": [
    {
      "key": "string",
      "key_info": {
        "additionalProp1": {}
      },
      "failed_reason": "string"
    }
  ]
}
```

### Response Fields

| Field | Type | Description |
|---|---|---|
| `total_requested` | `integer` | Total number of keys requested for update. |
| `successful_updates` | `array` | Keys successfully updated. |
| `failed_updates` | `array` | Keys that failed update. |
| `failed_reason` | `string` | Failure reason for a specific key. |

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

- Partial success is supported.
- A failure on one key does not stop updates to other keys.
- Always inspect `failed_updates` after execution.
- Use this endpoint for team-wide quota enforcement.
- Recommended for bulk administrative operations instead of multiple `/key/update` calls.
- This project uses this endpoint instead of `/team/update`.

---

## 5. API Grouping

### Model APIs

| Endpoint | Purpose |
|---|---|
| `/models` | Get available models. |

### Spend Management APIs

| Endpoint | Purpose |
|---|---|
| `/spend/logs/v2` | Query usage and spend history. |

### Key Management APIs

| Endpoint | Purpose |
|---|---|
| `/key/generate` | Create a new key. |
| `/key/update` | Update a single key. |
| `/key/block` | Disable a key from making requests. |
| `/key/delete` | Delete one or more keys. |

### Team Key Management APIs

| Endpoint | Purpose |
|---|---|
| `/team/key/bulk_update` | Update TPM/RPM/Budget/Concurrency settings for multiple keys within a team. |

---

## 6. Error Handling

| HTTP Status | Meaning | Recommended Handling |
|---:|---|---|
| `200` | Success | Parse response body and update local state. |
| `422` | Validation error | Check request body fields, query parameters, types, and required values. Surface a clear error message to backend logs. |
| `429` | Rate limit exceeded | Can occur when RPM/TPM/concurrency limits are exceeded. Display a rate limit message and retry later if appropriate. |

### Standard Validation Error Shape

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

## 7. Security Checklist

- Do not commit API keys, tokens, or generated secrets to Git.
- Use environment variables or a secret manager.
- Mask secrets in application logs.
- Avoid returning management API secrets to frontend unless absolutely necessary.
- Restrict access to management endpoints in backend services.
- Define timeout, retry, and failure handling explicitly.
- Add audit logs for key generation, update, blocking, deletion, and bulk update events.
- Treat `/key/delete` as a destructive operation.
- Inspect `failed_updates` after `/team/key/bulk_update`.

---

## 8. Suggested Backend Environment Variables

```env
ASCS_API_BASE_URL=https://api.ascs.sinica.edu.tw
ASCS_API_TIMEOUT_SECONDS=30
ASCS_API_AUTH_TOKEN=<set-in-secret-manager>
```

---

## 9. Suggested Python Client Skeleton

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


def list_models(params: dict[str, Any] | None = None) -> Any:
    response = requests.get(
        f"{ASCS_API_BASE_URL}/models",
        params=params,
        headers=_headers(),
        timeout=ASCS_API_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def get_spend_logs_v2(params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.get(
        f"{ASCS_API_BASE_URL}/spend/logs/v2",
        params=params,
        headers=_headers(),
        timeout=ASCS_API_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


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
    payload: dict[str, Any] = {}

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


def bulk_update_team_keys(payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        f"{ASCS_API_BASE_URL}/team/key/bulk_update",
        json=payload,
        headers=_headers(),
        timeout=ASCS_API_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()
```

---

## 10. Items To Confirm Before Production Use

- Required authentication method.
- Whether `POST` is the correct method for all key and team-key endpoints.
- Whether generated `token` and `key` fields differ in usage.
- Whether `/key/update` returns only a string or a structured object in all cases.
- Whether deleted keys can be recovered.
- Whether blocked keys can be restored.
- Actual model list available in production.
- Rate limit and budget semantics.
- Whether `max_parallel_requests` applies per key, per user, or per key-user pair.
- Whether `/key/delete` returns a string or the documented `deleted_keys` object in production.
- Whether `/team/key/bulk_update` requires `key_ids`, `all_keys_in_team=true`, or supports both exactly as documented.
