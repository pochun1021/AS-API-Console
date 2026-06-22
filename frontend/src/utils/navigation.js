import { isApiKeyApplicationLive, parseApiKeyApplicationGoLiveAt } from "./apiKeyGoLive";

export function proceedToLogin() {
  if (typeof window !== "undefined") {
    window.location.assign("/main/login");
  }
}

export function redirectToLogin() {
  if (typeof window === "undefined") {
    return;
  }

  const goLiveAt = parseApiKeyApplicationGoLiveAt();
  const nextPath = isApiKeyApplicationLive(goLiveAt) ? "/main/login" : "/main/login-coming-soon";
  window.location.assign(nextPath);
}
