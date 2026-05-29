import { httpApiProvider } from "./httpApiProvider";

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

export function setApiProvider(nextProvider) {
  provider = nextProvider;
}

export const apiClient = {
  getCurrentUser: (auth) => provider.getCurrentUser(auth),
  createApplication: (payload, auth) => provider.createApplication(payload, auth),
  listApiKeys: (paramsOrAuth, maybeAuth) => provider.listApiKeys(paramsOrAuth, maybeAuth),
  getApiKeyById: (id, auth) => provider.getApiKeyById(id, auth),
  updateApiKey: (id, payload, auth) => provider.updateApiKey(id, payload, auth),
  revokeApiKey: (id, auth) => provider.revokeApiKey(id, auth),
  renewApiKey: (id, auth) => provider.renewApiKey(id, auth),
  extendApiKey: (id, payload, auth) => provider.extendApiKey(id, payload, auth),
  listApiKeyUserStatistics: (params, auth) => provider.listApiKeyUserStatistics(params, auth),
  listOperationAuditLogs: (params, auth) => provider.listOperationAuditLogs(params, auth),
  listAuthAuditLogs: (params, auth) => provider.listAuthAuditLogs(params, auth),
  listAdmins: (auth) => provider.listAdmins(auth),
  listInstitutes: (auth) => provider.listInstitutes(auth),
  syncInstitutes: (auth) => provider.syncInstitutes(auth),
  searchUsers: (keyword, auth) => provider.searchUsers(keyword, auth),
  enableAdmin: (id, auth) => provider.enableAdmin(id, auth),
  disableAdmin: (id, auth) => provider.disableAdmin(id, auth),
  getLocalePreference: (auth) => provider.getLocalePreference(auth),
  updateLocalePreference: (preferredLocale, auth) => provider.updateLocalePreference(preferredLocale, auth),
  listWhitelists: (auth) => provider.listWhitelists(auth),
  createWhitelist: (payload, auth) => provider.createWhitelist(payload, auth),
  updateWhitelist: (id, payload, auth) => provider.updateWhitelist(id, payload, auth),
  getLimitStrategyConfig: (auth) => provider.getLimitStrategyConfig(auth),
  updateLimitStrategyConfig: (payload, auth) => provider.updateLimitStrategyConfig(payload, auth),
  listPendingApplications: (auth) => provider.listPendingApplications(auth),
  issueApplication: (id, auth) => provider.issueApplication(id, auth),
  logout: (auth) => provider.logout(auth)
};
