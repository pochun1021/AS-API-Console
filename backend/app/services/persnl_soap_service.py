from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import httpx
from zeep import Client as ZeepClient
from zeep import Settings as ZeepSettings

from app.core.config import get_settings


class PersnlSoapUnavailableError(RuntimeError):
    pass


@dataclass(slots=True)
class PersnlSoapService:
    url: str | None = None
    wsdl_url: str | None = None
    user: str | None = None
    password: str | None = None
    timeout_seconds: float = 3.0
    logged_in: bool = False
    unavailable_reason: str | None = None
    last_login_at: datetime | None = None
    _client: httpx.Client = field(init=False, repr=False)
    _zeep_client: ZeepClient | None = field(init=False, default=None, repr=False)
    _zeep_service: object | None = field(init=False, default=None, repr=False)

    def __init__(self) -> None:
        settings = get_settings()
        self.url = settings.persnl_soap_url
        self.wsdl_url = settings.persnl_soap_wsdl_url
        self.user = settings.persnl_soap_user
        self.password = settings.persnl_soap_password
        self.timeout_seconds = settings.persnl_soap_timeout_seconds
        self.logged_in = False
        self.unavailable_reason = None
        self.last_login_at = None
        self._client = httpx.Client(timeout=self.timeout_seconds)

    def is_configured(self) -> bool:
        return bool((self.url or self.wsdl_url) and self.user and self.password)

    def initialize(self) -> None:
        if not self.is_configured():
            self.unavailable_reason = "persnl soap is not configured"
            self.logged_in = False
            return
        try:
            result = self._soap_call("login", [self.user, self.password])
            if str(result).strip() != "0":
                self.unavailable_reason = "soap login failed"
                self.logged_in = False
                return
        except Exception as exc:
            self.unavailable_reason = f"soap login failed: {exc}"
            self.logged_in = False
            return
        self.unavailable_reason = None
        self.logged_in = True
        self.last_login_at = datetime.now(timezone.utc)

    def search_people_by_name(self, ch_name: str, on_job: str = "1") -> list[dict]:
        return self._query_users({"chName": ch_name, "onJob": on_job})

    def search_person_by_account(self, account: str, on_job: str = "1") -> list[dict]:
        return self._query_users({"cn": account, "onJob": on_job})

    def search_by_keyword(self, keyword: str, limit: int = 20) -> list[dict]:
        normalized = keyword.strip().lower()
        if not normalized:
            return []

        candidates = self.search_person_by_account(keyword) + self.search_people_by_name(keyword)
        deduped: list[dict] = []
        seen_sysid: set[str] = set()
        for item in candidates:
            sysid = str(item.get("sysId", "")).strip()
            if not sysid or sysid in seen_sysid:
                continue
            account = str(item.get("cn", "")).strip().lower()
            name = str(item.get("chName", "")).strip().lower()
            if normalized not in account and normalized not in name:
                continue
            seen_sysid.add(sysid)
            deduped.append(item)
            if len(deduped) >= limit:
                break
        return deduped

    def get_institutes(self) -> list[dict]:
        self._ensure_available()
        result = self._soap_call("Persnl.getInstitutes", [])
        try:
            payload = json.loads(result)
        except json.JSONDecodeError:
            return []

        raw_items: list[dict] = []
        if isinstance(payload, dict):
            for value in payload.values():
                if isinstance(value, dict):
                    raw_items.append(value)
        elif isinstance(payload, list):
            raw_items = [item for item in payload if isinstance(item, dict)]
        else:
            return []

        institutes: list[dict] = []
        for item in raw_items:
            inst_code = str(item.get("instCode", "")).strip()
            inst_name = str(item.get("instName", "")).strip()
            if not inst_code or not inst_name:
                continue
            institutes.append(
                {
                    "instCode": inst_code,
                    "instName": inst_name,
                    "abb_instName": str(item.get("abb_instName", "")).strip() or None,
                    "einstName": str(item.get("einstName", "")).strip() or None,
                    "division": str(item.get("division", "")).strip() or None,
                }
            )
        return institutes

    def _query_users(self, filters: dict[str, str]) -> list[dict]:
        self._ensure_available()
        attrs = ["sysId", "cn", "chName", "email", "instCode", "tCode"]
        result = self._soap_call(
            "Persnl.getUserAttributes",
            [json.dumps(filters, ensure_ascii=False), None, json.dumps(attrs)],
        )
        try:
            payload = json.loads(result)
        except json.JSONDecodeError:
            return []
        if isinstance(payload, dict):
            return []
        if not isinstance(payload, list):
            return []
        items: list[dict] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            items.append(
                {
                    "sysId": str(item.get("sysId", "")).strip(),
                    "cn": str(item.get("cn", "")).strip(),
                    "chName": str(item.get("chName", "")).strip(),
                    "email": str(item.get("email", "")).strip(),
                    "instCode": str(item.get("instCode", "")).strip(),
                    "tCode": str(item.get("tCode", "")).strip(),
                }
            )
        return items

    def _ensure_available(self) -> None:
        if not self.logged_in:
            raise PersnlSoapUnavailableError(self.unavailable_reason or "persnl soap unavailable")

    def _soap_call(self, method: str, params: list[object]) -> str:
        if self._zeep_client is None and self._zeep_service is None:
            self._init_zeep_client()
        if self._zeep_service is not None:
            value = getattr(self._zeep_service, method)(*params)
            return "" if value is None else str(value)
        if not self.url:
            raise PersnlSoapUnavailableError("persnl soap url is not configured")
        xml = self._build_soap_envelope(method, params)
        response = self._client.post(self.url, content=xml.encode("utf-8"), headers={"Content-Type": "text/xml; charset=utf-8"})
        response.raise_for_status()
        return self._parse_return_value(response.text)

    def _init_zeep_client(self) -> None:
        if not self.wsdl_url:
            self._zeep_client = None
            self._zeep_service = None
            return
        settings = ZeepSettings(strict=False, xml_huge_tree=True)
        try:
            self._zeep_client = ZeepClient(wsdl=self.wsdl_url, settings=settings)
            if self.url:
                # Use configured runtime endpoint even when wsdl address differs.
                binding_name = self._zeep_client.service._binding.name
                self._zeep_service = self._zeep_client.create_service(binding_name, self.url)
            else:
                self._zeep_service = self._zeep_client.service
        except Exception:
            self._zeep_client = None
            self._zeep_service = None

    def _build_soap_envelope(self, method: str, params: list[object]) -> str:
        args = "".join([f"<param{i}>{self._escape_xml(v)}</param{i}>" for i, v in enumerate(params)])
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:urn="uri">'
            "<soapenv:Header/>"
            "<soapenv:Body>"
            f"<urn:{method}>{args}</urn:{method}>"
            "</soapenv:Body>"
            "</soapenv:Envelope>"
        )

    def _parse_return_value(self, xml_text: str) -> str:
        root = ET.fromstring(xml_text)
        return_node = root.find(".//return")
        if return_node is None or return_node.text is None:
            raise PersnlSoapUnavailableError("invalid soap response")
        return return_node.text

    def _escape_xml(self, value: object) -> str:
        text = "" if value is None else str(value)
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )
