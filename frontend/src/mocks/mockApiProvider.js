import { containsOnlyAllowedPersistedTextCharacters, containsUnsafePersistedText, isAsciiDigits } from "../utils/inputValidation";

const today = new Date().toISOString().slice(0, 10);
const daysFromNow = (days) => new Date(Date.now() + 1000 * 60 * 60 * 24 * days).toISOString();
const MS_PER_DAY = 1000 * 60 * 60 * 24;

function startOfUtcDay(value) {
  const dt = value instanceof Date ? new Date(value) : new Date(value);
  return new Date(Date.UTC(dt.getUTCFullYear(), dt.getUTCMonth(), dt.getUTCDate()));
}

function expiresAtFromApplicationDate(applicationDate, durationDays) {
  const expires = startOfUtcDay(`${applicationDate}T00:00:00.000Z`);
  expires.setUTCDate(expires.getUTCDate() + durationDays);
  return expires.toISOString();
}

const mockInstitutes = [
  { inst_code: "01", inst_name: "院本部", abb_inst_name: "院本部", einst_name: "Headquarters", division: "1" },
  { inst_code: "02", inst_name: "資訊所", abb_inst_name: "資訊所", einst_name: "Institute of Information Science", division: "2" },
  { inst_code: "03", inst_name: "資安中心", abb_inst_name: "資安", einst_name: "Security Center", division: "2" },
  { inst_code: "04", inst_name: "資料平台", abb_inst_name: "資料平台", einst_name: "Data Platform", division: "2" },
  { inst_code: "05", inst_name: "營運處", abb_inst_name: "營運處", einst_name: "Operations", division: "3" }
];
const initialModelsPayload = {
  data: [
    {
      id: "gpt-4o",
      object: "model",
      created: 1677610602,
      owned_by: "openai"
    },
    {
      id: "gpt-4o-mini",
      object: "model",
      created: 1677610602,
      owned_by: "openai"
    }
  ],
  object: "list"
};
const initialUsageSeries = [
  {
    key_id: "key_002",
    granularity: "day",
    bucket_start: "2026-06-01T00:00:00+08:00",
    bucket_label: "2026-06-01",
    prompt_tokens: 1000,
    completion_tokens: 500,
    total_tokens: 1500,
    spend: 1.25
  },
  {
    key_id: "key_002",
    granularity: "day",
    bucket_start: "2026-06-02T00:00:00+08:00",
    bucket_label: "2026-06-02",
    prompt_tokens: 800,
    completion_tokens: 400,
    total_tokens: 1200,
    spend: 0.95
  },
  {
    key_id: "key_003",
    granularity: "day",
    bucket_start: "2026-06-01T00:00:00+08:00",
    bucket_label: "2026-06-01",
    prompt_tokens: 600,
    completion_tokens: 300,
    total_tokens: 900,
    spend: 0.55
  }
];

const initialApiKeys = [
  {
    id: "key_001",
    status: "active",
    masked_key: "AS-...xy90",
    application_date: today,
    duration_days: 180,
    purpose: "integration test for platform service",
    department: "02",
    created_at: "2026-06-04T09:00:00.000Z",
    expires_at: daysFromNow(14),
    expiration_notice_sent_at: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
    max_budget: "1000",
    tpm_limit: 10000,
    rpm_limit: 500,
    max_parallel_requests: 8,
    usage_spend: null,
    usage_prompt_tokens: null,
    usage_completion_tokens: null,
    usage_total_tokens: null,
    usage_budget_reset_at: null,
    usage_synced_at: null,
    owner_account: "jane.doe",
    owner_name: "Jane Doe",
    renewed_to_key_id: null
  },
  {
    id: "key_002",
    status: "revoked",
    masked_key: "AS-...mn56",
    key_alias: "shared_alias",
    application_date: today,
    duration_days: 30,
    purpose: "legacy integration",
    department: "02",
    created_at: "2026-06-03T09:00:00.000Z",
    expires_at: new Date(Date.now() + 1000 * 60 * 60 * 24 * 30).toISOString(),
    expiration_notice_sent_at: null,
    max_budget: "1000",
    tpm_limit: 10000,
    rpm_limit: 500,
    max_parallel_requests: 8,
    usage_spend: 850.25,
    usage_prompt_tokens: 1000,
    usage_completion_tokens: 500,
    usage_total_tokens: 1500,
    usage_budget_reset_at: "2026-06-02T08:03:27.000Z",
    usage_synced_at: "2026-06-02T08:03:27.000Z",
    owner_account: "jane.doe",
    owner_name: "Jane Doe",
    renewed_to_key_id: null
  },
  {
    id: "key_003",
    status: "active",
    masked_key: "AS-...ab12",
    application_date: today,
    duration_days: 360,
    purpose: "admin automation",
    department: "03",
    created_at: "2026-06-02T09:00:00.000Z",
    expires_at: new Date(Date.now() + 1000 * 60 * 60 * 24 * 360).toISOString(),
    expiration_notice_sent_at: null,
    max_budget: "0",
    tpm_limit: 0,
    rpm_limit: 0,
    max_parallel_requests: 0,
    usage_spend: 9999.99,
    usage_budget_reset_at: null,
    usage_synced_at: "2026-06-02T08:03:27.000Z",
    owner_account: "john.admin",
    owner_name: "John Admin",
    renewed_to_key_id: null
  },
  {
    id: "key_004",
    status: "expired",
    masked_key: "AS-...pq78",
    application_date: "2025-04-01",
    duration_days: 30,
    created_at: "2025-04-01T08:00:00.000Z",
    expires_at: "2025-05-01T08:00:00.000Z",
    expiration_notice_sent_at: "2025-04-01T08:00:00.000Z",
    owner_account: "john.admin",
    owner_name: "John Admin",
    renewed_to_key_id: null
  },
  {
    id: "key_005",
    status: "active",
    masked_key: "AS-...cd34",
    application_date: "2026-04-15",
    duration_days: 180,
    purpose: "reporting service integration",
    department: "04",
    created_at: "2026-04-15T09:30:00.000Z",
    expires_at: "2026-10-15T09:30:00.000Z",
    expiration_notice_sent_at: null,
    owner_account: "alice.wang",
    owner_name: "Alice Wang",
    renewed_to_key_id: null
  },
  {
    id: "key_005b",
    status: "active",
    masked_key: "AS-...kt01",
    application_date: "2026-04-20",
    duration_days: 180,
    purpose: "cross page search demo",
    department: "02",
    created_at: "2026-04-20T03:00:00.000Z",
    expires_at: "2026-10-20T03:00:00.000Z",
    expiration_notice_sent_at: null,
    owner_account: "ktu",
    owner_name: "尤凱婷",
    renewed_to_key_id: null
  },
  {
    id: "key_006",
    status: "revoked",
    masked_key: "AS-...ef56",
    application_date: "2026-03-10",
    duration_days: 360,
    purpose: "security scanner",
    department: "03",
    created_at: "2026-03-10T02:20:00.000Z",
    expires_at: "2027-03-10T02:20:00.000Z",
    expiration_notice_sent_at: null,
    owner_account: "sam.chen",
    owner_name: "Sam Chen",
    renewed_to_key_id: null
  },
  {
    id: "key_007",
    status: "expired",
    masked_key: "AS-...gh78",
    application_date: "2025-12-01",
    duration_days: 30,
    purpose: "legacy webhook client",
    department: "05",
    created_at: "2025-12-01T05:00:00.000Z",
    expires_at: "2026-01-01T05:00:00.000Z",
    expiration_notice_sent_at: "2025-12-01T05:00:00.000Z",
    owner_account: "mike.li",
    owner_name: "Mike Li",
    renewed_to_key_id: null
  },
  {
    id: "key_008",
    status: "active",
    masked_key: "AS-...du01",
    application_date: "2026-05-01",
    duration_days: 180,
    purpose: "dev.user local integration test",
    department: "02",
    created_at: "2026-05-04T02:15:00.000Z",
    expires_at: daysFromNow(45),
    expiration_notice_sent_at: null,
    owner_account: "dev.user",
    owner_name: "Dev User",
    renewed_to_key_id: null
  },
  {
    id: "key_009",
    status: "revoked",
    masked_key: "AS-...du02",
    application_date: "2026-04-18",
    duration_days: 30,
    purpose: "dev.user revoke flow test",
    department: "02",
    created_at: "2026-05-03T07:20:00.000Z",
    expires_at: "2026-05-18T07:20:00.000Z",
    expiration_notice_sent_at: null,
    owner_account: "dev.user",
    owner_name: "Dev User",
    renewed_to_key_id: null
  },
  {
    id: "key_010",
    status: "expired",
    masked_key: "AS-...du03",
    application_date: "2026-02-10",
    duration_days: 30,
    purpose: "dev.user expiry scenario",
    department: "02",
    created_at: "2026-05-02T11:00:00.000Z",
    expires_at: "2026-03-10T11:00:00.000Z",
    expiration_notice_sent_at: null,
    owner_account: "dev.user",
    owner_name: "Dev User",
    renewed_to_key_id: null
  },
  {
    id: "key_011",
    status: "active",
    masked_key: "AS-...du04",
    application_date: today,
    duration_days: 30,
    purpose: "dev.user near expiry scenario",
    department: "02",
    created_at: "2026-05-01T09:00:00.000Z",
    expires_at: daysFromNow(14),
    expiration_notice_sent_at: null,
    owner_account: "dev.user",
    owner_name: "Dev User",
    renewed_to_key_id: null
  }
];

const initialWhitelists = [
  {
    id: "wl_001",
    email: "jane.doe@company.com",
    account: "jane.doe",
    sysid: 123,
    name: "Jane Doe",
    status: "active",
    note: "platform team",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  },
  {
    id: "wl_002",
    email: "legacy.user@company.com",
    account: "legacy.user",
    sysid: 999,
    name: "Legacy User",
    status: "inactive",
    note: "offboarded",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  },
  {
    id: "wl_003",
    email: "bob.lin@company.com",
    account: "bob.lin",
    sysid: 654,
    name: "Bob Lin",
    status: "active",
    note: "qa team",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  },
  {
    id: "wl_004",
    email: "sam.chen@company.com",
    account: "sam.chen",
    sysid: 789,
    name: "Sam Chen",
    status: "active",
    note: "secops automation",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  }
];

const initialAnnouncements = [
  {
    id: "ann_001",
    title: "平台維護公告",
    body: "本週三 18:00 進行例行維護，期間可能有短暫延遲。",
    status: "active",
    publish_from: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
    publish_to: new Date(Date.now() + 1000 * 60 * 60 * 24 * 7).toISOString(),
    created_at: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
    updated_at: new Date().toISOString()
  },
  {
    id: "ann_002",
    title: "草稿公告",
    body: "尚未啟用的公告",
    status: "inactive",
    publish_from: null,
    publish_to: null,
    created_at: new Date(Date.now() - 1000 * 60 * 60 * 48).toISOString(),
    updated_at: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString()
  }
];

const initialUsers = [
  {
    id: "usr_001",
    account: "jane.doe",
    sysid: 123,
    name: "Jane Doe",
    email: "jane.doe@company.com",
    role: "user",
    status: "active",
    preferred_locale: null
  },
  {
    id: "usr_002",
    account: "john.admin",
    sysid: 1,
    name: "John Admin",
    email: "john.admin@company.com",
    role: "admin",
    status: "active",
    preferred_locale: null
  },
  {
    id: "usr_003",
    account: "alice.wang",
    sysid: 456,
    name: "Alice Wang",
    email: "alice.wang@company.com",
    role: "user",
    status: "active",
    preferred_locale: null
  },
  {
    id: "usr_004",
    account: "sam.chen",
    sysid: 789,
    name: "Sam Chen",
    email: "sam.chen@company.com",
    role: "user",
    status: "active",
    preferred_locale: null
  },
  {
    id: "usr_005",
    account: "mike.li",
    sysid: 999,
    name: "Mike Li",
    email: "mike.li@company.com",
    role: "user",
    status: "active",
    preferred_locale: null
  }
];

let apiKeys = initialApiKeys.map((item) => ({ ...item }));
let whitelists = initialWhitelists.map((item) => ({ ...item }));
let announcements = initialAnnouncements.map((item) => ({ ...item }));
let users = initialUsers.map((item) => ({ ...item }));
let modelsPayload = {
  data: initialModelsPayload.data.map((item) => ({ ...item })),
  object: initialModelsPayload.object
};
let usageSeries = initialUsageSeries.map((item) => ({ ...item }));
let limitStrategyConfig = {
  budget_max_budget: "1000",
  budget_duration: "monthly",
  rate_limit_tpm: 10000,
  rate_limit_rpm: 500,
  max_parallel_requests: 0
};
let operationAuditLogs = [
  {
    id: "oplog_001",
    created_at: new Date().toISOString(),
    event_type: "api_key",
    action: "create",
    result: "success",
    actor_account: "john.admin",
    target_type: "api_key",
    target_id: "key_003",
    error_code: null,
    error_detail: null,
    request_id: "req-op-001"
  },
  {
    id: "oplog_002",
    created_at: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
    event_type: "whitelist",
    action: "update",
    result: "failure",
    actor_account: "john.admin",
    target_type: "whitelist",
    target_id: "wl_001",
    error_code: "VALIDATION_ERROR",
    error_detail: "status must be active or inactive",
    request_id: "req-op-002"
  }
];
let schedulerLogs = [
  {
    id: "schedlog_001",
    job: "sync_api_key_usage",
    log_date: "2026-06-17",
    source_file: "2026-06-17.log",
    timestamp: "2026-06-17T00:15:01+08:00",
    level: "ERROR",
    message: "event=usage_sync mode=sync processed_keys=10 success=8 failed=2",
    raw_line: "[2026-06-17T00:15:01+08:00] level=ERROR event=usage_sync mode=sync processed_keys=10 success=8 failed=2"
  },
  {
    id: "schedlog_002",
    job: "sync_api_key_usage",
    log_date: "2026-06-17",
    source_file: "2026-06-17.log",
    timestamp: "2026-06-17T00:05:01+08:00",
    level: "INFO",
    message: "event=usage_sync mode=sync processed_keys=10 success=9 failed=1",
    raw_line: "[2026-06-17T00:05:01+08:00] level=INFO event=usage_sync mode=sync processed_keys=10 success=9 failed=1"
  },
  {
    id: "schedlog_003",
    job: "send_expiration_reminders",
    log_date: "2026-06-16",
    source_file: "2026-06-16.log",
    timestamp: "2026-06-16T08:00:00+08:00",
    level: "WARNING",
    message: "event=expiration_notice sent=0 failed=1",
    raw_line: "[2026-06-16T08:00:00+08:00] level=WARNING event=expiration_notice sent=0 failed=1"
  }
];
let authAuditLogs = [
  {
    id: "authlog_001",
    created_at: new Date().toISOString(),
    provider: "sso",
    result: "success",
    account: "jane.doe",
    sysid: 123,
    role: "user",
    error_code: null,
    request_id: "req-auth-001"
  },
  {
    id: "authlog_002",
    created_at: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
    provider: "sso",
    result: "failure",
    account: null,
    sysid: null,
    role: null,
    error_code: "LOGIN_NOT_ELIGIBLE",
    request_id: "req-auth-002"
  }
];

function createError(code, message, status = 400) {
  const error = new Error(message);
  error.status = status;
  error.payload = { error: { code, message } };
  return error;
}

function delay(ms = 250) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function ensureAdmin(auth) {
  if (auth.role !== "admin") {
    throw createError("FORBIDDEN", "僅管理者可執行此操作", 403);
  }
}

function validateApplication(payload, auth) {
  if (![30, 180, 360].includes(payload.duration_days)) {
    throw createError("INVALID_DURATION_DAYS", "生效時長僅允許 30、180、360 天");
  }

  if (!/^\d{4}-\d{2}-\d{2}$/.test(payload.application_date) || payload.application_date > today) {
    throw createError("INVALID_APPLICATION_DATE", "申請日期格式需為 YYYY-MM-DD，且不可晚於今天");
  }

  if (!payload.purpose || !payload.purpose.trim()) {
    throw createError("VALIDATION_ERROR", "請填寫用途");
  }
  if (containsUnsafePersistedText(payload.purpose)) {
    throw createError("VALIDATION_ERROR", "purpose contains unsafe syntax", 422);
  }
  if (payload.target_identity?.account && containsUnsafePersistedText(payload.target_identity.account)) {
    throw createError("VALIDATION_ERROR", "target_identity.account contains unsafe syntax", 422);
  }

  const activeWhitelist = whitelists.find((item) => item.sysid === auth.sysid && item.status === "active");
  if (!activeWhitelist) {
    throw createError("APPLICANT_NOT_ELIGIBLE", "申請者不符合資格", 403);
  }
}

function generatePlainKey() {
  const keyPrefix = "AS-";
  const chars = "abcdefghijklmnopqrstuvwxyz0123456789";
  let randomPart = "";
  for (let i = 0; i < 30; i += 1) {
    randomPart += chars[Math.floor(Math.random() * chars.length)];
  }
  return `${keyPrefix}${randomPart}`;
}

function findApiKeyById(id) {
  return apiKeys.find((item) => item.id === id);
}

function findUserById(id) {
  return users.find((item) => item.id === id);
}

function findAnnouncementById(id) {
  return announcements.find((item) => item.id === id);
}

function normalizeAlias(item) {
  return item.key_alias || `for_${item.owner_account}`;
}

function resolveVersionedAlias(ownerAccount, currentAlias) {
  const normalizedAlias = (currentAlias || "").trim();
  if (!normalizedAlias) return `for_${ownerAccount}`;

  const matched = normalizedAlias.match(/^(.*)_v(\d+)$/);
  if (!matched) return `${normalizedAlias}_v2`;
  return `${matched[1]}_v${Number(matched[2]) + 1}`;
}

function ensureUniqueAlias(ownerAccount, preferredAlias) {
  let alias = (preferredAlias || "").trim() || `for_${ownerAccount}`;
  const seen = new Set(apiKeys.map((item) => normalizeAlias(item)).filter(Boolean));
  while (seen.has(alias)) {
    alias = resolveVersionedAlias(ownerAccount, alias);
  }
  return alias;
}

function isExtendEligible(item, auth) {
  return ["active", "expired"].includes(item.status);
}

function findOrCreateUserByAuth(auth) {
  let user = users.find((item) => item.account === auth.account);
  if (user) return user;

  user = {
    id: `usr_${String(users.length + 1).padStart(3, "0")}`,
    account: auth.account,
    sysid: auth.sysid,
    name: auth.name,
    email: auth.email,
    department: auth.department || "",
    role: auth.role || "user",
    status: "active",
    preferred_locale: null
  };
  users = [user, ...users];
  return user;
}

function mapUserForAdminPage(user) {
  return {
    id: user.id,
    account: user.account,
    sysid: user.sysid,
    name: user.name,
    email: user.email,
    department: user.department || "",
    status: user.status || "active",
    created_at: user.created_at || new Date().toISOString(),
    updated_at: user.updated_at || user.created_at || new Date().toISOString()
  };
}

function containsCI(value, keyword) {
  return String(value || "").toLowerCase().includes(String(keyword || "").trim().toLowerCase());
}

function normalizeAnnouncementPayload(payload) {
  const title = validatePersistedText(payload?.title, { required: true });
  if (!title.ok) {
    throw createError("VALIDATION_ERROR", title.reason === "unsafe" ? "title contains unsafe syntax" : "title is required", 422);
  }
  const body = validatePersistedText(payload?.body, { required: true });
  if (!body.ok) {
    throw createError("VALIDATION_ERROR", body.reason === "unsafe" ? "body contains unsafe syntax" : "body is required", 422);
  }
  if (!["active", "inactive"].includes(payload?.status)) {
    throw createError("VALIDATION_ERROR", "status must be active or inactive", 422);
  }
  const publishFrom = payload?.publish_from ? new Date(payload.publish_from).toISOString() : null;
  const publishTo = payload?.publish_to ? new Date(payload.publish_to).toISOString() : null;
  if (publishFrom && publishTo && new Date(publishFrom) > new Date(publishTo)) {
    throw createError("VALIDATION_ERROR", "publish_from must be less than or equal to publish_to", 422);
  }
  return {
    title: title.value,
    body: body.value,
    status: payload.status,
    publish_from: publishFrom,
    publish_to: publishTo
  };
}

function isAnnouncementVisible(item, now = new Date()) {
  if (item.status !== "active") return false;
  if (item.publish_from && new Date(item.publish_from) > now) return false;
  if (item.publish_to && new Date(item.publish_to) < now) return false;
  return true;
}

function compareValues(a, b, sortDir = "asc") {
  if (a === b) return 0;
  if (typeof a === "number" && typeof b === "number") {
    return sortDir === "asc" ? a - b : b - a;
  }
  return sortDir === "asc"
    ? String(a || "").localeCompare(String(b || ""))
    : String(b || "").localeCompare(String(a || ""));
}

function parseBudget(value) {
  if (value == null || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function roundMoney(value) {
  return Math.round(value * 100) / 100;
}

function buildUsageSummary(item) {
  const maxBudget = parseBudget(item.max_budget);
  let remainingBudget = null;
  if (maxBudget != null && item.usage_spend != null) {
    remainingBudget = maxBudget === 0 ? 0 : roundMoney(Math.max(maxBudget - item.usage_spend, 0));
  }
  return {
    spend: item.usage_spend == null ? null : roundMoney(item.usage_spend),
    prompt_tokens: item.usage_prompt_tokens ?? null,
    completion_tokens: item.usage_completion_tokens ?? null,
    total_tokens: item.usage_total_tokens ?? null,
    max_budget: maxBudget,
    remaining_budget: remainingBudget,
    tpm_limit: limitStrategyConfig.rate_limit_tpm ?? null,
    rpm_limit: limitStrategyConfig.rate_limit_rpm ?? null,
    max_parallel_requests: limitStrategyConfig.max_parallel_requests ?? null,
    budget_reset_at: item.usage_budget_reset_at ?? null,
    synced_at: item.usage_synced_at ?? null,
  };
}

function decorateApiKey(item, auth) {
  const usageSummary = buildUsageSummary(item);
  return {
    ...item,
    key_alias: normalizeAlias(item),
    extend_eligible: isExtendEligible(item, auth),
    usage_summary: usageSummary,
  };
}

function paginateItems(items, params, defaultPageSize = 20) {
  const page = Number(params?.page || 1);
  const pageSize = Number(params?.page_size || defaultPageSize);
  const start = (page - 1) * pageSize;
  return {
    items: items.slice(start, start + pageSize),
    page,
    page_size: pageSize,
    total: items.length
  };
}

function buildUserStatistics(
  items,
  { q = "", scope = "all", from, to, owner_account = "", owner_name = "", owner_email = "", owner_department = "" }
) {
  const keyword = q.trim().toLowerCase();
  const filtered = items.filter((item) => {
    if (scope !== "all" && item.status !== scope) return false;
    if (from && item.application_date < from) return false;
    if (to && item.application_date > to) return false;
    if (owner_account && !containsCI(item.owner_account, owner_account)) return false;
    if (owner_name && !containsCI(item.owner_name, owner_name)) return false;
    if (owner_email && !containsCI(`${item.owner_account}@example.com`, owner_email)) return false;
    if (owner_department && !containsCI(item.department || "", owner_department)) return false;
    if (!keyword) return true;
    return [item.owner_account, item.owner_name, `${item.owner_account}@example.com`]
      .join(" ")
      .toLowerCase()
      .includes(keyword);
  });

  const byOwner = new Map();
  for (const item of filtered) {
    if (!byOwner.has(item.owner_account)) {
      byOwner.set(item.owner_account, {
        owner_account: item.owner_account,
        owner_name: item.owner_name,
        owner_email: `${item.owner_account}@example.com`,
        owner_department: item.department || "",
        total_applications: 0,
        active_count: 0,
        revoked_count: 0,
        expired_count: 0,
        last_applied_at: item.application_date
      });
    }
    const stat = byOwner.get(item.owner_account);
    stat.total_applications += 1;
    if (item.status === "active") stat.active_count += 1;
    if (item.status === "revoked") stat.revoked_count += 1;
    if (item.status === "expired") stat.expired_count += 1;
    if (item.application_date > stat.last_applied_at) {
      stat.last_applied_at = item.application_date;
    }
  }
  return Array.from(byOwner.values());
}

function ensureUsageAccess(item, auth) {
  if (!item) {
    throw createError("VALIDATION_ERROR", "key not found", 404);
  }
  if (auth.role !== "admin" && item.owner_account !== auth.account) {
    throw createError("KEY_NOT_OWNED_BY_USER", "key is not owned by requester", 403);
  }
}

function applyDateRange(items, { from, to }) {
  return items.filter((item) => {
    const date = item.created_at.slice(0, 10);
    if (from && date < from) return false;
    if (to && date > to) return false;
    return true;
  });
}

function applyDateRangeByField(items, { from, to }, field) {
  return items.filter((item) => {
    const date = String(item[field] || "").slice(0, 10);
    if (from && date < from) return false;
    if (to && date > to) return false;
    return true;
  });
}

export const mockApiProvider = {
  async getCurrentUser(auth) {
    await delay();
    const user = findOrCreateUserByAuth(auth || {
      account: "jane.doe",
      name: "Jane Doe",
      email: "jane.doe@company.com",
      department: "02",
      sysid: 123,
      role: "user"
    });
    return {
      account: user.account,
      name: user.name,
      email: user.email,
      department: user.department || "02",
      sysid: user.sysid,
      role: user.role,
      csrf_token: "mock-csrf-token"
    };
  },

  async createApplication(payload, auth) {
    await delay();
    validateApplication(payload, auth);

    const plain = generatePlainKey();
    const id = `key_${String(apiKeys.length + 1).padStart(3, "0")}`;
    const now = new Date();
    const expires = new Date(now.getTime() + payload.duration_days * MS_PER_DAY);

    apiKeys = [
      {
        id,
        status: "active",
        masked_key: `AS-...${plain.slice(-4)}`,
        application_date: payload.application_date,
        duration_days: payload.duration_days,
        original_duration_days: payload.duration_days,
        purpose: payload.purpose.trim(),
        key_alias: ensureUniqueAlias(auth.account),
        department: auth.department,
        created_at: now.toISOString(),
        expires_at: expires.toISOString(),
        expiration_notice_sent_at: null,
        max_budget: limitStrategyConfig.budget_max_budget,
        tpm_limit: limitStrategyConfig.rate_limit_tpm,
        rpm_limit: limitStrategyConfig.rate_limit_rpm,
        usage_spend: null,
        usage_budget_reset_at: null,
        usage_synced_at: null,
        owner_account: auth.account,
        owner_name: auth.name,
        renewed_to_key_id: null
      },
      ...apiKeys
    ];

    return {
      application: {
        id,
        account: auth.account,
        status: "active",
        issued_at: now.toISOString(),
        expires_at: expires.toISOString()
      },
      api_key_plaintext: plain
    };
  },

  async listApiKeys(paramsOrAuth, maybeAuth) {
    await delay();
    const hasAuthHeaderShape = Boolean(paramsOrAuth?.account && paramsOrAuth?.email && paramsOrAuth?.sysid);
    const auth = hasAuthHeaderShape ? paramsOrAuth : maybeAuth;
    const params = hasAuthHeaderShape ? {} : paramsOrAuth || {};

    let items = auth.role === "admin"
      ? [...apiKeys]
      : apiKeys.filter((item) => item.owner_account === auth.account && !item.renewed_to_key_id);

    if (auth.role === "admin" && params.owner_account) {
      items = items.filter((item) => containsCI(item.owner_account, params.owner_account));
    }
    if (auth.role === "admin" && params.owner_name) {
      items = items.filter((item) => containsCI(item.owner_name, params.owner_name));
    }
    if (params.status) {
      items = items.filter((item) => item.status === params.status);
    }
    if (params.key_alias) {
      items = items.filter((item) => containsCI(normalizeAlias(item), params.key_alias));
    }
    const applicationDateFrom = params.application_date_from || params.from;
    const applicationDateTo = params.application_date_to || params.to;
    if (applicationDateFrom) {
      items = items.filter((item) => item.application_date >= applicationDateFrom);
    }
    if (applicationDateTo) {
      items = items.filter((item) => item.application_date <= applicationDateTo);
    }
    if (params.expires_from) {
      const expiresFrom = new Date(params.expires_from).getTime();
      items = items.filter((item) => new Date(item.expires_at).getTime() >= expiresFrom);
    }
    if (params.expires_to) {
      const expiresTo = new Date(params.expires_to).getTime();
      items = items.filter((item) => new Date(item.expires_at).getTime() <= expiresTo);
    }

    const sortBy = params.sort_by || "created_at";
    const sortDir = params.sort_dir === "asc" ? "asc" : "desc";
    items.sort((left, right) => {
      const leftValue = {
        application_date: left.application_date,
        duration_days: left.duration_days,
        status: left.status,
        expires_at: left.expires_at,
        masked_key: left.masked_key,
        key_alias: normalizeAlias(left),
        owner_account: left.owner_account,
        owner_name: left.owner_name,
        created_at: left.created_at,
      }[sortBy];
      const rightValue = {
        application_date: right.application_date,
        duration_days: right.duration_days,
        status: right.status,
        expires_at: right.expires_at,
        masked_key: right.masked_key,
        key_alias: normalizeAlias(right),
        owner_account: right.owner_account,
        owner_name: right.owner_name,
        created_at: right.created_at,
      }[sortBy];
      const compared = compareValues(leftValue, rightValue, sortDir);
      return compared || compareValues(left.id, right.id, sortDir);
    });

    const page = Number(params.page || 1);
    const pageSize = Number(params.page_size || 20);
    const start = (page - 1) * pageSize;
    const paged = items.slice(start, start + pageSize);
    return {
      items: paged.map((item) => decorateApiKey(item, auth)),
      page,
      page_size: pageSize,
      total: items.length
    };
  },

  async listApiKeyUsageSeries(params, auth) {
    await delay();
    if (params?.granularity !== "day") {
      throw createError("VALIDATION_ERROR", "granularity must be day", 422);
    }
    if (!params?.from || !params?.to || params.from > params.to) {
      throw createError("VALIDATION_ERROR", "invalid date range", 422);
    }
    const key = findApiKeyById(params?.key_id);
    ensureUsageAccess(key, auth);
    const items = usageSeries
      .filter((item) => item.key_id === params.key_id && item.granularity === "day")
      .filter((item) => item.bucket_label >= params.from && item.bucket_label <= params.to)
      .sort((left, right) => left.bucket_label.localeCompare(right.bucket_label))
      .map(({ key_id, granularity, ...rest }) => rest);
    return {
      key_id: params.key_id,
      granularity: "day",
      from: params.from,
      to: params.to,
      items
    };
  },

  async getApiKeyUsageTotal(auth) {
    await delay();
    const visibleItems = filterKeysByAuth(apiKeys, auth);
    const visibleIds = new Set(visibleItems.map((item) => item.id));
    let promptTokens = 0;
    let completionTokens = 0;
    let totalTokens = 0;
    const countedKeys = new Set();

    usageSeries.forEach((item) => {
      if (!visibleIds.has(item.key_id)) return;
      countedKeys.add(item.key_id);
      promptTokens += item.prompt_tokens ?? 0;
      completionTokens += item.completion_tokens ?? 0;
      totalTokens += item.total_tokens ?? 0;
    });

    return {
      scope: "all_visible_keys",
      prompt_tokens: promptTokens,
      completion_tokens: completionTokens,
      total_tokens: totalTokens,
      key_count: countedKeys.size,
    };
  },

  async listApiKeyUserStatistics(params, auth) {
    await delay();
    ensureAdmin(auth);
    const page = Number(params.page || 1);
    const pageSize = Number(params.page_size || 20);
    const sortBy = params.sort_by || "total_applications";
    const sortDir = params.sort_dir === "asc" ? "asc" : "desc";
    const stats = buildUserStatistics(apiKeys, params);
    const sorted = stats.sort((a, b) => {
      const compared = compareValues(a[sortBy], b[sortBy], sortDir);
      return compared || a.owner_account.localeCompare(b.owner_account);
    });

    const start = (page - 1) * pageSize;
    const end = start + pageSize;
    return {
      items: sorted.slice(start, end),
      page,
      page_size: pageSize,
      total: sorted.length
    };
  },

  async listOperationAuditLogs(params, auth) {
    await delay();
    ensureAdmin(auth);
    const sortBy = params?.sort_by || "created_at";
    const sortDir = params?.sort_dir === "asc" ? "asc" : "desc";
    const filtered = applyDateRange(operationAuditLogs, params || {})
      .filter((item) => (params?.event_type ? item.event_type === params.event_type : true))
      .filter((item) => (params?.action ? containsCI(item.action, params.action) : true))
      .filter((item) => (params?.result ? item.result === params.result : true))
      .filter((item) => (params?.actor_account ? containsCI(item.actor_account, params.actor_account) : true))
      .filter((item) => (params?.target_type ? item.target_type === params.target_type : true))
      .filter((item) => (params?.target_id ? containsCI(item.target_id, params.target_id) : true))
      .filter((item) => (params?.error_code ? containsCI(item.error_code, params.error_code) : true))
      .sort((a, b) => {
        const compared = compareValues(a[sortBy], b[sortBy], sortDir);
        return compared || String(a.id).localeCompare(String(b.id));
      });

    return paginateItems(filtered, params);
  },

  async listAuthAuditLogs(params, auth) {
    await delay();
    ensureAdmin(auth);
    const sortBy = params?.sort_by || "created_at";
    const sortDir = params?.sort_dir === "asc" ? "asc" : "desc";
    const normalizedSysid = params?.sysid != null && String(params.sysid).trim() !== ""
      ? Number(params.sysid)
      : null;
    const filtered = applyDateRange(authAuditLogs, params || {})
      .filter((item) => (params?.provider ? item.provider === params.provider : true))
      .filter((item) => (params?.result ? item.result === params.result : true))
      .filter((item) => (params?.account ? containsCI(item.account, params.account) : true))
      .filter((item) => (normalizedSysid != null ? item.sysid === normalizedSysid : true))
      .filter((item) => (params?.role ? item.role === params.role : true))
      .filter((item) => (params?.error_code ? containsCI(item.error_code, params.error_code) : true))
      .filter((item) => (params?.request_id ? containsCI(item.request_id, params.request_id) : true))
      .sort((a, b) => {
        const compared = compareValues(a[sortBy], b[sortBy], sortDir);
        return compared || String(a.id).localeCompare(String(b.id));
      });

    return paginateItems(filtered, params);
  },

  async listSchedulerLogs(params, auth) {
    await delay();
    ensureAdmin(auth);
    const sortDir = params?.sort_dir === "asc" ? "asc" : "desc";
    const fileMode = params?.file_mode || "date";
    const availableFiles = params?.job
      ? schedulerLogs
          .filter((item) => item.job === params.job)
          .map((item) => ({ log_date: item.log_date, source_file: item.source_file }))
          .filter((item, index, arr) => arr.findIndex((candidate) => candidate.source_file === item.source_file) === index)
          .sort((a, b) => String(b.log_date).localeCompare(String(a.log_date)))
      : [];
    let scopedItems = schedulerLogs;
    if (fileMode === "latest") {
      const latestByJob = new Map();
      for (const item of schedulerLogs) {
        const previous = latestByJob.get(item.job);
        if (!previous || item.log_date > previous.log_date) {
          latestByJob.set(item.job, item);
        }
      }
      scopedItems = schedulerLogs.filter((item) => latestByJob.get(item.job)?.source_file === item.source_file);
    } else if (fileMode === "date") {
      scopedItems = applyDateRangeByField(schedulerLogs, params || {}, "log_date");
    }

    const filtered = scopedItems
      .filter((item) => (params?.job ? item.job === params.job : true))
      .filter((item) => (params?.level ? item.level === params.level : true))
      .filter((item) => (params?.q ? containsCI(item.message, params.q) || containsCI(item.raw_line, params.q) : true))
      .sort((a, b) => {
        const compared = compareValues(a.timestamp, b.timestamp, sortDir);
        return compared || String(a.id).localeCompare(String(b.id));
      });

    return {
      available_files: availableFiles,
      ...paginateItems(filtered, params)
    };
  },

  async getApiKeyById(id, auth) {
    await delay();
    const target = findApiKeyById(id);
    if (!target) {
      throw createError("VALIDATION_ERROR", "id not found", 404);
    }

    if (auth.role !== "admin" && target.owner_account !== auth.account) {
      throw createError("KEY_NOT_OWNED_BY_USER", "key is not owned by user", 403);
    }

    return { item: decorateApiKey(target, auth) };
  },

  async updateApiKey(id, payload, auth) {
    await delay();
    ensureAdmin(auth);
    const target = findApiKeyById(id);
    if (!target) {
      throw createError("VALIDATION_ERROR", "id not found", 404);
    }
    const normalizedAlias = String(payload?.key_alias || "").trim();
    if (!normalizedAlias) {
      throw createError("VALIDATION_ERROR", "key alias cannot be empty", 422);
    }
    if (containsUnsafePersistedText(normalizedAlias)) {
      throw createError("VALIDATION_ERROR", "key_alias contains unsafe syntax", 422);
    }
    if (!containsOnlyAllowedPersistedTextCharacters(normalizedAlias, { allowSpaces: false })) {
      throw createError("VALIDATION_ERROR", "key_alias contains invalid characters", 422);
    }
    if (apiKeys.some((item) => item.id !== id && normalizeAlias(item) === normalizedAlias)) {
      throw createError("KEY_ALIAS_DUPLICATE", "key_alias already exists", 409);
    }
    target.key_alias = normalizedAlias;
    return { item: { ...target, key_alias: normalizeAlias(target) } };
  },

  async revokeApiKey(id, auth) {
    await delay();
    const target = findApiKeyById(id);
    if (!target) {
      throw createError("VALIDATION_ERROR", "id not found", 404);
    }
    if (auth.role !== "admin" && target.owner_account !== auth.account) {
      throw createError("KEY_NOT_OWNED_BY_USER", "key is not owned by user", 403);
    }
    if (target.status !== "active") {
      throw createError("KEY_NOT_ACTIVE", "key is not active");
    }
    target.status = "revoked";
    return { success: true };
  },

  async renewApiKey(id, auth) {
    await delay();
    const target = findApiKeyById(id);
    if (!target) {
      throw createError("VALIDATION_ERROR", "id not found", 404);
    }
    if (auth.role !== "admin" && target.owner_account !== auth.account) {
      throw createError("KEY_NOT_OWNED_BY_USER", "key is not owned by user", 403);
    }
    if (!["revoked", "expired"].includes(target.status)) {
      throw createError("KEY_NOT_RENEWABLE", "only revoked or expired key can be renewed", 409);
    }
    if (target.renewed_to_key_id) {
      throw createError("KEY_ALREADY_RENEWED", "key already renewed", 409);
    }

    const idNew = `key_${String(apiKeys.length + 1).padStart(3, "0")}`;
    const now = new Date();
    const expires = new Date(now.getTime() + target.duration_days * MS_PER_DAY);
    const plain = generatePlainKey();

    apiKeys = [
      {
        id: idNew,
        status: "active",
        masked_key: `AS-...${plain.slice(-4)}`,
        application_date: now.toISOString().slice(0, 10),
        duration_days: target.duration_days,
        original_duration_days: target.original_duration_days ?? target.duration_days,
        purpose: target.purpose || "",
        key_alias: ensureUniqueAlias(target.owner_account, target.key_alias),
        department: target.department,
        created_at: now.toISOString(),
        expires_at: expires.toISOString(),
        expiration_notice_sent_at: null,
        owner_account: target.owner_account,
        owner_name: target.owner_name,
        renewed_to_key_id: null
      },
      ...apiKeys
    ];

    target.renewed_to_key_id = idNew;
    return {
      id: idNew,
      status: "active",
      expires_at: expires.toISOString(),
      renewed_from_key_id: target.id,
      api_key_plaintext: plain
    };
  },

  async extendApiKey(id, auth) {
    await delay();
    const target = findApiKeyById(id);
    if (!target) {
      throw createError("VALIDATION_ERROR", "id not found", 404);
    }
    if (auth.role !== "admin" && target.owner_account !== auth.account) {
      throw createError("KEY_NOT_OWNED_BY_USER", "key is not owned by user", 403);
    }
    if (target.status !== "active") {
      throw createError("KEY_NOT_EXTENDABLE", "only active key can be extended", 409);
    }
    if (target.renewed_to_key_id) {
      throw createError("KEY_ALREADY_RENEWED", "key already renewed", 409);
    }

    const originalDurationDays = Number(target.original_duration_days ?? target.duration_days);
    const now = new Date();
    target.original_duration_days = originalDurationDays;
    target.application_date = now.toISOString().slice(0, 10);
    target.duration_days = originalDurationDays;
    target.expires_at = expiresAtFromApplicationDate(target.application_date, originalDurationDays);
    target.status = "active";
    target.expiration_notice_sent_at = null;

    return {
      id: target.id,
      status: "active",
      expires_at: target.expires_at
    };
  },

  async listWhitelists(paramsOrAuth, maybeAuth) {
    await delay();
    const hasAuthHeaderShape = Boolean(paramsOrAuth?.account && paramsOrAuth?.email && paramsOrAuth?.sysid);
    const auth = hasAuthHeaderShape ? paramsOrAuth : maybeAuth;
    const params = hasAuthHeaderShape ? {} : paramsOrAuth || {};
    ensureAdmin(auth);
    let items = [...whitelists];

    if (params.status) {
      items = items.filter((item) => item.status === params.status);
    }
    if (params.sysid != null && params.sysid !== "") {
      items = items.filter((item) => item.sysid === Number(params.sysid));
    }
    if (params.account) {
      const q = String(params.account).trim().toLowerCase();
      items = items.filter((item) => String(item.account || "").toLowerCase().includes(q));
    }
    if (params.name) {
      const q = String(params.name).trim().toLowerCase();
      items = items.filter((item) => String(item.name || "").toLowerCase().includes(q));
    }
    if (params.email) {
      const q = String(params.email).trim().toLowerCase();
      items = items.filter((item) => String(item.email || "").toLowerCase().includes(q));
    }
    if (params.created_from) {
      items = items.filter((item) => new Date(item.created_at) >= new Date(params.created_from));
    }
    if (params.created_to) {
      items = items.filter((item) => new Date(item.created_at) <= new Date(params.created_to));
    }
    if (params.updated_from) {
      items = items.filter((item) => new Date(item.updated_at) >= new Date(params.updated_from));
    }
    if (params.updated_to) {
      items = items.filter((item) => new Date(item.updated_at) <= new Date(params.updated_to));
    }

    const sortBy = params.sort_by || "created_at";
    const sortDir = params.sort_dir === "asc" ? "asc" : "desc";
    items.sort((a, b) => {
      const direction = sortDir === "asc" ? 1 : -1;
      const left = a[sortBy];
      const right = b[sortBy];
      if (left == null && right == null) return 0;
      if (left == null) return 1 * direction;
      if (right == null) return -1 * direction;
      if (sortBy === "sysid") return (Number(left) - Number(right)) * direction;
      return String(left).localeCompare(String(right)) * direction;
    });

    const page = Math.max(Number(params.page || 1), 1);
    const pageSize = Math.max(Number(params.page_size || 20), 1);
    const total = items.length;
    const start = (page - 1) * pageSize;
    const pagedItems = items.slice(start, start + pageSize);

    return { items: pagedItems, page, page_size: pageSize, total };
  },

  async searchUsers(keyword, auth, options = {}) {
    await delay();
    ensureAdmin(auth);

    const q = keyword?.trim().toLowerCase();
    if (!q) {
      throw createError("VALIDATION_ERROR", "請輸入查詢關鍵字");
    }
    if (!["proxy_application", "admin_create", "whitelist_create"].includes(options.lookup_context || "")) {
      throw createError(
        "VALIDATION_ERROR",
        "lookup_context must be one of: proxy_application, admin_create, whitelist_create",
        422
      );
    }

    const items = users.filter((item) =>
      [item.sysid, item.account, item.name, item.email].some((value) => String(value).toLowerCase().includes(q))
    );

    return { items: items.map(mapUserForAdminPage) };
  },

  async listAdmins(paramsOrAuth, maybeAuth) {
    await delay();
    const hasAuthHeaderShape = Boolean(paramsOrAuth?.account && paramsOrAuth?.email && paramsOrAuth?.sysid);
    const auth = hasAuthHeaderShape ? paramsOrAuth : maybeAuth;
    const params = hasAuthHeaderShape ? {} : paramsOrAuth || {};
    ensureAdmin(auth);
    const normalizedSysid = String(params.sysid || "").trim();
    const parsedSysid = normalizedSysid && isAsciiDigits(normalizedSysid) ? Number(normalizedSysid) : null;
    const filtered = users
      .filter((item) => item.role === "admin")
      .map(mapUserForAdminPage)
      .filter((item) => {
        if (params.status && item.status !== params.status) return false;
        if (parsedSysid != null && item.sysid !== parsedSysid) return false;
        if (params.account && !containsCI(item.account, params.account)) return false;
        if (params.name && !containsCI(item.name, params.name)) return false;
        if (params.email && !containsCI(item.email, params.email)) return false;
        if (params.created_from && item.created_at < params.created_from) return false;
        if (params.created_to && item.created_at > params.created_to) return false;
        if (params.updated_from && item.updated_at < params.updated_from) return false;
        if (params.updated_to && item.updated_at > params.updated_to) return false;
        return true;
      });

    const sortField = params.sort_by || "created_at";
    const sortDir = params.sort_dir || "desc";
    const sorted = [...filtered].sort((a, b) => compareValues(a[sortField], b[sortField], sortDir));
    return paginateItems(sorted, params);
  },

  async listAnnouncements(paramsOrAuth, maybeAuth) {
    await delay();
    const hasAuthHeaderShape = Boolean(paramsOrAuth?.account && paramsOrAuth?.email && paramsOrAuth?.sysid);
    const auth = hasAuthHeaderShape ? paramsOrAuth : maybeAuth;
    const params = hasAuthHeaderShape ? {} : paramsOrAuth || {};
    if (!auth?.account) {
      throw createError("UNAUTHORIZED", "unauthorized", 401);
    }

    const scope = params.scope || "";
    if (scope && scope !== "all") {
      throw createError("VALIDATION_ERROR", "scope must be all when provided", 422);
    }
    if (scope === "all") {
      ensureAdmin(auth);
    }

    let items = [...announcements];
    if (scope !== "all") {
      items = items.filter((item) => isAnnouncementVisible(item));
    }
    if (params.status) {
      items = items.filter((item) => item.status === params.status);
    }
    if (params.title) {
      items = items.filter((item) => containsCI(item.title, params.title));
    }
    if (params.publish_from_from) {
      items = items.filter((item) => item.publish_from && new Date(item.publish_from) >= new Date(params.publish_from_from));
    }
    if (params.publish_from_to) {
      items = items.filter((item) => item.publish_from && new Date(item.publish_from) <= new Date(params.publish_from_to));
    }
    if (params.publish_to_from) {
      items = items.filter((item) => item.publish_to && new Date(item.publish_to) >= new Date(params.publish_to_from));
    }
    if (params.publish_to_to) {
      items = items.filter((item) => item.publish_to && new Date(item.publish_to) <= new Date(params.publish_to_to));
    }
    if (params.updated_from) {
      items = items.filter((item) => new Date(item.updated_at) >= new Date(params.updated_from));
    }
    if (params.updated_to) {
      items = items.filter((item) => new Date(item.updated_at) <= new Date(params.updated_to));
    }

    const sortField = params.sort_by || "updated_at";
    const sortDir = params.sort_dir || "desc";
    const sorted = [...items].sort((a, b) => compareValues(a[sortField], b[sortField], sortDir));
    return paginateItems(sorted, params);
  },

  async listInstitutes(auth) {
    await delay();
    if (!auth?.account) {
      throw createError("UNAUTHORIZED", "unauthorized", 401);
    }
    return { items: mockInstitutes, total: mockInstitutes.length };
  },

  async listModels(auth) {
    await delay();
    if (!auth?.account) {
      throw createError("UNAUTHORIZED", "unauthorized", 401);
    }
    const items = (modelsPayload.data || [])
      .map((item) => String(item?.id || "").trim())
      .filter(Boolean)
      .sort((a, b) => a.localeCompare(b))
      .map((id) => ({ id, label: id }));
    return {
      items,
      total: items.length,
      fetched_at: new Date().toISOString()
    };
  },

  async syncInstitutes(auth) {
    await delay();
    ensureAdmin(auth);
    return {
      fetched_count: mockInstitutes.length,
      inserted_count: 0,
      updated_count: 0,
      unchanged_count: mockInstitutes.length,
      deactivated_count: 0
    };
  },

  async enableAdmin(id, auth) {
    await delay();
    ensureAdmin(auth);
    const user = findUserById(id);
    if (!user) {
      throw createError("USER_NOT_FOUND", "使用者不存在", 404);
    }
    user.role = "admin";
    user.status = "active";
    return { item: mapUserForAdminPage(user) };
  },

  async createAdmin(id, payload, auth) {
    await delay();
    ensureAdmin(auth);
    const existing = findUserById(id);
    if (existing && existing.role === "admin") {
      throw createError("ADMIN_ALREADY_EXISTS", "管理者已存在", 409);
    }
    const user = existing || findOrCreateUserByAuth({
      account: payload.account,
      name: payload.name,
      email: payload.email,
      department: payload.department || "",
      sysid: Number(payload.id) || 0,
      role: "user"
    });
    user.role = "admin";
    user.status = "active";
    user.account = payload.account;
    user.name = payload.name;
    user.email = payload.email;
    user.department = payload.department || "";
    return { item: mapUserForAdminPage(user) };
  },

  async disableAdmin(id, auth) {
    await delay();
    ensureAdmin(auth);
    const user = findUserById(id);
    if (!user) {
      throw createError("USER_NOT_FOUND", "使用者不存在", 404);
    }
    if (user.sysid === auth.sysid) {
      throw createError("VALIDATION_ERROR", "不可取消自己的管理者權限");
    }
    user.role = "admin";
    user.status = "inactive";
    return { item: mapUserForAdminPage(user) };
  },

  async deleteAdmin(id, auth) {
    await delay();
    ensureAdmin(auth);
    const user = findUserById(id);
    if (!user || user.role !== "admin") {
      throw createError("USER_NOT_FOUND", "使用者不存在", 404);
    }
    if (user.status !== "inactive") {
      throw createError("VALIDATION_ERROR", "active admin cannot be deleted", 422);
    }
    users = users.filter((item) => item.id !== id);
  },

  async createAnnouncement(payload, auth) {
    await delay();
    ensureAdmin(auth);
    const normalized = normalizeAnnouncementPayload(payload);
    const now = new Date().toISOString();
    const item = {
      id: `ann_${String(announcements.length + 1).padStart(3, "0")}`,
      ...normalized,
      created_at: now,
      updated_at: now
    };
    announcements = [item, ...announcements];
    return item;
  },

  async updateAnnouncement(id, payload, auth) {
    await delay();
    ensureAdmin(auth);
    const item = findAnnouncementById(id);
    if (!item) {
      throw createError("VALIDATION_ERROR", "announcement not found", 404);
    }
    const normalized = normalizeAnnouncementPayload(payload);
    Object.assign(item, normalized, { updated_at: new Date().toISOString() });
    return { ...item };
  },

  async deleteAnnouncement(id, auth) {
    await delay();
    ensureAdmin(auth);
    const item = findAnnouncementById(id);
    if (!item) {
      throw createError("VALIDATION_ERROR", "announcement not found", 404);
    }
    announcements = announcements.filter((entry) => entry.id !== id);
    return {};
  },

  async getLocalePreference(auth) {
    await delay();
    const user = findOrCreateUserByAuth(auth);
    return { preferred_locale: user.preferred_locale || null };
  },

  async updateLocalePreference(preferredLocale, auth) {
    await delay();
    if (!["zh-TW", "en"].includes(preferredLocale)) {
      throw createError("VALIDATION_ERROR", "preferred_locale must be one of: zh-TW, en");
    }
    const user = findOrCreateUserByAuth(auth);
    user.preferred_locale = preferredLocale;
    return { preferred_locale: user.preferred_locale };
  },

  async createWhitelist(payload, auth) {
    await delay();
    ensureAdmin(auth);

    const sysid = Number(payload.sysid);
    if (!Number.isInteger(sysid) || sysid <= 0) {
      throw createError("VALIDATION_ERROR", "SysID 不可為空");
    }

    if (whitelists.some((item) => item.sysid === sysid)) {
      throw createError("WHITELIST_SYSID_DUPLICATED", "SysID 已存在於特殊人員名單");
    }

    const now = new Date().toISOString();
    const item = {
      id: `wl_${String(whitelists.length + 1).padStart(3, "0")}`,
      email: payload.email?.trim().toLowerCase() || "",
      account: payload.account || "",
      status: "active",
      note: payload.note?.trim() || "",
      sysid,
      name: payload.name || "",
      created_at: now,
      updated_at: now
    };
    whitelists = [item, ...whitelists];
    return { item };
  },

  async updateWhitelist(id, payload, auth) {
    await delay();
    ensureAdmin(auth);

    const item = whitelists.find((entry) => entry.id === id);
    if (!item) {
      throw createError("VALIDATION_ERROR", "id not found", 404);
    }

    if (payload.status && !["active", "inactive"].includes(payload.status)) {
      throw createError("VALIDATION_ERROR", "status 僅允許 active 或 inactive");
    }

    if (typeof payload.note === "string" && containsUnsafePersistedText(payload.note)) {
      throw createError("VALIDATION_ERROR", "note contains unsafe syntax", 422);
    }
    if (typeof payload.note === "string" && payload.note.trim() && !containsOnlyAllowedPersistedTextCharacters(payload.note.trim(), { allowSpaces: true })) {
      throw createError("VALIDATION_ERROR", "note contains invalid characters", 422);
    }

    item.status = payload.status || item.status;
    item.note = typeof payload.note === "string" ? payload.note : item.note;
    item.updated_at = new Date().toISOString();

    return { item };
  },

  async deleteWhitelist(id, auth) {
    await delay();
    ensureAdmin(auth);
    const index = whitelists.findIndex((entry) => entry.id === id);
    if (index < 0) {
      throw createError("VALIDATION_ERROR", "id not found", 404);
    }
    whitelists.splice(index, 1);
    return {};
  },

  async getLimitStrategyConfig(auth) {
    await delay();
    ensureAdmin(auth);
    return { ...limitStrategyConfig };
  },

  async updateLimitStrategyConfig(payload, auth) {
    await delay();
    ensureAdmin(auth);
    if (!String(payload?.budget_max_budget || "").trim() || !String(payload?.budget_duration || "").trim()) {
      throw createError("VALIDATION_ERROR", "budget config is required", 422);
    }
    if (!isAsciiDigits(String(payload?.budget_max_budget || "").trim())) {
      throw createError("VALIDATION_ERROR", "budget_max_budget must contain only ASCII digits", 422);
    }
    const rawTpm = payload?.rate_limit_tpm;
    const rawRpm = payload?.rate_limit_rpm;
    const rawMaxParallelRequests = payload?.max_parallel_requests;
    if (!isAsciiDigits(String(rawTpm)) || !isAsciiDigits(String(rawRpm)) || !isAsciiDigits(String(rawMaxParallelRequests))) {
      throw createError("VALIDATION_ERROR", "rate limit config is required", 422);
    }
    const rateLimitTpm = Number(rawTpm);
    const rateLimitRpm = Number(rawRpm);
    const maxParallelRequests = Number(rawMaxParallelRequests);
    limitStrategyConfig = {
      budget_max_budget: String(payload.budget_max_budget).trim(),
      budget_duration: String(payload.budget_duration).trim(),
      rate_limit_tpm: rateLimitTpm,
      rate_limit_rpm: rateLimitRpm,
      max_parallel_requests: maxParallelRequests
    };
    return { ...limitStrategyConfig };
  },

  async listPendingApplications(auth) {
    await delay();
    ensureAdmin(auth);
    return { items: [], total: 0 };
  },

  async updateApplicationIssuanceMode(id, mode, auth) {
    await delay();
    ensureAdmin(auth);
    return { id, selected_issuance_mode: mode };
  },

  async issueApplication(id, auth) {
    await delay();
    ensureAdmin(auth);
    return {
      application: { id, account: "mock", status: "active", issued_at: new Date().toISOString(), expires_at: new Date().toISOString() },
      api_key_plaintext: "AS-mockmockmockmockmockmockmockmo"
    };
  },

  async logout() {
    await delay();
    return { status: "ok" };
  },

  resetForTests() {
    apiKeys = initialApiKeys.map((item) => ({ ...item }));
    whitelists = initialWhitelists.map((item) => ({ ...item }));
    announcements = initialAnnouncements.map((item) => ({ ...item }));
    users = initialUsers.map((item) => ({ ...item }));
    modelsPayload = {
      data: initialModelsPayload.data.map((item) => ({ ...item })),
      object: initialModelsPayload.object
    };
    usageSeries = initialUsageSeries.map((item) => ({ ...item }));
    limitStrategyConfig = {
      budget_max_budget: "1000",
      budget_duration: "monthly",
      rate_limit_tpm: 10000,
      rate_limit_rpm: 500,
      max_parallel_requests: 0
    };
    operationAuditLogs = [
      {
        id: "oplog_001",
        created_at: new Date().toISOString(),
        event_type: "api_key",
        action: "create",
        result: "success",
        actor_account: "john.admin",
        target_type: "api_key",
        target_id: "key_003",
        error_code: null,
        error_detail: null,
        request_id: "req-op-001"
      },
      {
        id: "oplog_002",
        created_at: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
        event_type: "whitelist",
        action: "update",
        result: "failure",
        actor_account: "john.admin",
        target_type: "whitelist",
        target_id: "wl_001",
        error_code: "VALIDATION_ERROR",
        error_detail: "status must be active or inactive",
        request_id: "req-op-002"
      }
    ];
    schedulerLogs = [
      {
        id: "schedlog_001",
        job: "sync_api_key_usage",
        log_date: "2026-06-17",
        source_file: "2026-06-17.log",
        timestamp: "2026-06-17T00:15:01+08:00",
        level: "ERROR",
        message: "event=usage_sync mode=sync processed_keys=10 success=8 failed=2",
        raw_line: "[2026-06-17T00:15:01+08:00] level=ERROR event=usage_sync mode=sync processed_keys=10 success=8 failed=2"
      },
      {
        id: "schedlog_002",
        job: "sync_api_key_usage",
        log_date: "2026-06-17",
        source_file: "2026-06-17.log",
        timestamp: "2026-06-17T00:05:01+08:00",
        level: "INFO",
        message: "event=usage_sync mode=sync processed_keys=10 success=9 failed=1",
        raw_line: "[2026-06-17T00:05:01+08:00] level=INFO event=usage_sync mode=sync processed_keys=10 success=9 failed=1"
      },
      {
        id: "schedlog_003",
        job: "send_expiration_reminders",
        log_date: "2026-06-16",
        source_file: "2026-06-16.log",
        timestamp: "2026-06-16T08:00:00+08:00",
        level: "WARNING",
        message: "event=expiration_notice sent=0 failed=1",
        raw_line: "[2026-06-16T08:00:00+08:00] level=WARNING event=expiration_notice sent=0 failed=1"
      }
    ];
    authAuditLogs = [
      {
        id: "authlog_001",
        created_at: new Date().toISOString(),
        provider: "sso",
        result: "success",
        account: "jane.doe",
        sysid: 123,
        role: "user",
        error_code: null,
        request_id: "req-auth-001"
      },
      {
        id: "authlog_002",
        created_at: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
        provider: "sso",
        result: "failure",
        account: null,
        sysid: null,
        role: null,
        error_code: "LOGIN_NOT_ELIGIBLE",
        request_id: "req-auth-002"
      }
    ];
  }
};
