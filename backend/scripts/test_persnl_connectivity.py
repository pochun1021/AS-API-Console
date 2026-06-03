#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from typing import Any
from xml.etree import ElementTree as ET

import httpx


def _require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"missing required env var: {name}")
    return value


def _escape_xml(value: object) -> str:
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _build_envelope(method: str, params: list[object]) -> str:
    args = "".join([f"<param{i}>{_escape_xml(v)}</param{i}>" for i, v in enumerate(params)])
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:urn="uri">'
        "<soapenv:Header/>"
        "<soapenv:Body>"
        f"<urn:{method}>{args}</urn:{method}>"
        "</soapenv:Body>"
        "</soapenv:Envelope>"
    )


def _parse_return_value(xml_text: str) -> str:
    root = ET.fromstring(xml_text)
    node = root.find(".//return")
    if node is None or node.text is None:
        raise RuntimeError("invalid soap response: missing return")
    return node.text


def _soap_call(client: httpx.Client, url: str, method: str, params: list[object]) -> str:
    response = client.post(url, content=_build_envelope(method, params).encode("utf-8"), headers={"Content-Type": "text/xml; charset=utf-8"})
    response.raise_for_status()
    return _parse_return_value(response.text)


def _bool_record(ok: bool, detail: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": ok, "detail": detail}
    if extra:
        payload.update(extra)
    return payload


def _safe_json_loads(payload: str) -> Any:
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def main() -> int:
    fixed_ch_name = "廖俊智"
    fixed_cn = "liaoj"
    fixed_missing_ch_name = "廖某"
    fixed_on_job = "1"

    try:
        url = _require_env("PERSNL_SOAP_URL")
        user = _require_env("PERSNL_SOAP_USER")
        password = _require_env("PERSNL_SOAP_PASSWORD")
        timeout_seconds = float((os.getenv("PERSNL_SOAP_TIMEOUT_SECONDS") or "3.0").strip())
    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 1

    results: dict[str, Any] = {}
    overall_ok = True
    attrs = json.dumps(["sysId", "cn", "chName", "email", "instCode", "tCode"], ensure_ascii=False)

    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=False) as client:
            login_response = _soap_call(client, url, "login", [user, password])
            login_ok = str(login_response).strip() == "0"
            results["login"] = _bool_record(login_ok, "login success" if login_ok else f"login failed: {login_response}")
            overall_ok = overall_ok and login_ok
            if not login_ok:
                print("[FAIL] login")
                return 1

            positive_name_payload = _soap_call(
                client,
                url,
                "Persnl.getUserAttributes",
                [json.dumps({"chName": fixed_ch_name, "onJob": fixed_on_job}, ensure_ascii=False), None, attrs],
            )
            positive_name = _safe_json_loads(positive_name_payload)
            positive_name_count = len(positive_name) if isinstance(positive_name, list) else 0
            name_ok = positive_name_count > 0
            results["lookup_by_ch_name"] = _bool_record(
                name_ok,
                f"records={positive_name_count}",
                {"query": {"chName": fixed_ch_name, "onJob": fixed_on_job}},
            )
            overall_ok = overall_ok and name_ok

            missing_payload = _soap_call(
                client,
                url,
                "Persnl.getUserAttributes",
                [json.dumps({"chName": fixed_missing_ch_name, "onJob": fixed_on_job}, ensure_ascii=False), None, attrs],
            )
            missing = _safe_json_loads(missing_payload)
            missing_ok = isinstance(missing, dict) and missing.get("errMsg") == "data not found."
            results["lookup_missing_ch_name"] = _bool_record(
                missing_ok,
                "expected not found" if missing_ok else f"unexpected response: {missing_payload[:120]}",
                {"query": {"chName": fixed_missing_ch_name, "onJob": fixed_on_job}},
            )
            overall_ok = overall_ok and missing_ok

            by_cn_payload = _soap_call(
                client,
                url,
                "Persnl.getUserAttributes",
                [json.dumps({"cn": fixed_cn, "onJob": fixed_on_job}, ensure_ascii=False), None, attrs],
            )
            by_cn = _safe_json_loads(by_cn_payload)
            by_cn_count = len(by_cn) if isinstance(by_cn, list) else 0
            cn_ok = by_cn_count > 0
            results["lookup_by_cn"] = _bool_record(cn_ok, f"records={by_cn_count}", {"query": {"cn": fixed_cn, "onJob": fixed_on_job}})
            overall_ok = overall_ok and cn_ok

            institutes_payload = _soap_call(client, url, "Persnl.getInstitutes", [])
            institutes = _safe_json_loads(institutes_payload)
            if isinstance(institutes, dict):
                institute_count = len(institutes)
            elif isinstance(institutes, list):
                institute_count = len(institutes)
            else:
                institute_count = 0
            inst_ok = institute_count > 0
            results["get_institutes"] = _bool_record(inst_ok, f"records={institute_count}")
            overall_ok = overall_ok and inst_ok
    except Exception as exc:
        results["exception"] = _bool_record(False, f"{type(exc).__name__}: {exc}")
        overall_ok = False

    for step, info in results.items():
        status = "PASS" if info["ok"] else "FAIL"
        print(f"[{status}] {step}: {info['detail']}")
    print("[PASS] overall" if overall_ok else "[FAIL] overall")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
