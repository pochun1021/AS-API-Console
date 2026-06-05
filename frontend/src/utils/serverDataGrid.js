function normalizeDateValue(value) {
  if (!value) return "";
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}/.test(value)) {
    return value.slice(0, 10);
  }

  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "";

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function buildDateRange(fromValue, toValue) {
  return {
    from: normalizeDateValue(fromValue),
    to: normalizeDateValue(toValue),
  };
}

export function buildTaipeiDateTimeRange(fromValue, toValue) {
  const dateRange = buildDateRange(fromValue, toValue);
  return {
    from: dateRange.from ? new Date(`${dateRange.from}T00:00:00+08:00`).toISOString() : "",
    to: dateRange.to ? new Date(`${dateRange.to}T23:59:59.999+08:00`).toISOString() : "",
  };
}

export function getServerSort(sortModel, fallback) {
  const [primarySort] = Array.isArray(sortModel) ? sortModel : [];
  if (!primarySort?.field || !primarySort?.sort) return fallback;
  return { field: primarySort.field, sort: primarySort.sort };
}
