function buildHeaders(auth, method) {
  const headers = {
    "Content-Type": "application/json"
  };
  if (import.meta.env.DEV && auth?.account) {
    headers["x-account"] = auth.account;
    headers["x-name"] = auth.name;
    headers["x-email"] = auth.email;
    headers["x-department"] = auth.department;
    headers["x-sysid"] = String(auth.sysid);
    headers["x-role"] = auth.role || "user";
  }
  if (!["GET", "HEAD", "OPTIONS"].includes(method) && auth?.csrf_token) {
    headers["x-csrf-token"] = auth.csrf_token;
  }
  return headers;
}

function mapErrorPayload(status, body) {
  if (body?.error?.code && body?.error?.message) {
    return body;
  }

  return {
    error: {
      code: status >= 500 ? "INTERNAL_ERROR" : "REQUEST_FAILED",
      message: body?.message || "請求失敗"
    }
  };
}

const APP_BASE = "/main";
const API_BASE = `${APP_BASE}/api/v1`;

function apiPath(path = "") {
  return `${API_BASE}${path}`;
}

async function request(path, { method = "GET", auth, body } = {}) {
  const headers = buildHeaders(auth, method);
  const response = await fetch(path, {
    method,
    headers,
    credentials: "same-origin",
    body: body ? JSON.stringify(body) : undefined
  });

  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { message: text };
    }
  }

  if (!response.ok) {
    const error = new Error(data?.error?.message || "請求失敗");
    error.status = response.status;
    error.payload = mapErrorPayload(response.status, data);
    throw error;
  }

  return data;
}

function mapWhitelistItem(item) {
  return {
    ...item,
    remark: item.note || ""
  };
}

export const httpApiProvider = {
  getCurrentUser(auth) {
    return request(apiPath("/users/me"), { auth });
  },

  createApplication(payload, auth) {
    return request(apiPath("/api-keys/applications"), { method: "POST", auth, body: payload });
  },

  listApiKeys(paramsOrAuth, maybeAuth) {
    const hasAuthHeaderShape = Boolean(paramsOrAuth?.account && paramsOrAuth?.email && paramsOrAuth?.sysid);
    const auth = hasAuthHeaderShape ? paramsOrAuth : maybeAuth;
    const params = hasAuthHeaderShape ? {} : paramsOrAuth || {};
    const query = new URLSearchParams();
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    if (params.status) query.set("status", params.status);
    if (params.owner_account) query.set("owner_account", params.owner_account);
    if (params.from) query.set("from", params.from);
    if (params.to) query.set("to", params.to);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request(`${apiPath("/api-keys")}${suffix}`, { auth });
  },

  getApiKeyById(id, auth) {
    return request(apiPath(`/api-keys/${id}`), { auth }).then((item) => ({ item }));
  },

  updateApiKey(id, payload, auth) {
    return request(apiPath(`/api-keys/${id}`), { method: "PATCH", auth, body: payload }).then((item) => ({ item }));
  },

  revokeApiKey(id, auth) {
    return request(apiPath(`/api-keys/${id}/revoke`), { method: "POST", auth });
  },

  renewApiKey(id, auth) {
    return request(apiPath(`/api-keys/${id}/renew`), { method: "POST", auth });
  },
  extendApiKey(id, payload, auth) {
    return request(apiPath(`/api-keys/${id}/extend`), { method: "POST", auth, body: payload });
  },

  listApiKeyUserStatistics(params, auth) {
    const query = new URLSearchParams();
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    if (params.q) query.set("q", params.q);
    if (params.scope) query.set("scope", params.scope);
    if (params.from) query.set("from", params.from);
    if (params.to) query.set("to", params.to);
    if (params.sort_by) query.set("sort_by", params.sort_by);
    if (params.sort_dir) query.set("sort_dir", params.sort_dir);
    return request(`${apiPath("/api-keys/statistics/users")}?${query.toString()}`, { auth });
  },

  listOperationAuditLogs(params, auth) {
    const query = new URLSearchParams();
    if (params?.page) query.set("page", String(params.page));
    if (params?.page_size) query.set("page_size", String(params.page_size));
    if (params?.from) query.set("from", params.from);
    if (params?.to) query.set("to", params.to);
    if (params?.event_type) query.set("event_type", params.event_type);
    if (params?.result) query.set("result", params.result);
    return request(`${apiPath("/operation-audit-logs")}?${query.toString()}`, { auth });
  },

  listAuthAuditLogs(params, auth) {
    const query = new URLSearchParams();
    if (params?.page) query.set("page", String(params.page));
    if (params?.page_size) query.set("page_size", String(params.page_size));
    if (params?.from) query.set("from", params.from);
    if (params?.to) query.set("to", params.to);
    if (params?.provider) query.set("provider", params.provider);
    if (params?.result) query.set("result", params.result);
    return request(`${apiPath("/auth-audit-logs")}?${query.toString()}`, { auth });
  },

  listAdmins(auth) {
    return request(apiPath("/admins"), { auth });
  },

  listInstitutes(auth) {
    return request(apiPath("/institutes"), { auth });
  },

  syncInstitutes(auth) {
    return request(apiPath("/institutes/sync"), { method: "POST", auth });
  },

  searchUsers(keyword, auth) {
    const q = encodeURIComponent(keyword || "");
    return request(`${apiPath("/users")}?q=${q}`, { auth });
  },

  enableAdmin(id, auth) {
    return request(apiPath(`/admins/${id}/enable`), { method: "POST", auth });
  },

  disableAdmin(id, auth) {
    return request(apiPath(`/admins/${id}/disable`), { method: "POST", auth });
  },

  getLocalePreference(auth) {
    return request(apiPath("/users/preferences/locale"), { auth });
  },

  updateLocalePreference(preferred_locale, auth) {
    return request(apiPath("/users/preferences/locale"), {
      method: "PATCH",
      auth,
      body: { preferred_locale }
    });
  },

  async listWhitelists(auth) {
    const result = await request(apiPath("/whitelists"), { auth });
    return { ...result, items: result.items.map(mapWhitelistItem) };
  },

  createWhitelist(payload, auth) {
    return request(apiPath("/whitelists"), {
      method: "POST",
      auth,
      body: { sysid: payload.sysid, note: payload.remark || null }
    }).then(mapWhitelistItem);
  },

  updateWhitelist(id, payload, auth) {
    return request(apiPath(`/whitelists/${id}`), {
      method: "PATCH",
      auth,
      body: {
        status: payload.status || "active",
        note: payload.remark || null
      }
    }).then(mapWhitelistItem);
  },

  getLimitStrategyConfig(auth) {
    return request(apiPath("/limit-strategy-config"), { auth });
  },

  updateLimitStrategyConfig(payload, auth) {
    return request(apiPath("/limit-strategy-config"), {
      method: "PATCH",
      auth,
      body: payload
    });
  },

  logout(auth) {
    return request(`${APP_BASE}/logout`, { method: "POST", auth });
  },

};
