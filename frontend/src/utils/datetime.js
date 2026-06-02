const DISPLAY_TIME_ZONE = "Asia/Taipei";

function normalizeLocale(locale) {
  return locale === "zh-TW" ? "zh-TW" : "en-US";
}

function getPart(parts, type) {
  return parts.find((part) => part.type === type)?.value || "";
}

export function formatDateTimeInTaipei(value, { locale = "zh-TW", fallback = "-", showSeconds = true } = {}) {
  if (!value) return fallback;

  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return fallback;

  const parts = new Intl.DateTimeFormat(normalizeLocale(locale), {
    timeZone: DISPLAY_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: showSeconds ? "2-digit" : undefined,
    hour12: false
  }).formatToParts(dt);

  const year = getPart(parts, "year");
  const month = getPart(parts, "month");
  const day = getPart(parts, "day");
  const hour = getPart(parts, "hour");
  const minute = getPart(parts, "minute");
  const second = getPart(parts, "second");

  return showSeconds
    ? `${year}-${month}-${day} ${hour}:${minute}:${second}`
    : `${year}-${month}-${day} ${hour}:${minute}`;
}

export { DISPLAY_TIME_ZONE };
