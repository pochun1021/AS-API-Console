const today = new Date().toISOString().slice(0, 10);

let apiKeys = [
  {
    id: "key_001",
    status: "active",
    masked_key: "ab12****xy90",
    key_prefix: "ab12cd",
    application_date: today,
    duration_months: 6,
    created_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 1000 * 60 * 60 * 24 * 180).toISOString(),
    owner_account: "jane.doe"
  },
  {
    id: "key_002",
    status: "revoked",
    masked_key: "cd34****mn56",
    key_prefix: "cd34ef",
    application_date: today,
    duration_months: 1,
    created_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 1000 * 60 * 60 * 24 * 30).toISOString(),
    owner_account: "jane.doe"
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

  if (auth.email !== "jane.doe@company.com") {
    throw createError("APPLICANT_NOT_WHITELISTED", "Email 不在可申請白名單中", 403);
  }
}

function generatePlainKey() {
  const chars = "abcdefghijklmnopqrstuvwxyz0123456789";
  let key = "";
  for (let i = 0; i < 30; i += 1) {
    key += chars[Math.floor(Math.random() * chars.length)];
  }
  return key;
}

export const mockApiProvider = {
  async createApplication(payload, auth) {
    await delay();
    validateApplication(payload, auth);

    const plain = generatePlainKey();
    const prefix = plain.slice(0, 6);
    const id = `key_${String(apiKeys.length + 1).padStart(3, "0")}`;
    const now = new Date();
    const expires = new Date(now);
    expires.setMonth(expires.getMonth() + payload.duration_months);

    apiKeys = [
      {
        id,
        status: "active",
        masked_key: `${plain.slice(0, 4)}****${plain.slice(-4)}`,
        key_prefix: prefix,
        application_date: payload.application_date,
        duration_months: payload.duration_months,
        created_at: now.toISOString(),
        expires_at: expires.toISOString(),
        owner_account: auth.account
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
    const items = apiKeys.filter((item) => item.owner_account === auth.account);
    return { items, page: 1, page_size: 20, total: items.length };
  },

  async revokeApiKey(id, auth) {
    await delay();
    const target = apiKeys.find((item) => item.id === id);
    if (!target) {
      throw createError("VALIDATION_ERROR", "id not found", 404);
    }
    if (target.owner_account !== auth.account) {
      throw createError("KEY_NOT_OWNED_BY_USER", "key is not owned by user", 403);
    }
    if (target.status !== "active") {
      throw createError("KEY_NOT_ACTIVE", "key is not active");
    }
    target.status = "revoked";
    return { success: true };
  },

  resetForTests() {
    apiKeys = [...apiKeys.map((x) => ({ ...x }))];
  }
};
