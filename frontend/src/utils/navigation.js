import { isApiKeyApplicationLive, parseApiKeyApplicationGoLiveAt } from "./apiKeyGoLive";
import { appPath } from "../runtimePath";

export function proceedToLogin() {
  if (typeof window !== "undefined") {
    window.location.assign(appPath("/login"));
  }
}

export function redirectToLogin() {
  if (typeof window === "undefined") {
    return;
  }

  const goLiveAt = parseApiKeyApplicationGoLiveAt();
  const nextPath = isApiKeyApplicationLive(goLiveAt) ? appPath("/login") : appPath("/login-coming-soon");
  window.location.assign(nextPath);
}
