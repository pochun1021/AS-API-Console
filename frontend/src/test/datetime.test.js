import { formatDateTimeInTaipei } from "../utils/datetime";

test("formats UTC timestamp as Asia/Taipei time", () => {
  expect(formatDateTimeInTaipei("2026-03-10T11:00:00.000Z")).toBe("2026-03-10 19:00:00");
});

test("handles date rollover when converting to Asia/Taipei", () => {
  expect(formatDateTimeInTaipei("2026-03-10T23:30:00.000Z")).toBe("2026-03-11 07:30:00");
});

test("returns fallback for invalid datetime values", () => {
  expect(formatDateTimeInTaipei("not-a-date")).toBe("-");
  expect(formatDateTimeInTaipei("", { fallback: "N/A" })).toBe("N/A");
});
