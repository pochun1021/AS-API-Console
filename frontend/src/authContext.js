export const devAuthProfiles = {
  admin: {
    account: "abcd1234",
    name: "abcd1234",
    email: "s880632520@gmail.com",
    department: "02",
    sysid: 100001,
    role: "admin"
  },
  user: {
    account: "pochen",
    name: "Pochen",
    email: "pochen@as.edu.tw",
    department: "02",
    sysid: 200001,
    role: "user"
  }
};

const OAUTH_AUTH_STORAGE_KEY = "as-api-console-auth-context";

function normalizeAuthCandidate(candidate) {
  if (!candidate || typeof candidate !== "object") {
    return null;
  }

  const role = candidate.role === "admin" ? "admin" : candidate.role === "user" ? "user" : null;
  if (!role) {
    return null;
  }

  const requiredFields = ["account", "name", "email", "department"];
  for (const key of requiredFields) {
    if (!candidate[key] || typeof candidate[key] !== "string") return null;
  }
  const numericSysid =
    typeof candidate.sysid === "number"
      ? candidate.sysid
      : typeof candidate.sysid === "string" && /^\d+$/.test(candidate.sysid)
        ? Number(candidate.sysid)
        : null;
  if (!numericSysid || numericSysid <= 0) return null;

  return {
    account: candidate.account,
    name: candidate.name,
    email: candidate.email,
    department: candidate.department,
    sysid: numericSysid,
    role
  };
}

function readStoredOAuthAuth() {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const raw = window.sessionStorage.getItem(OAUTH_AUTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return normalizeAuthCandidate(parsed);
  } catch {
    return null;
  }
}

export function readOAuthAuthContext() {
  if (typeof window === "undefined") {
    return null;
  }

  const fromWindow = normalizeAuthCandidate(window.__AS_AUTH_CONTEXT__);
  if (fromWindow) {
    return fromWindow;
  }

  return readStoredOAuthAuth();
}

export function clearOAuthAuthContext() {
  if (typeof window === "undefined") {
    return;
  }
  window.sessionStorage.removeItem(OAUTH_AUTH_STORAGE_KEY);
  if ("__AS_AUTH_CONTEXT__" in window) {
    try {
      delete window.__AS_AUTH_CONTEXT__;
    } catch {
      window.__AS_AUTH_CONTEXT__ = undefined;
    }
  }
}
