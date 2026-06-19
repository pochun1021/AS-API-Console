import { enUS, zhTW } from "@mui/x-data-grid/locales";

export function getGridLocaleText(locale) {
  return locale === "zh-TW"
    ? zhTW.components.MuiDataGrid.defaultProps.localeText
    : enUS.components.MuiDataGrid.defaultProps.localeText;
}
