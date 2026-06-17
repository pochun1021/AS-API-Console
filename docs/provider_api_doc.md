# External API Integration Document

> Source domain: `api.ascs.sinica.edu.tw`
> Purpose: API key management, model listing, spend log query, and team key bulk update for AI API service
> Repo key type: `llm_api`

## Endpoint Summary

| Endpoint | Method |
|----------|---------|
| `/models` | GET |
| `/spend/logs/v2` | GET |
| `/key/generate` | POST |
| `/key/update` | POST |
| `/key/delete` | POST |
| `/team/key/bulk_update` | POST |

---

# /models

OpenAI-compatible model discovery endpoint.

Query parameters:
- include_metadata
- fallback_type
- scope
- team_id
- return_wildcard_routes
- include_model_access_groups
- only_model_access_groups

Response:
- HTTP 200
- HTTP 422 validation error

---

# /spend/logs/v2

Paginated spend log query.

Supported filters:
- api_key
- user_id
- request_id
- team_id
- min_spend
- max_spend
- start_date
- end_date
- page
- page_size
- status_filter
- model
- model_id
- key_alias
- end_user
- error_code
- error_message
- sort_by
- sort_order

Response contains:

```json
{
  "data": [],
  "total": 0,
  "page": 1,
  "page_size": 50,
  "total_pages": 0
}
```

---

# /key/generate

Generate API Key.

Parameters:

- team_id
- key_alias
- duration
- max_budget
- budget_duration
- tpm_limit
- rpm_limit
- max_parallel_requests
- key_type

Example:

```json
{
  "team_id": "team_123",
  "key_alias": "research-key",
  "duration": "30d",
  "max_budget": 100,
  "budget_duration": "30d",
  "tpm_limit": 100000,
  "rpm_limit": 100,
  "max_parallel_requests": 5,
  "key_type": "llm_api"
}
```

Notes:

- `max_parallel_requests` limits concurrent requests.
- Exceeding the limit may return HTTP 429.
- Omit `models` field.
- Use `key_type=llm_api`.

---

# /key/update

Update an existing key.

Parameters:

- key
- key_alias
- duration
- max_budget
- budget_duration
- tpm_limit
- rpm_limit

Example:

```json
{
  "key": "sk-xxxxx",
  "duration": "180d"
}
```

---

# /key/delete

Delete keys from the key management system.

Request:

```json
{
  "keys": [
    "sk-xxxxx"
  ]
}
```

or

```json
{
  "key_aliases": [
    "alias1"
  ]
}
```

Response:

```json
{
  "deleted_keys": [
    "sk-xxxxx"
  ]
}
```

---

# /team/key/bulk_update

Bulk update keys inside a team.

Request:

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

Supported update fields:

- max_budget
- budget_duration
- tpm_limit
- rpm_limit
- max_parallel_requests

Response:

```json
{
  "total_requested": 0,
  "successful_updates": [],
  "failed_updates": []
}
```

---

## Key Lifecycle

```text
Create Key  -> /key/generate
Update Key  -> /key/update
Delete Key  -> /key/delete

Team Bulk Management
-> /team/key/bulk_update
```

## Removed APIs

This document intentionally excludes:

- /key/block
- /team/update
