import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import { useLocale } from "../i18n/locale";

export function formatDepartmentLabel(departmentCodeOrText, locale, byCode) {
  if (!departmentCodeOrText) return "-";
  const raw = String(departmentCodeOrText).trim();
  if (!raw) return "-";
  const entry = byCode.get(raw);
  if (!entry) return raw;
  if (locale === "en") {
    return entry.einst_name || entry.inst_name || entry.abb_inst_name || raw;
  }
  return entry.inst_name || entry.abb_inst_name || entry.einst_name || raw;
}

export function formatDepartmentOptionLabel(departmentCodeOrText, locale, byCode) {
  if (!departmentCodeOrText) return "-";
  const raw = String(departmentCodeOrText).trim();
  if (!raw) return "-";
  const entry = byCode.get(raw);
  if (!entry) return raw;
  const name = locale === "en"
    ? entry.einst_name || entry.inst_name || entry.abb_inst_name || raw
    : entry.inst_name || entry.abb_inst_name || entry.einst_name || raw;
  return `${raw} ${name}`;
}

export function useDepartmentDisplay(auth) {
  const { locale } = useLocale();
  const [institutes, setInstitutes] = useState([]);

  useEffect(() => {
    let canceled = false;
    async function load() {
      try {
        const resp = await apiClient.listInstitutes(auth);
        if (!canceled) {
          setInstitutes(resp.items || []);
        }
      } catch {
        if (!canceled) {
          setInstitutes([]);
        }
      }
    }
    load();
    return () => {
      canceled = true;
    };
  }, [auth?.account, auth?.role]);

  const byCode = useMemo(() => {
    const map = new Map();
    for (const item of institutes) {
      if (item?.inst_code) {
        map.set(String(item.inst_code), item);
      }
    }
    return map;
  }, [institutes]);

  const options = useMemo(
    () => institutes
      .filter((item) => item?.inst_code)
      .map((item) => ({
        value: String(item.inst_code),
        label: formatDepartmentOptionLabel(item.inst_code, locale, byCode),
      })),
    [byCode, institutes, locale]
  );

  return {
    departmentOptions: options,
    formatDepartment: (value, locale) => formatDepartmentLabel(value, locale, byCode),
    formatDepartmentOption: (value, locale) => formatDepartmentOptionLabel(value, locale, byCode),
  };
}
