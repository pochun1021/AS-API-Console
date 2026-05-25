import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ThemeProvider, CssBaseline } from "@mui/material";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { enUS as dateEnUS, zhTW as dateZhTW } from "@mui/x-date-pickers/locales";
import "dayjs/locale/en";
import "dayjs/locale/zh-tw";
import App from "./App";
import { appTheme } from "./theme";
import { LocaleProvider, useLocale } from "./i18n/locale";

function DateLocalizationBridge({ children }) {
  const { locale } = useLocale();
  const isZh = locale === "zh-TW";
  return (
    <LocalizationProvider
      dateAdapter={AdapterDayjs}
      adapterLocale={isZh ? "zh-tw" : "en"}
      localeText={isZh ? dateZhTW.components.MuiLocalizationProvider.defaultProps.localeText : dateEnUS.components.MuiLocalizationProvider.defaultProps.localeText}
    >
      {children}
    </LocalizationProvider>
  );
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ThemeProvider theme={appTheme}>
      <CssBaseline />
      <LocaleProvider>
        <DateLocalizationBridge>
          <BrowserRouter basename="/main">
            <App />
          </BrowserRouter>
        </DateLocalizationBridge>
      </LocaleProvider>
    </ThemeProvider>
  </React.StrictMode>
);
