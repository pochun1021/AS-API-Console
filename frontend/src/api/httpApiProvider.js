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
    return {
      ...body,
      retry_after_seconds:
        typeof body?.retry_after_seconds === "number" ? body.retry_after_seconds : undefined,
      next_allowed_at:
        typeof body?.next_allowed_at === "string" ? body.next_allowed_at : undefined
    };
  }

  return {
    error: {
      code: status >= 500 ? "INTERNAL_ERROR" : "REQUEST_FAILED",
      message: body?.message || ""
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
    const error = new Error(data?.error?.message || "");
    error.status = response.status;
    error.payload = mapErrorPayload(response.status, data);
    error.retryAfter = response.headers.get("retry-after");
    throw error;
  }

  return data;
}

function mapWhitelistItem(item) {
  return {
    ...item,
    note: item.note || ""
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
    if (params.owner_name) query.set("owner_name", params.owner_name);
    if (params.key_alias) query.set("key_alias", params.key_alias);
    if (params.application_date_from) query.set("application_date_from", params.application_date_from);
    if (params.application_date_to) query.set("application_date_to", params.application_date_to);
    if (params.expires_from) query.set("expires_from", params.expires_from);
    if (params.expires_to) query.set("expires_to", params.expires_to);
    if (params.from) query.set("from", params.from);
    if (params.to) query.set("to", params.to);
    if (params.sort_by) query.set("sort_by", params.sort_by);
    if (params.sort_dir) query.set("sort_dir", params.sort_dir);
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
  extendApiKey(id, auth) {
    return request(apiPath(`/api-keys/${id}/extend`), { method: "POST", auth });
  },

  listApiKeyUserStatistics(params, auth) {
    const query = new URLSearchParams();
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    if (params.q) query.set("q", params.q);
    if (params.scope) query.set("scope", params.scope);
    if (params.from) query.set("from", params.from);
    if (params.to) query.set("to", params.to);
    if (params.owner_account) query.set("owner_account", params.owner_account);
    if (params.owner_name) query.set("owner_name", params.owner_name);
    if (params.owner_email) query.set("owner_email", params.owner_email);
    if (params.owner_department) query.set("owner_department", params.owner_department);
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
    if (params?.action) query.set("action", params.action);
    if (params?.result) query.set("result", params.result);
    if (params?.actor_account) query.set("actor_account", params.actor_account);
    if (params?.target_type) query.set("target_type", params.target_type);
    if (params?.target_id) query.set("target_id", params.target_id);
    if (params?.error_code) query.set("error_code", params.error_code);
    if (params?.sort_by) query.set("sort_by", params.sort_by);
    if (params?.sort_dir) query.set("sort_dir", params.sort_dir);
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
    if (params?.account) query.set("account", params.account);
    if (params?.sysid != null) query.set("sysid", String(params.sysid));
    if (params?.role) query.set("role", params.role);
    if (params?.error_code) query.set("error_code", params.error_code);
    if (params?.request_id) query.set("request_id", params.request_id);
    if (params?.sort_by) query.set("sort_by", params.sort_by);
    if (params?.sort_dir) query.set("sort_dir", params.sort_dir);
    return request(`${apiPath("/auth-audit-logs")}?${query.toString()}`, { auth });
  },

  async listAdmins(paramsOrAuth, maybeAuth) {
    const hasAuthHeaderShape = Boolean(paramsOrAuth?.account && paramsOrAuth?.email && paramsOrAuth?.sysid);
    const auth = hasAuthHeaderShape ? paramsOrAuth : maybeAuth;
    const params = hasAuthHeaderShape ? {} : paramsOrAuth || {};
    const query = new URLSearchParams();
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    if (params.status) query.set("status", params.status);
    if (params.sysid != null) query.set("sysid", String(params.sysid));
    if (params.account) query.set("account", params.account);
    if (params.name) query.set("name", params.name);
    if (params.email) query.set("email", params.email);
    if (params.created_from) query.set("created_from", params.created_from);
    if (params.created_to) query.set("created_to", params.created_to);
    if (params.updated_from) query.set("updated_from", params.updated_from);
    if (params.updated_to) query.set("updated_to", params.updated_to);
    if (params.sort_by) query.set("sort_by", params.sort_by);
    if (params.sort_dir) query.set("sort_dir", params.sort_dir);
    return request(`${apiPath("/admins")}?${query.toString()}`, { auth });
  },

  async listAnnouncements(paramsOrAuth, maybeAuth) {
    const hasAuthHeaderShape = Boolean(paramsOrAuth?.account && paramsOrAuth?.email && paramsOrAuth?.sysid);
    const auth = hasAuthHeaderShape ? paramsOrAuth : maybeAuth;
    const params = hasAuthHeaderShape ? {} : paramsOrAuth || {};
    const query = new URLSearchParams();
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    if (params.scope) query.set("scope", params.scope);
    if (params.status) query.set("status", params.status);
    if (params.title) query.set("title", params.title);
    if (params.publish_from_from) query.set("publish_from_from", params.publish_from_from);
    if (params.publish_from_to) query.set("publish_from_to", params.publish_from_to);
    if (params.publish_to_from) query.set("publish_to_from", params.publish_to_from);
    if (params.publish_to_to) query.set("publish_to_to", params.publish_to_to);
    if (params.updated_from) query.set("updated_from", params.updated_from);
    if (params.updated_to) query.set("updated_to", params.updated_to);
    if (params.sort_by) query.set("sort_by", params.sort_by);
    if (params.sort_dir) query.set("sort_dir", params.sort_dir);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request(`${apiPath("/announcements")}${suffix}`, { auth });
  },

  listInstitutes(auth) {
    return request(apiPath("/institutes"), { auth });
  },

  getInstituteSyncStatus(auth) {
    return request(apiPath("/institutes/sync-status"), { auth });
  },

  listModels(auth) {
    return request(apiPath("/models"), { auth });
  },

  syncInstitutes(auth) {
    return request(apiPath("/institutes/sync"), { method: "POST", auth });
  },

  searchUsers(keyword, auth, options = {}) {
    const query = new URLSearchParams();
    query.set("q", String(keyword || ""));
    if (options.lookup_context) query.set("lookup_context", options.lookup_context);
    return request(`${apiPath("/users")}?${query.toString()}`, { auth });
  },

  enableAdmin(id, auth) {
    return request(apiPath(`/admins/${id}/enable`), { method: "POST", auth });
  },

  createAdmin(id, payload, auth) {
    return request(apiPath(`/admins/${id}`), { method: "PUT", auth, body: payload });
  },

  disableAdmin(id, auth) {
    return request(apiPath(`/admins/${id}/disable`), { method: "POST", auth });
  },

  deleteAdmin(id, auth) {
    return request(apiPath(`/admins/${id}`), { method: "DELETE", auth });
  },

  createAnnouncement(payload, auth) {
    return request(apiPath("/announcements"), {
      method: "POST",
      auth,
      body: payload
    });
  },

  updateAnnouncement(id, payload, auth) {
    return request(apiPath(`/announcements/${id}`), {
      method: "PATCH",
      auth,
      body: payload
    });
  },

  deleteAnnouncement(id, auth) {
    return request(apiPath(`/announcements/${id}`), {
      method: "DELETE",
      auth
    });
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

  async listWhitelists(paramsOrAuth, maybeAuth) {
    const hasAuthHeaderShape = Boolean(paramsOrAuth?.account && paramsOrAuth?.email && paramsOrAuth?.sysid);
    const auth = hasAuthHeaderShape ? paramsOrAuth : maybeAuth;
    const params = hasAuthHeaderShape ? {} : paramsOrAuth || {};
    const query = new URLSearchParams();
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    if (params.status) query.set("status", params.status);
    if (params.sysid) query.set("sysid", String(params.sysid));
    if (params.account) query.set("account", params.account);
    if (params.name) query.set("name", params.name);
    if (params.email) query.set("email", params.email);
    if (params.created_from) query.set("created_from", params.created_from);
    if (params.created_to) query.set("created_to", params.created_to);
    if (params.updated_from) query.set("updated_from", params.updated_from);
    if (params.updated_to) query.set("updated_to", params.updated_to);
    if (params.sort_by) query.set("sort_by", params.sort_by);
    if (params.sort_dir) query.set("sort_dir", params.sort_dir);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    const result = await request(`${apiPath("/whitelists")}${suffix}`, { auth });
    return { ...result, items: result.items.map(mapWhitelistItem) };
  },

  createWhitelist(payload, auth) {
    return request(apiPath("/whitelists"), {
      method: "POST",
      auth,
      body: {
        sysid: payload.sysid,
        account: payload.account,
        name: payload.name,
        email: payload.email,
        note: payload.note || null
      }
    }).then(mapWhitelistItem);
  },

  updateWhitelist(id, payload, auth) {
    return request(apiPath(`/whitelists/${id}`), {
      method: "PATCH",
      auth,
      body: {
        status: payload.status || "active",
        note: payload.note || null
      }
    }).then(mapWhitelistItem);
  },

  deleteWhitelist(id, auth) {
    return request(apiPath(`/whitelists/${id}`), {
      method: "DELETE",
      auth
    });
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
