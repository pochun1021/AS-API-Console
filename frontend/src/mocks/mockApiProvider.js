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
  }
];

const initialUsers = [
  {
    id: "usr_001",
    account: "jane.doe",
    sysid: "user_123",
    name: "Jane Doe",
    email: "jane.doe@company.com",
    role: "user"
  },
  {
    id: "usr_002",
    account: "john.admin",
    sysid: "admin_001",
    name: "John Admin",
    email: "john.admin@company.com",
    role: "admin"
  },
  {
    id: "usr_003",
    account: "alice.wang",
    sysid: "user_456",
    name: "Alice Wang",
    email: "alice.wang@company.com",
    role: "user"
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
    throw createError("APPLICANT_NOT_WHITELISTED", "Email 不在可申請白名單中", 403);
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

    return { items };
  },

  async listUsers(auth) {
    await delay();
    ensureAdmin(auth);
    return { items: users };
  },

  async grantAdmin(id, auth) {
    await delay();
    ensureAdmin(auth);
    const user = findUserById(id);
    if (!user) {
      throw createError("USER_NOT_FOUND", "使用者不存在", 404);
    }
    user.role = "admin";
    return { item: user };
  },

  async revokeAdmin(id, auth) {
    await delay();
    ensureAdmin(auth);
    const user = findUserById(id);
    if (!user) {
      throw createError("USER_NOT_FOUND", "使用者不存在", 404);
    }
    if (user.sysid === auth.sysid) {
      throw createError("VALIDATION_ERROR", "不可取消自己的管理者權限");
    }
    user.role = "user";
    return { item: user };
  },

  async createWhitelist(payload, auth) {
    await delay();
    ensureAdmin(auth);

    const email = payload.email?.trim().toLowerCase();
    if (!email || !/^\S+@\S+\.\S+$/.test(email)) {
      throw createError("VALIDATION_ERROR", "Email 格式不正確");
    }

    if (whitelists.some((item) => item.email.toLowerCase() === email)) {
      throw createError("WHITELIST_EMAIL_DUPLICATED", "Email 已存在於白名單");
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
