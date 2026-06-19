# External API Integration Document

> Source domain: `api.ascs.sinica.edu.tw`
> Purpose: API key management, model listing, spend log query, and team key bulk update for AI API service
> Repo key type: `llm_api`

## Endpoint Summary

| Endpoint | Method |
|----------|---------|
| `/models` | GET |
| `/spend/keys` | GET |
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

# /spend/keys

Current reset-cycle summary query.

用途：
- 提供單把 key 在目前 reset 週期內的 summary 資訊
- 本系統用於同步 `usage_summary.spend` 與 reset window metadata

常見欄位：
- `token`
- `key_alias`
- `team_id`
- `spend`
- `budget_duration`
- `budget_reset_at`
- `tpm_limit`
- `rpm_limit`
- `max_parallel_requests`
- `updated_at`

本系統使用方式：
- 以 `token` 優先對應本地 `api_keys.key_hash`
- 若 `token` 無法對應，再以 `key_alias` 作為輔助比對
- `spend` 直接作為 current-cycle spend
- `budget_reset_at` 直接視為「下一次重置時間」，不做本地推算或 rollover
- `updated_at` 優先映射為本地 `usage_summary.synced_at`

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

常見 record 欄位：
- `api_key`
- `status`
- `spend`
- `prompt_tokens`
- `completion_tokens`
- `total_tokens`
- `startTime`
- `endTime`
- `metadata.user_api_key_alias`

本系統使用方式：
- 以 `api_key` 作為主要查詢鍵，對應本地 `api_keys.key_hash`
- 僅累計 `status=success` 的紀錄
- `prompt_tokens`、`completion_tokens`、`total_tokens` 由目前 reset window 內的 logs 聚合得出
- `startTime` 作為 current-cycle 篩選依據
- 每日歷史 bucket 仍以 `Asia/Taipei` 日曆日聚合後寫入本地 `api_key_usage_snapshots`

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
