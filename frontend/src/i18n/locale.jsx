import { createContext, useContext, useMemo, useState } from "react";
import { messages } from "./messages";

const LocaleContext = createContext(null);

function formatMessage(template, params = {}) {
  return Object.entries(params).reduce(
    (message, [key, value]) => message.replaceAll(`{${key}}`, String(value)),
    String(template || ""),
  );
}

function normalizeTranslationArgs(fallbackOrParams, maybeParams) {
  if (fallbackOrParams && typeof fallbackOrParams === "object" && !Array.isArray(fallbackOrParams)) {
    return { fallback: "", params: fallbackOrParams };
  }
  return { fallback: fallbackOrParams || "", params: maybeParams || {} };
}

const fallbackLocaleContext = {
  locale: "zh-TW",
  setLocale: () => {},
  t(key, fallbackOrParams = "", maybeParams = {}) {
    const dict = messages["zh-TW"];
    const { fallback, params } = normalizeTranslationArgs(fallbackOrParams, maybeParams);
    return formatMessage(dict[key] || fallback || key, params);
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
    return {
      locale,
      setLocale,
      t(key, fallbackOrParams = "", maybeParams = {}) {
        const { fallback, params } = normalizeTranslationArgs(fallbackOrParams, maybeParams);
        return formatMessage(dict[key] || fallback || key, params);
      }
    };
  }, [locale]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  const ctx = useContext(LocaleContext);
  return ctx || fallbackLocaleContext;
}
