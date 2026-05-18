function buildHeaders(auth) {
  return {
    "Content-Type": "application/json",
    "x-account": auth.account,
    "x-name": auth.name,
    "x-email": auth.email,
    "x-department": auth.department,
    "x-sysid": auth.sysid,
    "x-role": auth.role || "user"
  };
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

async function request(path, { method = "GET", auth, body } = {}) {
  const headers = auth ? buildHeaders(auth) : { "Content-Type": "application/json" };
  const response = await fetch(path, {
    method,
    headers,
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
  createApplication(payload, auth) {
    return request("/api/v1/api-keys/applications", { method: "POST", auth, body: payload });
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
    return request(`/api/v1/api-keys${suffix}`, { auth });
  },

  getApiKeyById(id, auth) {
    return request(`/api/v1/api-keys/${id}`, { auth }).then((item) => ({ item }));
  },

  updateApiKey(id, payload, auth) {
    return request(`/api/v1/api-keys/${id}`, { method: "PATCH", auth, body: payload }).then((item) => ({ item }));
  },

  revokeApiKey(id, auth) {
    return request(`/api/v1/api-keys/${id}/revoke`, { method: "POST", auth });
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
    return request(`/api/v1/api-keys/statistics/users?${query.toString()}`, { auth });
  },

  listUsers(auth) {
    return request("/api/v1/users", { auth });
  },

  searchUsers(keyword, auth) {
    const q = encodeURIComponent(keyword || "");
    return request(`/api/v1/users?q=${q}`, { auth });
  },

  enableAdmin(id, auth) {
    return request(`/api/v1/admins/${id}/enable`, { method: "POST", auth });
  },

  disableAdmin(id, auth) {
    return request(`/api/v1/admins/${id}/disable`, { method: "POST", auth });
  },

  getLocalePreference(auth) {
    return request("/api/v1/users/preferences/locale", { auth });
  },

  updateLocalePreference(preferred_locale, auth) {
    return request("/api/v1/users/preferences/locale", {
      method: "PATCH",
      auth,
      body: { preferred_locale }
    });
  },

  async listWhitelists(auth) {
    const result = await request("/api/v1/whitelists", { auth });
    return { ...result, items: result.items.map(mapWhitelistItem) };
  },

  createWhitelist(payload, auth) {
    return request("/api/v1/whitelists", {
      method: "POST",
      auth,
      body: { sysid: payload.sysid, note: payload.remark || null }
    }).then(mapWhitelistItem);
  },

  updateWhitelist(id, payload, auth) {
    return request(`/api/v1/whitelists/${id}`, {
      method: "PATCH",
      auth,
      body: {
        status: payload.status || "active",
        note: payload.remark || null
      }
    }).then(mapWhitelistItem);
  },

  getLimitStrategyConfig(auth) {
    return request("/api/v1/limit-strategy-config", { auth });
  },

  updateLimitStrategyConfig(payload, auth) {
    return request("/api/v1/limit-strategy-config", {
      method: "PATCH",
      auth,
      body: payload
    });
  },

  listPendingApplications(auth) {
    return request("/api/v1/api-keys/applications/pending", { auth });
  },

  updateApplicationIssuanceMode(id, mode, auth) {
    return request(`/api/v1/api-keys/applications/${id}/issuance-mode`, {
      method: "PATCH",
      auth,
      body: { mode }
    });
  },

  issueApplication(id, auth) {
    return request(`/api/v1/api-keys/applications/${id}/issue`, {
      method: "POST",
      auth
    });
  },

  listNotifications(params, auth) {
    const query = new URLSearchParams();
    if (params?.page) query.set("page", String(params.page));
    if (params?.page_size) query.set("page_size", String(params.page_size));
    if (typeof params?.is_read === "boolean") query.set("is_read", String(params.is_read));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request(`/api/v1/notifications${suffix}`, { auth });
  },

  markNotificationRead(id, auth) {
    return request(`/api/v1/notifications/${id}/read`, { method: "PATCH", auth });
  },

  logout() {
    return request("/logout", { method: "POST" });
  },

};
