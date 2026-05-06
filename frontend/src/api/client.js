import { mockApiProvider } from "../mocks/mockApiProvider";

let provider = mockApiProvider;

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
