import { httpApiProvider } from "./httpApiProvider";
import { mockApiProvider } from "../mocks/mockApiProvider";

const providerByKey = {
  real: httpApiProvider,
  mock: mockApiProvider
};

function resolveProviderKey() {
  const raw = import.meta.env.VITE_API_PROVIDER;
  return (raw || "real").toLowerCase();
}

function resolveProvider() {
  const key = resolveProviderKey();
  const resolved = providerByKey[key];
  if (resolved) {
    return resolved;
  }
  if (import.meta.env.DEV) {
    // eslint-disable-next-line no-console
    console.warn(`[apiClient] Unknown VITE_API_PROVIDER="${key}", fallback to real`);
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
  createApplication: (payload, auth) => provider.createApplication(payload, auth),
  listApiKeys: (auth) => provider.listApiKeys(auth),
  getApiKeyById: (id, auth) => provider.getApiKeyById(id, auth),
  updateApiKey: (id, payload, auth) => provider.updateApiKey(id, payload, auth),
  revokeApiKey: (id, auth) => provider.revokeApiKey(id, auth),
  listApiKeyUserStatistics: (params, auth) => provider.listApiKeyUserStatistics(params, auth),
  listUsers: (auth) => provider.listUsers(auth),
  searchUsers: (keyword, auth) => provider.searchUsers(keyword, auth),
  enableAdmin: (id, auth) => provider.enableAdmin(id, auth),
  disableAdmin: (id, auth) => provider.disableAdmin(id, auth),
  getLocalePreference: (auth) => provider.getLocalePreference(auth),
  updateLocalePreference: (preferredLocale, auth) => provider.updateLocalePreference(preferredLocale, auth),
  listWhitelists: (auth) => provider.listWhitelists(auth),
  createWhitelist: (payload, auth) => provider.createWhitelist(payload, auth),
  updateWhitelist: (id, payload, auth) => provider.updateWhitelist(id, payload, auth)
};
