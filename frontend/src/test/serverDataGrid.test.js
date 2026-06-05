import {
  getContainsFilterValue,
  getDateRangeFilterValues,
  getServerSort,
  getSingleSelectFilterValue,
  getTaipeiDateTimeRangeFilterValues,
} from "../utils/serverDataGrid";

test("extracts contains and single-select filter values", () => {
  const filterModel = {
    items: [
      { field: "owner_account", operator: "contains", value: "ktu" },
      { field: "status", operator: "is", value: "active" },
    ],
  };

  expect(getContainsFilterValue(filterModel, "owner_account")).toBe("ktu");
  expect(getSingleSelectFilterValue(filterModel, "status")).toBe("active");
});

test("maps date filters to inclusive range params", () => {
  const filterModel = {
    items: [
      { field: "application_date", operator: "onOrAfter", value: new Date("2026-05-01T00:00:00") },
      { field: "application_date", operator: "onOrBefore", value: new Date("2026-05-31T00:00:00") },
    ],
  };

  expect(getDateRangeFilterValues(filterModel, "application_date")).toEqual({
    from: "2026-05-01",
    to: "2026-05-31",
  });
});

test("maps Taipei-local date filters to UTC datetime boundaries", () => {
  const filterModel = {
    items: [{ field: "expires_at", operator: "is", value: new Date("2026-05-21T00:00:00") }],
  };

  expect(getTaipeiDateTimeRangeFilterValues(filterModel, "expires_at")).toEqual({
    from: "2026-05-20T16:00:00.000Z",
    to: "2026-05-21T15:59:59.999Z",
  });
});

test("falls back to default server sort when sort model is empty", () => {
  expect(getServerSort([], { field: "created_at", sort: "desc" })).toEqual({
    field: "created_at",
    sort: "desc",
  });
});
