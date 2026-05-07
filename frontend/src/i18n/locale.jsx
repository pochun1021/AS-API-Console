import { createContext, useContext, useMemo, useState } from "react";
import { enUS, zhTW } from "@mui/x-data-grid/locales";
import { messages } from "./messages";

const LocaleContext = createContext(null);
const fallbackLocaleContext = {
  locale: "zh-TW",
  setLocale: () => {},
  gridLocaleText: zhTW.components.MuiDataGrid.defaultProps.localeText,
  t(key, fallback = "") {
    const dict = messages["zh-TW"];
    return dict[key] || fallback || key;
  }
};

export function detectSystemLocale() {
  const langs = [];
  if (typeof navigator !== "undefined") {
    if (Array.isArray(navigator.languages)) {
      langs.push(...navigator.languages);
    }
    if (navigator.language) {
      langs.push(navigator.language);
    }
  }

  const normalized = langs.map((item) => String(item || "").toLowerCase());
  if (normalized.some((item) => item.startsWith("zh"))) return "zh-TW";
  if (normalized.some((item) => item.startsWith("en"))) return "en";
  return "en";
}

export function LocaleProvider({ children }) {
  const [locale, setLocale] = useState("en");

  const value = useMemo(() => {
    const dict = messages[locale] || messages.en;
    const gridLocaleText =
      locale === "zh-TW"
        ? zhTW.components.MuiDataGrid.defaultProps.localeText
        : enUS.components.MuiDataGrid.defaultProps.localeText;
    return {
      locale,
      setLocale,
      gridLocaleText,
      t(key, fallback = "") {
        return dict[key] || fallback || key;
      }
    };
  }, [locale]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  const ctx = useContext(LocaleContext);
  return ctx || fallbackLocaleContext;
}
