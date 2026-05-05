import { mockApiProvider } from "../mocks/mockApiProvider";

let provider = mockApiProvider;

export function setApiProvider(nextProvider) {
  provider = nextProvider;
}

export const apiClient = {
  createApplication: (payload, auth) => provider.createApplication(payload, auth),
  listApiKeys: (auth) => provider.listApiKeys(auth),
  revokeApiKey: (id, auth) => provider.revokeApiKey(id, auth)
};
