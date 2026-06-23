import { httpApiProvider } from "./httpApiProvider";

const INSTITUTE_COOLDOWN_PARAM = "mockInstituteCooldown";
const INSTITUTE_COOLDOWN_SECONDS_PARAM = "mockInstituteCooldownSeconds";
const DEFAULT_MOCK_COOLDOWN_SECONDS = 75;
const LOCAL_DEBUG_HOSTS = new Set(["localhost", "127.0.0.1", "::1"]);

function resolveProviderKey() {
  const raw = import.meta.env.VITE_API_PROVIDER;
  return (raw || "real").toLowerCase();
}

function resolveProvider() {
  const key = resolveProviderKey();
  if (key === "real") return httpApiProvider;
  if (import.meta.env.DEV) {
    // eslint-disable-next-line no-console
    console.warn(`[apiClient] Unsupported VITE_API_PROVIDER="${key}", fallback to real`);
  }
  return httpApiProvider;
}

let provider = resolveProvider();

if (import.meta.env.DEV) {
  // eslint-disable-next-line no-console
  console.log(`[apiClient] provider=${resolveProviderKey()}`);
}

let instituteCooldownMockState = null;

function canUseInstituteCooldownMock() {
  if (typeof window === "undefined") return false;
  if (import.meta.env.DEV) return true;
  return LOCAL_DEBUG_HOSTS.has(window.location.hostname);
}

function resolveInstituteCooldownSeconds(search) {
  if (!canUseInstituteCooldownMock()) return 0;
  const params = new URLSearchParams(search);
  const explicitSeconds = params.get(INSTITUTE_COOLDOWN_SECONDS_PARAM);
  if (explicitSeconds != null) {
    const parsedExplicitSeconds = Number.parseInt(explicitSeconds, 10);
    return Number.isFinite(parsedExplicitSeconds) && parsedExplicitSeconds > 0
      ? parsedExplicitSeconds
      : DEFAULT_MOCK_COOLDOWN_SECONDS;
  }
  const rawValue = params.get(INSTITUTE_COOLDOWN_PARAM);
  if (rawValue == null) return 0;
  if (rawValue === "" || rawValue === "1" || rawValue.toLowerCase() === "true") {
    return DEFAULT_MOCK_COOLDOWN_SECONDS;
  }
  const parsed = Number.parseInt(rawValue, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_MOCK_COOLDOWN_SECONDS;
}

function getInstituteCooldownMockState() {
  if (!canUseInstituteCooldownMock()) return null;
  const search = window.location.search;
  const retryAfterSeconds = resolveInstituteCooldownSeconds(search);
  if (retryAfterSeconds <= 0) {
    instituteCooldownMockState = null;
    return null;
  }
  if (instituteCooldownMockState?.search === search) {
    return instituteCooldownMockState;
  }
  instituteCooldownMockState = {
    search,
    retryAfterSeconds,
    expiresAtMs: Date.now() + retryAfterSeconds * 1000
  };
  return instituteCooldownMockState;
}

function buildInstituteCooldownPayload() {
  const state = getInstituteCooldownMockState();
  if (!state) {
    return {
      retry_after_seconds: 0,
      next_allowed_at: null
    };
  }
  const remainingSeconds = Math.max(0, Math.ceil((state.expiresAtMs - Date.now()) / 1000));
  const nextAllowedAt = new Date(state.expiresAtMs).toISOString();
  return {
    retry_after_seconds: remainingSeconds,
    next_allowed_at: nextAllowedAt
  };
}

function buildInstituteCooldownInstitutesPayload() {
  return {
    items: [],
    total: 0
  };
}

function shouldMockInstituteCooldown() {
  return getInstituteCooldownMockState() !== null;
}

function createInstituteCooldownError() {
  const payload = buildInstituteCooldownPayload();
  const error = new Error("institute sync is cooling down");
  error.status = 429;
  error.payload = {
    error: {
      code: "INSTITUTE_SYNC_COOLDOWN",
      message: "institute sync is cooling down"
    },
    ...payload
  };
  return error;
}

export function setApiProvider(nextProvider) {
  provider = nextProvider;
}

export const apiClient = {
  getCurrentUser: (auth) => provider.getCurrentUser(auth),
  createApplication: (payload, auth) => provider.createApplication(payload, auth),
  listApiKeys: (paramsOrAuth, maybeAuth) => provider.listApiKeys(paramsOrAuth, maybeAuth),
  listApiKeyUsageSeries: (params, auth) => provider.listApiKeyUsageSeries(params, auth),
  getApiKeyUsageTotal: (auth) => provider.getApiKeyUsageTotal(auth),
  getApiKeyById: (id, auth) => provider.getApiKeyById(id, auth),
  updateApiKey: (id, payload, auth) => provider.updateApiKey(id, payload, auth),
  revokeApiKey: (id, auth) => provider.revokeApiKey(id, auth),
  renewApiKey: (id, auth) => provider.renewApiKey(id, auth),
  extendApiKey: (id, auth) => provider.extendApiKey(id, auth),
  listApiKeyUserStatistics: (params, auth) => provider.listApiKeyUserStatistics(params, auth),
  listOperationAuditLogs: (params, auth) => provider.listOperationAuditLogs(params, auth),
  listAuthAuditLogs: (params, auth) => provider.listAuthAuditLogs(params, auth),
  listSchedulerLogs: (params, auth) => provider.listSchedulerLogs(params, auth),
  listAdmins: (paramsOrAuth, maybeAuth) => provider.listAdmins(paramsOrAuth, maybeAuth),
  listAnnouncements: (paramsOrAuth, maybeAuth) => provider.listAnnouncements(paramsOrAuth, maybeAuth),
  listInstitutes: (auth) => {
    if (shouldMockInstituteCooldown()) {
      return Promise.resolve(buildInstituteCooldownInstitutesPayload());
    }
    return provider.listInstitutes(auth);
  },
  getInstituteSyncStatus: (auth) => {
    if (shouldMockInstituteCooldown()) {
      return Promise.resolve({
        status: "idle",
        ...buildInstituteCooldownPayload()
      });
    }
    return provider.getInstituteSyncStatus(auth);
  },
  listModels: (auth) => provider.listModels(auth),
  syncInstitutes: (auth) => {
    if (shouldMockInstituteCooldown()) {
      return Promise.reject(createInstituteCooldownError());
    }
    return provider.syncInstitutes(auth);
  },
  searchUsers: (keyword, auth, options) => provider.searchUsers(keyword, auth, options),
  createAdmin: (id, payload, auth) => provider.createAdmin(id, payload, auth),
  enableAdmin: (id, auth) => provider.enableAdmin(id, auth),
  disableAdmin: (id, auth) => provider.disableAdmin(id, auth),
  deleteAdmin: (id, auth) => provider.deleteAdmin(id, auth),
  createAnnouncement: (payload, auth) => provider.createAnnouncement(payload, auth),
  updateAnnouncement: (id, payload, auth) => provider.updateAnnouncement(id, payload, auth),
  deleteAnnouncement: (id, auth) => provider.deleteAnnouncement(id, auth),
  getLocalePreference: (auth) => provider.getLocalePreference(auth),
  updateLocalePreference: (preferredLocale, auth) => provider.updateLocalePreference(preferredLocale, auth),
  listWhitelists: (paramsOrAuth, maybeAuth) => provider.listWhitelists(paramsOrAuth, maybeAuth),
  createWhitelist: (payload, auth) => provider.createWhitelist(payload, auth),
  updateWhitelist: (id, payload, auth) => provider.updateWhitelist(id, payload, auth),
  deleteWhitelist: (id, auth) => provider.deleteWhitelist(id, auth),
  getLimitStrategyConfig: (auth) => provider.getLimitStrategyConfig(auth),
  updateLimitStrategyConfig: (payload, auth) => provider.updateLimitStrategyConfig(payload, auth),
  listPendingApplications: (auth) => provider.listPendingApplications(auth),
  issueApplication: (id, auth) => provider.issueApplication(id, auth),
  logout: (auth) => provider.logout(auth)
};
