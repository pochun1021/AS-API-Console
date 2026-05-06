import { httpApiProvider } from "./httpApiProvider";
import { mockApiProvider } from "../mocks/mockApiProvider";

const providerByKey = {
  real: httpApiProvider,
  mock: mockApiProvider
};

function resolveProvider() {
  const key = (import.meta.env.VITE_API_PROVIDER || "mock").toLowerCase();
  const resolved = providerByKey[key];
  if (resolved) {
    return resolved;
  }
  if (import.meta.env.DEV) {
    // eslint-disable-next-line no-console
    console.warn(`[apiClient] Unknown VITE_API_PROVIDER="${key}", fallback to mock`);
  }
  return mockApiProvider;
}

let provider = resolveProvider();

export function setApiProvider(nextProvider) {
  provider = nextProvider;
}

export const apiClient = {
  createApplication: (payload, auth) => provider.createApplication(payload, auth),
  listApiKeys: (auth) => provider.listApiKeys(auth),
  getApiKeyById: (id, auth) => provider.getApiKeyById(id, auth),
  revokeApiKey: (id, auth) => provider.revokeApiKey(id, auth),
  listUsers: (auth) => provider.listUsers(auth),
  searchUsers: (keyword, auth) => provider.searchUsers(keyword, auth),
  grantAdmin: (id, auth) => provider.grantAdmin(id, auth),
  revokeAdmin: (id, auth) => provider.revokeAdmin(id, auth),
  listWhitelists: (auth) => provider.listWhitelists(auth),
  createWhitelist: (payload, auth) => provider.createWhitelist(payload, auth),
  updateWhitelist: (id, payload, auth) => provider.updateWhitelist(id, payload, auth)
};
