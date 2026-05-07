const today = new Date().toISOString().slice(0, 10);

const initialApiKeys = [
  {
    id: "key_001",
    status: "active",
    masked_key: "AS-****xy90",
    key_prefix: "AS-",
    application_date: today,
    duration_months: 6,
    purpose: "integration test for platform service",
    department: "Platform Engineering",
    created_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 1000 * 60 * 60 * 24 * 180).toISOString(),
    owner_account: "jane.doe",
    owner_name: "Jane Doe"
  },
  {
    id: "key_002",
    status: "revoked",
    masked_key: "AS-****mn56",
    key_prefix: "AS-",
    application_date: today,
    duration_months: 1,
    purpose: "legacy integration",
    department: "Platform Engineering",
    created_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 1000 * 60 * 60 * 24 * 30).toISOString(),
    owner_account: "jane.doe",
    owner_name: "Jane Doe"
  },
  {
    id: "key_003",
    status: "active",
    masked_key: "AS-****ab12",
    key_prefix: "AS-",
    application_date: today,
    duration_months: 12,
    purpose: "admin automation",
    department: "Security",
    created_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 1000 * 60 * 60 * 24 * 365).toISOString(),
    owner_account: "john.admin",
    owner_name: "John Admin"
  },
  {
    id: "key_004",
    status: "expired",
    masked_key: "AS-****pq78",
    key_prefix: "AS-",
    application_date: "2025-04-01",
    duration_months: 1,
    created_at: "2025-04-01T08:00:00.000Z",
    expires_at: "2025-05-01T08:00:00.000Z",
    owner_account: "john.admin",
    owner_name: "John Admin"
  },
  {
    id: "key_005",
    status: "active",
    masked_key: "AS-****cd34",
    key_prefix: "AS-",
    application_date: "2026-04-15",
    duration_months: 6,
    purpose: "reporting service integration",
    department: "Data Platform",
    created_at: "2026-04-15T09:30:00.000Z",
    expires_at: "2026-10-15T09:30:00.000Z",
    owner_account: "alice.wang",
    owner_name: "Alice Wang"
  },
  {
    id: "key_006",
    status: "revoked",
    masked_key: "AS-****ef56",
    key_prefix: "AS-",
    application_date: "2026-03-10",
    duration_months: 12,
    purpose: "security scanner",
    department: "Security",
    created_at: "2026-03-10T02:20:00.000Z",
    expires_at: "2027-03-10T02:20:00.000Z",
    owner_account: "sam.chen",
    owner_name: "Sam Chen"
  },
  {
    id: "key_007",
    status: "expired",
    masked_key: "AS-****gh78",
    key_prefix: "AS-",
    application_date: "2025-12-01",
    duration_months: 1,
    purpose: "legacy webhook client",
    department: "Operations",
    created_at: "2025-12-01T05:00:00.000Z",
    expires_at: "2026-01-01T05:00:00.000Z",
    owner_account: "mike.li",
    owner_name: "Mike Li"
  }
];

const initialWhitelists = [
  {
    id: "wl_001",
    email: "jane.doe@company.com",
    account: "jane.doe",
    sysid: "user_123",
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
    sysid: "user_999",
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
    sysid: "user_654",
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
    sysid: "user_789",
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
    sysid: "user_123",
    name: "Jane Doe",
    email: "jane.doe@company.com",
    role: "user",
    status: "active"
  },
  {
    id: "usr_002",
    account: "john.admin",
    sysid: "admin_001",
    name: "John Admin",
    email: "john.admin@company.com",
    role: "admin",
    status: "active"
  },
  {
    id: "usr_003",
    account: "alice.wang",
    sysid: "user_456",
    name: "Alice Wang",
    email: "alice.wang@company.com",
    role: "user",
    status: "active"
  },
  {
    id: "usr_004",
    account: "sam.chen",
    sysid: "user_789",
    name: "Sam Chen",
    email: "sam.chen@company.com",
    role: "user",
    status: "active"
  },
  {
    id: "usr_005",
    account: "mike.li",
    sysid: "user_999",
    name: "Mike Li",
    email: "mike.li@company.com",
    role: "user",
    status: "active"
  }
];

let apiKeys = initialApiKeys.map((item) => ({ ...item }));
let whitelists = initialWhitelists.map((item) => ({ ...item }));
let users = initialUsers.map((item) => ({ ...item }));

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

  const activeWhitelist = whitelists.find((item) => item.email === auth.email && item.status === "active");
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

function mapUserForAdminPage(user) {
  return {
    id: user.id,
    account: user.account,
    sysid: user.sysid,
    name: user.name,
    email: user.email,
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

export const mockApiProvider = {
  async createApplication(payload, auth) {
    await delay();
    validateApplication(payload, auth);

    const plain = generatePlainKey();
    const prefix = "AS-";
    const id = `key_${String(apiKeys.length + 1).padStart(3, "0")}`;
    const now = new Date();
    const expires = new Date(now);
    expires.setMonth(expires.getMonth() + payload.duration_months);

    apiKeys = [
      {
        id,
        status: "active",
        masked_key: `AS-****${plain.slice(-4)}`,
        key_prefix: prefix,
        application_date: payload.application_date,
        duration_months: payload.duration_months,
        purpose: payload.purpose.trim(),
        department: auth.department,
        created_at: now.toISOString(),
        expires_at: expires.toISOString(),
        owner_account: auth.account,
        owner_name: auth.name
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
      api_key_plaintext: plain,
      api_key_prefix: prefix
    };
  },

  async listApiKeys(auth) {
    await delay();
    const items = auth.role === "admin" ? apiKeys : apiKeys.filter((item) => item.owner_account === auth.account);
    return { items, page: 1, page_size: 20, total: items.length };
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

  async getApiKeyById(id, auth) {
    await delay();
    const target = findApiKeyById(id);
    if (!target) {
      throw createError("VALIDATION_ERROR", "id not found", 404);
    }

    if (auth.role !== "admin" && target.owner_account !== auth.account) {
      throw createError("KEY_NOT_OWNED_BY_USER", "key is not owned by user", 403);
    }

    return { item: target };
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
      [item.sysid, item.account, item.name, item.email].some((value) => value.toLowerCase().includes(q))
    );

    return { items: items.map(mapUserForAdminPage) };
  },

  async listUsers(auth) {
    await delay();
    ensureAdmin(auth);
    return { items: users.filter((item) => item.role === "admin").map(mapUserForAdminPage) };
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

  async createWhitelist(payload, auth) {
    await delay();
    ensureAdmin(auth);

    const email = payload.email?.trim().toLowerCase();
    if (!email || !/^\S+@\S+\.\S+$/.test(email)) {
      throw createError("VALIDATION_ERROR", "Email 格式不正確");
    }

    if (whitelists.some((item) => item.email.toLowerCase() === email)) {
      throw createError("WHITELIST_EMAIL_DUPLICATED", "Email 已存在於特殊人員名單");
    }

    const now = new Date().toISOString();
    const item = {
      id: `wl_${String(whitelists.length + 1).padStart(3, "0")}`,
      email,
      account: payload.account || "",
      status: "active",
      remark: payload.remark?.trim() || "",
      sysid: payload.sysid || "",
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

  resetForTests() {
    apiKeys = initialApiKeys.map((item) => ({ ...item }));
    whitelists = initialWhitelists.map((item) => ({ ...item }));
    users = initialUsers.map((item) => ({ ...item }));
  }
};
