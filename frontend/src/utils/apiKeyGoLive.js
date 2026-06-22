export const API_KEY_APPLICATION_GO_LIVE_AT = "2026-06-30T00:00:00+08:00";

export function parseApiKeyApplicationGoLiveAt(rawValue) {
  const parsed = new Date(rawValue || API_KEY_APPLICATION_GO_LIVE_AT);
  if (!Number.isNaN(parsed.getTime())) {
    return parsed;
  }
  return new Date(API_KEY_APPLICATION_GO_LIVE_AT);
}

export function getApiKeyApplicationCountdown(goLiveAt, now = new Date()) {
  const diffMs = goLiveAt.getTime() - now.getTime();
  if (diffMs <= 0) {
    return {
      isLive: true,
      days: 0,
      hours: 0,
      minutes: 0,
      seconds: 0,
    };
  }

  const totalSeconds = Math.floor(diffMs / 1000);
  return {
    isLive: false,
    days: Math.floor(totalSeconds / 86400),
    hours: Math.floor((totalSeconds % 86400) / 3600),
    minutes: Math.floor((totalSeconds % 3600) / 60),
    seconds: totalSeconds % 60,
  };
}

export function formatApiKeyApplicationGoLiveAt(goLiveAt, locale) {
  return new Intl.DateTimeFormat(locale === "zh-TW" ? "zh-TW" : "en-US", {
    timeZone: "Asia/Taipei",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(goLiveAt);
}
