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

function getActiveFilterItems(filterModel, field) {
  const items = Array.isArray(filterModel?.items) ? filterModel.items : [];
  return items.filter((item) => item?.field === field && item?.operator && item?.value != null && String(item.value).trim() !== "");
}

export function getContainsFilterValue(filterModel, field) {
  const item = getActiveFilterItems(filterModel, field).find((candidate) => candidate.operator === "contains");
  return item ? String(item.value).trim() : "";
}

export function getSingleSelectFilterValue(filterModel, field) {
  const item = getActiveFilterItems(filterModel, field).find((candidate) => candidate.operator === "is");
  return item ? String(item.value).trim() : "";
}

export function getDateRangeFilterValues(filterModel, field) {
  const result = { from: "", to: "" };
  const items = getActiveFilterItems(filterModel, field);

  for (const item of items) {
    const value = normalizeDateValue(item.value);
    if (!value) continue;

    if (item.operator === "is") {
      result.from = value;
      result.to = value;
    } else if (item.operator === "onOrAfter") {
      result.from = value;
    } else if (item.operator === "onOrBefore") {
      result.to = value;
    }
  }

  return result;
}

export function getTaipeiDateTimeRangeFilterValues(filterModel, field) {
  const dateRange = getDateRangeFilterValues(filterModel, field);
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
