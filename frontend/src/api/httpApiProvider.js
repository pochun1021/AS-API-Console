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
  const response = await fetch(path, {
    method,
    headers: buildHeaders(auth),
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

  listApiKeys(auth) {
    return request("/api/v1/api-keys", { auth });
  },

  getApiKeyById(id, auth) {
    return request(`/api/v1/api-keys/${id}`, { auth }).then((item) => ({ item }));
  },

  revokeApiKey(id, auth) {
    return request(`/api/v1/api-keys/${id}/revoke`, { method: "POST", auth });
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

  async listWhitelists(auth) {
    const result = await request("/api/v1/whitelists", { auth });
    return { ...result, items: result.items.map(mapWhitelistItem) };
  },

  createWhitelist(payload, auth) {
    return request("/api/v1/whitelists", {
      method: "POST",
      auth,
      body: { email: payload.email, note: payload.remark || null }
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
  }
};
