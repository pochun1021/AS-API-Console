import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";

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

export function useDepartmentDisplay(auth) {
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

  return { formatDepartment: (value, locale) => formatDepartmentLabel(value, locale, byCode) };
}
