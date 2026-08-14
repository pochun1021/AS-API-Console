export const APP_BASE = (import.meta.env.BASE_URL || "/dev/").replace(/\/$/u, "");

export function appPath(path = "") {
  return `${APP_BASE}${path}`;
}
