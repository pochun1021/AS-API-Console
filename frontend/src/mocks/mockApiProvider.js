const today = new Date().toISOString().slice(0, 10);
const mockInstitutes = [
  { inst_code: "01", inst_name: "院本部", abb_inst_name: "院本部", einst_name: "Headquarters", division: "1" },
  { inst_code: "02", inst_name: "資訊所", abb_inst_name: "資訊所", einst_name: "Institute of Information Science", division: "2" },
  { inst_code: "03", inst_name: "資安中心", abb_inst_name: "資安", einst_name: "Security Center", division: "2" },
  { inst_code: "04", inst_name: "資料平台", abb_inst_name: "資料平台", einst_name: "Data Platform", division: "2" },
  { inst_code: "05", inst_name: "營運處", abb_inst_name: "營運處", einst_name: "Operations", division: "3" }
];

const initialApiKeys = [
  {
    id: "key_001",
    status: "active",
    masked_key: "AS-...xy90",
    application_date: today,
    duration_months: 6,
    purpose: "integration test for platform service",
    department: "02",
    created_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 1000 * 60 * 60 * 24 * 180).toISOString(),
    owner_account: "jane.doe",
    owner_name: "Jane Doe",
    renewed_to_key_id: null
  },
  {
    id: "key_002",
    status: "revoked",
    masked_key: "AS-...mn56",
    application_date: today,
    duration_months: 1,
    purpose: "legacy integration",
    department: "02",
    created_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 1000 * 60 * 60 * 24 * 30).toISOString(),
    owner_account: "jane.doe",
    owner_name: "Jane Doe",
    renewed_to_key_id: null
  },
  {
    id: "key_003",
    status: "active",
    masked_key: "AS-...ab12",
    application_date: today,
    duration_months: 12,
    purpose: "admin automation",
    department: "03",
    created_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 1000 * 60 * 60 * 24 * 365).toISOString(),
    owner_account: "john.admin",
    owner_name: "John Admin",
    renewed_to_key_id: null
  },
  {
    id: "key_004",
    status: "expired",
    masked_key: "AS-...pq78",
    application_date: "2025-04-01",
    duration_months: 1,
    created_at: "2025-04-01T08:00:00.000Z",
    expires_at: "2025-05-01T08:00:00.000Z",
    owner_account: "john.admin",
    owner_name: "John Admin",
    renewed_to_key_id: null
  },
  {
    id: "key_005",
    status: "active",
    masked_key: "AS-...cd34",
    application_date: "2026-04-15",
    duration_months: 6,
    purpose: "reporting service integration",
    department: "04",
    created_at: "2026-04-15T09:30:00.000Z",
    expires_at: "2026-10-15T09:30:00.000Z",
    owner_account: "alice.wang",
    owner_name: "Alice Wang",
    renewed_to_key_id: null
  },
  {
    id: "key_006",
    status: "revoked",
    masked_key: "AS-...ef56",
    application_date: "2026-03-10",
    duration_months: 12,
    purpose: "security scanner",
    department: "03",
    created_at: "2026-03-10T02:20:00.000Z",
    expires_at: "2027-03-10T02:20:00.000Z",
    owner_account: "sam.chen",
    owner_name: "Sam Chen",
    renewed_to_key_id: null
  },
  {
    id: "key_007",
    status: "expired",
    masked_key: "AS-...gh78",
    application_date: "2025-12-01",
    duration_months: 1,
    purpose: "legacy webhook client",
    department: "05",
    created_at: "2025-12-01T05:00:00.000Z",
    expires_at: "2026-01-01T05:00:00.000Z",
    owner_account: "mike.li",
    owner_name: "Mike Li",
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
    remark: "platform team",
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
    remark: "offboarded",
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
    remark: "qa team",
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
    remark: "secops automation",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
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
let users = initialUsers.map((item) => ({ ...item }));
let limitStrategyConfig = {
  budget_max_budget: "1000",
  budget_duration: "monthly",
  rate_limit_tpm: 10000,
  rate_limit_rpm: 500
};
let notifications = [
  {
    id: "ntf_001",
    account: "jane.doe",
    type: "api_key_issued",
    title: "API key issued",
    message: "Your pending API key application has been issued.",
    is_read: false,
    created_at: new Date().toISOString(),
    read_at: null,
    metadata: { application_id: "app_mock_001", key_id: "key_001" }
  }
];
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
    error_code: null
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
    error_code: "VALIDATION_ERROR"
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
  if (![1, 6, 12].includes(payload.duration_months)) {
    throw createError("INVALID_DURATION_MONTHS", "生效時長僅允許 1、6、12 個月");
  }

  if (!/^\d{4}-\d{2}-\d{2}$/.test(payload.application_date) || payload.application_date > today) {
    throw createError("INVALID_APPLICATION_DATE", "申請日期格式需為 YYYY-MM-DD，且不可晚於今天");
  }

  if (!payload.purpose || !payload.purpose.trim()) {
    throw createError("VALIDATION_ERROR", "請填寫用途");
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

function normalizeAlias(item) {
  return item.key_alias || `for_${item.owner_account}`;
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
    status: user.status || "active"
  };
}

function buildUserStatistics(items, { q = "", scope = "all", from, to }) {
  const keyword = q.trim().toLowerCase();
  const filtered = items.filter((item) => {
    if (scope !== "all" && item.status !== scope) return false;
    if (from && item.application_date < from) return false;
    if (to && item.application_date > to) return false;
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

function applyDateRange(items, { from, to }) {
  return items.filter((item) => {
    const date = item.created_at.slice(0, 10);
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
    const expires = new Date(now);
    expires.setMonth(expires.getMonth() + payload.duration_months);

    apiKeys = [
      {
        id,
        status: "active",
        masked_key: `AS-...${plain.slice(-4)}`,
        application_date: payload.application_date,
        duration_months: payload.duration_months,
        purpose: payload.purpose.trim(),
        key_alias: `for_${auth.account}`,
        department: auth.department,
        created_at: now.toISOString(),
        expires_at: expires.toISOString(),
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
      issuance_status: "issued",
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
      items = items.filter((item) => item.owner_account === params.owner_account);
    }
    if (params.status) {
      items = items.filter((item) => item.status === params.status);
    }
    if (params.from) {
      items = items.filter((item) => item.application_date >= params.from);
    }
    if (params.to) {
      items = items.filter((item) => item.application_date <= params.to);
    }

    const page = Number(params.page || 1);
    const pageSize = Number(params.page_size || 20);
    const start = (page - 1) * pageSize;
    const paged = items.slice(start, start + pageSize);
    return {
      items: paged.map((item) => ({ ...item, key_alias: normalizeAlias(item) })),
      page,
      page_size: pageSize,
      total: items.length
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
      const av = a[sortBy];
      const bv = b[sortBy];
      if (av === bv) return a.owner_account.localeCompare(b.owner_account);
      if (sortDir === "asc") return av > bv ? 1 : -1;
      return av < bv ? 1 : -1;
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
    const page = Number(params?.page || 1);
    const pageSize = Number(params?.page_size || 20);
    const filtered = applyDateRange(operationAuditLogs, params || {})
      .filter((item) => (params?.event_type ? item.event_type === params.event_type : true))
      .filter((item) => (params?.result ? item.result === params.result : true))
      .sort((a, b) => (a.created_at < b.created_at ? 1 : -1));

    const start = (page - 1) * pageSize;
    return {
      items: filtered.slice(start, start + pageSize),
      page,
      page_size: pageSize,
      total: filtered.length
    };
  },

  async listAuthAuditLogs(params, auth) {
    await delay();
    ensureAdmin(auth);
    const page = Number(params?.page || 1);
    const pageSize = Number(params?.page_size || 20);
    const filtered = applyDateRange(authAuditLogs, params || {})
      .filter((item) => (params?.provider ? item.provider === params.provider : true))
      .filter((item) => (params?.result ? item.result === params.result : true))
      .sort((a, b) => (a.created_at < b.created_at ? 1 : -1));

    const start = (page - 1) * pageSize;
    return {
      items: filtered.slice(start, start + pageSize),
      page,
      page_size: pageSize,
      total: filtered.length
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

    return { item: { ...target, key_alias: normalizeAlias(target) } };
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
    if (target.status !== "revoked") {
      throw createError("KEY_NOT_RENEWABLE", "only revoked key can be renewed", 409);
    }
    if (target.renewed_to_key_id) {
      throw createError("KEY_ALREADY_RENEWED", "key already renewed", 409);
    }

    const idNew = `key_${String(apiKeys.length + 1).padStart(3, "0")}`;
    const now = new Date();
    const expires = new Date(now);
    expires.setMonth(expires.getMonth() + target.duration_months);
    const plain = generatePlainKey();

    apiKeys = [
      {
        id: idNew,
        status: "active",
        masked_key: `AS-...${plain.slice(-4)}`,
        application_date: now.toISOString().slice(0, 10),
        duration_months: target.duration_months,
        purpose: target.purpose || "",
        key_alias: `for_${target.owner_account}`,
        department: target.department,
        created_at: now.toISOString(),
        expires_at: expires.toISOString(),
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
      issuance_status: "issued",
      renewed_from_key_id: target.id,
      api_key_plaintext: plain,
      pending_reason: null
    };
  },

  async extendApiKey(id, payload, auth) {
    await delay();
    const target = findApiKeyById(id);
    if (!target) {
      throw createError("VALIDATION_ERROR", "id not found", 404);
    }
    if (auth.role !== "admin" && target.owner_account !== auth.account) {
      throw createError("KEY_NOT_OWNED_BY_USER", "key is not owned by user", 403);
    }
    if (!["active", "expired"].includes(target.status)) {
      throw createError("KEY_NOT_EXTENDABLE", "only active or expired key can be extended", 409);
    }
    const durationMonths = Number(payload?.duration_months);
    if (![1, 6, 12].includes(durationMonths)) {
      throw createError("VALIDATION_ERROR", "duration_months must be one of 1, 6, 12", 422);
    }
    if (target.renewed_to_key_id) {
      throw createError("KEY_ALREADY_RENEWED", "key already renewed", 409);
    }

    const idNew = `key_${String(apiKeys.length + 1).padStart(3, "0")}`;
    const now = new Date();
    const expires = new Date(now);
    expires.setMonth(expires.getMonth() + durationMonths);
    const plain = generatePlainKey();

    apiKeys = [
      {
        id: idNew,
        status: "active",
        masked_key: `AS-...${plain.slice(-4)}`,
        application_date: now.toISOString().slice(0, 10),
        duration_months: durationMonths,
        purpose: target.purpose || "",
        key_alias: `for_${target.owner_account}`,
        department: target.department,
        created_at: now.toISOString(),
        expires_at: expires.toISOString(),
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
      issuance_status: "issued",
      renewed_from_key_id: target.id,
      api_key_plaintext: plain,
      pending_reason: null
    };
  },

  async listWhitelists(auth) {
    await delay();
    ensureAdmin(auth);
    return { items: whitelists, page: 1, page_size: 20, total: whitelists.length };
  },

  async searchUsers(keyword, auth) {
    await delay();
    ensureAdmin(auth);

    const q = keyword?.trim().toLowerCase();
    if (!q) {
      throw createError("VALIDATION_ERROR", "請輸入查詢關鍵字");
    }

    const items = users.filter((item) =>
      [item.sysid, item.account, item.name, item.email].some((value) => String(value).toLowerCase().includes(q))
    );

    return { items: items.map(mapUserForAdminPage) };
  },

  async listAdmins(auth) {
    await delay();
    ensureAdmin(auth);
    return { items: users.filter((item) => item.role === "admin").map(mapUserForAdminPage) };
  },

  async listInstitutes(auth) {
    await delay();
    if (!auth?.account) {
      throw createError("UNAUTHORIZED", "unauthorized", 401);
    }
    return { items: mockInstitutes, total: mockInstitutes.length };
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
      remark: payload.remark?.trim() || "",
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

    if (typeof payload.remark === "string" && payload.remark.length > 200) {
      throw createError("VALIDATION_ERROR", "remark 長度不可超過 200 字元");
    }

    item.status = payload.status || item.status;
    item.remark = typeof payload.remark === "string" ? payload.remark : item.remark;
    item.updated_at = new Date().toISOString();

    return { item };
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
      throw createError("MISSING_BUDGET_FIELDS", "budget config is required", 422);
    }
    if (!Number(payload?.rate_limit_tpm) || !Number(payload?.rate_limit_rpm)) {
      throw createError("MISSING_RATE_LIMIT_FIELDS", "rate limit config is required", 422);
    }
    limitStrategyConfig = {
      budget_max_budget: String(payload.budget_max_budget).trim(),
      budget_duration: String(payload.budget_duration).trim(),
      rate_limit_tpm: Number(payload.rate_limit_tpm),
      rate_limit_rpm: Number(payload.rate_limit_rpm)
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
    return { id, selected_issuance_mode: mode, issuance_status: "pending" };
  },

  async issueApplication(id, auth) {
    await delay();
    ensureAdmin(auth);
    return {
      application: { id, account: "mock", status: "active", issued_at: new Date().toISOString(), expires_at: new Date().toISOString() },
      issuance_status: "issued",
      api_key_plaintext: "AS-mockmockmockmockmockmockmockmo",
      pending_reason: null
    };
  },

  async listNotifications(params, auth) {
    await delay();
    const page = Number(params?.page || 1);
    const pageSize = Number(params?.page_size || 20);
    let scoped = notifications.filter((item) => item.account === auth.account);
    if (typeof params?.is_read === "boolean") {
      scoped = scoped.filter((item) => item.is_read === params.is_read);
    }
    const offset = (page - 1) * pageSize;
    return {
      items: scoped.slice(offset, offset + pageSize).map(({ account, ...item }) => ({ ...item })),
      page,
      page_size: pageSize,
      total: scoped.length
    };
  },

  async markNotificationRead(id, auth) {
    await delay();
    const target = notifications.find((item) => item.id === id && item.account === auth.account);
    if (!target) {
      throw createError("VALIDATION_ERROR", "notification not found", 404);
    }
    const firstRead = !target.is_read;
    target.is_read = true;
    target.read_at = new Date().toISOString();
    return {
      id: target.id,
      is_read: target.is_read,
      read_at: target.read_at,
      revealed: firstRead && target.type === "api_key_issued",
      api_key_plaintext: firstRead && target.type === "api_key_issued" ? "AS-mockmockmockmockmockmockmockmo" : null
    };
  },

  async logout() {
    await delay();
    return { status: "ok" };
  },

  resetForTests() {
    apiKeys = initialApiKeys.map((item) => ({ ...item }));
    whitelists = initialWhitelists.map((item) => ({ ...item }));
    users = initialUsers.map((item) => ({ ...item }));
    limitStrategyConfig = {
      budget_max_budget: "1000",
      budget_duration: "monthly",
      rate_limit_tpm: 10000,
      rate_limit_rpm: 500
    };
    notifications = [
      {
        id: "ntf_001",
        account: "jane.doe",
        type: "api_key_issued",
        title: "API key issued",
        message: "Your pending API key application has been issued.",
        is_read: false,
        created_at: new Date().toISOString(),
        read_at: null,
        metadata: { application_id: "app_mock_001", key_id: "key_001" }
      }
    ];
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
        error_code: null
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
        error_code: "VALIDATION_ERROR"
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
