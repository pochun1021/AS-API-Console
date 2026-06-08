import { useMemo, useState } from "react";
import CalendarMonthIcon from "@mui/icons-material/CalendarMonth";
import { Box, Button, IconButton, InputAdornment, Popover, Stack, TextField } from "@mui/material";
import dayjs from "dayjs";
import { DayPicker } from "react-day-picker";
import { enUS, zhTW } from "react-day-picker/locale";
import "react-day-picker/style.css";
import { useLocale } from "../i18n/locale";

function normalizeDateValue(value) {
  if (!value) return "";
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return value;
  }

  const parsed = dayjs(value);
  return parsed.isValid() ? parsed.format("YYYY-MM-DD") : "";
}

function buildSummary(fromValue, toValue) {
  if (fromValue && toValue) return `${fromValue} - ${toValue}`;
  if (fromValue) return `${fromValue} -`;
  if (toValue) return `- ${toValue}`;
  return "";
}

function toPickerDate(value) {
  if (!value) return undefined;
  const parsed = dayjs(value);
  return parsed.isValid() ? parsed.toDate() : undefined;
}

export default function DateRangeFilterField({
  label,
  fromValue,
  toValue,
  onChange,
  startLabel,
  endLabel,
  clearLabel = "Clear",
  closeLabel = "Close",
  minWidth = 220,
}) {
  const { locale } = useLocale();
  const [anchorEl, setAnchorEl] = useState(null);
  const open = Boolean(anchorEl);
  const pickerLocale = locale === "zh-TW" ? zhTW : enUS;
  const selectedRange = useMemo(
    () => ({
      from: toPickerDate(fromValue),
      to: toPickerDate(toValue),
    }),
    [fromValue, toValue]
  );
  const defaultMonth = selectedRange.from || selectedRange.to || new Date();

  function emitRange(nextFrom, nextTo) {
    onChange({
      from: normalizeDateValue(nextFrom),
      to: normalizeDateValue(nextTo),
    });
  }

  function handleStartChange(nextValue) {
    const nextFrom = normalizeDateValue(nextValue);
    if (!nextFrom) {
      emitRange("", toValue);
      return;
    }
    if (toValue && nextFrom > toValue) {
      emitRange(nextFrom, nextFrom);
      return;
    }
    emitRange(nextFrom, toValue);
  }

  function handleEndChange(nextValue) {
    const nextTo = normalizeDateValue(nextValue);
    if (!nextTo) {
      emitRange(fromValue, "");
      return;
    }
    if (fromValue && nextTo < fromValue) {
      emitRange(nextTo, nextTo);
      return;
    }
    emitRange(fromValue, nextTo);
  }

  return (
    <>
      <TextField
        label={label}
        value={buildSummary(fromValue, toValue)}
        placeholder="YYYY-MM-DD - YYYY-MM-DD"
        onClick={(event) => setAnchorEl(event.currentTarget)}
        sx={{ minWidth }}
        inputProps={{ readOnly: true, "aria-label": label }}
        InputProps={{
          endAdornment: (
            <InputAdornment position="end">
              <IconButton aria-label={`${label} picker`} edge="end" onClick={(event) => setAnchorEl(event.currentTarget)}>
                <CalendarMonthIcon fontSize="small" />
              </IconButton>
            </InputAdornment>
          ),
        }}
      />
      <Popover
        open={open}
        anchorEl={anchorEl}
        onClose={() => setAnchorEl(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
        transformOrigin={{ vertical: "top", horizontal: "left" }}
      >
        <Stack spacing={2} sx={{ p: 2 }}>
          <Box
            sx={{
              position: "absolute",
              width: 1,
              height: 1,
              p: 0,
              m: -1,
              overflow: "hidden",
              clip: "rect(0 0 0 0)",
              whiteSpace: "nowrap",
              border: 0,
            }}
          >
            <label>
              {startLabel}
              <input type="date" value={fromValue} onChange={(event) => handleStartChange(event.target.value)} />
            </label>
            <label>
              {endLabel}
              <input type="date" value={toValue} onChange={(event) => handleEndChange(event.target.value)} />
            </label>
          </Box>
          <Box
            sx={{
              "& .rdp-root": {
                "--rdp-accent-color": "#0b3c5d",
                "--rdp-accent-background-color": "#dfeaf2",
                "--rdp-range_middle-background-color": "#e9f1f7",
                "--rdp-range_middle-color": "#0b3c5d",
                "--rdp-day_button-border-radius": "8px",
                "--rdp-day-width": "40px",
                "--rdp-day-height": "40px",
                "--rdp-nav_button-width": "32px",
                "--rdp-nav_button-height": "32px",
                fontFamily: "'IBM Plex Sans', 'Noto Sans TC', sans-serif",
              },
              "& .rdp-months": {
                display: "flex",
                gap: 2,
                flexDirection: { xs: "column", md: "row" },
              },
              "& .rdp-range_start .rdp-day_button, & .rdp-range_end .rdp-day_button": {
                backgroundColor: "#0b3c5d",
                color: "#fff",
              },
              "& .rdp-range_middle": {
                backgroundColor: "#e9f1f7",
              },
              "& .rdp-day_button:hover": {
                borderColor: "#0b3c5d",
                backgroundColor: "#eef4f8",
              },
            }}
          >
            <DayPicker
              mode="range"
              numberOfMonths={2}
              pagedNavigation
              fixedWeeks
              locale={pickerLocale}
              defaultMonth={defaultMonth}
              selected={selectedRange}
              onSelect={(range) => {
                emitRange(range?.from || "", range?.to || "");
              }}
            />
          </Box>
          <Stack direction="row" spacing={1} justifyContent="flex-end">
            <Button
              onClick={() => {
                emitRange("", "");
              }}
              disabled={!fromValue && !toValue}
            >
              {clearLabel}
            </Button>
            <Button variant="contained" onClick={() => setAnchorEl(null)}>
              {closeLabel}
            </Button>
          </Stack>
        </Stack>
      </Popover>
    </>
  );
}
