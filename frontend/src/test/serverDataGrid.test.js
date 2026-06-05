import {
  buildDateRange,
  getServerSort,
  buildTaipeiDateTimeRange,
} from "../utils/serverDataGrid";

test("maps date values to inclusive range params", () => {
  expect(buildDateRange(new Date("2026-05-01T00:00:00"), new Date("2026-05-31T00:00:00"))).toEqual({
    from: "2026-05-01",
    to: "2026-05-31",
  });
});

test("maps Taipei-local date filters to UTC datetime boundaries", () => {
  expect(buildTaipeiDateTimeRange(new Date("2026-05-21T00:00:00"), new Date("2026-05-21T00:00:00"))).toEqual({
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
