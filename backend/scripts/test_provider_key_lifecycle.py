#!/usr/bin/env python3
import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

_RESET = "\033[0m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"


def _colorize(label: str, color: str) -> str:
    return f"{color}{label}{_RESET}"


PASS_LABEL = _colorize("[PASS]", _GREEN)
FAIL_LABEL = _colorize("[FAIL]", _RED)
WARN_LABEL = _colorize("[WARN]", _YELLOW)


def _require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"missing required env var: {name}")
    return value


def _json_dump(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)


def _provider_duration(days: int) -> str:
    if days <= 0:
        raise ValueError("duration must be positive")
    return f"{days}d"


def _next_duration_days(current: int) -> int:
    for candidate in (30, 180, 360):
        if candidate > current:
            return candidate
    return current


@dataclass(slots=True)
class StepResult:
    status_code: int
    body: Any


class ProviderLifecycleError(RuntimeError):
    pass


class ProviderLifecycleTester:
    def __init__(
        self,
        *,
        base_url: str,
        master_key: str,
        team_id: str,
        timeout_seconds: float,
        alias_prefix: str,
        duration_days: int,
        max_budget: float,
        tpm_limit: int,
        rpm_limit: int,
        keep_on_failure: bool,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.master_key = master_key
        self.team_id = team_id
        self.timeout_seconds = timeout_seconds
        self.alias_prefix = alias_prefix
        self.duration_days = duration_days
        self.extend_duration_days = _next_duration_days(duration_days)
        self.max_budget = max_budget
        self.tpm_limit = tpm_limit
        self.rpm_limit = rpm_limit
        self.keep_on_failure = keep_on_failure
        self.key_a: str | None = None
        self.key_b: str | None = None
        self.aliases_seen: list[str] = []

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.master_key}",
        }

    def _request(
        self,
        *,
        step: str,
        path: str,
        payload: dict[str, Any],
        expected_statuses: tuple[int, ...] = (200,),
    ) -> StepResult:
        url = f"{self.base_url}{path}"
        headers = self._headers()

        print(f"\n=== STEP: {step} ===")
        print(f"URL: {url}")
        print(f"HEADERS: {_json_dump(headers)}")
        print(f"REQUEST JSON: {_json_dump(payload)}")

        try:
            with httpx.Client(timeout=self.timeout_seconds, follow_redirects=False) as client:
                response = client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            print(f"STATUS: timeout after {self.timeout_seconds}s")
            print("RESPONSE BODY: <timeout>")
            raise ProviderLifecycleError(f"{step} timed out") from exc
        except httpx.RequestError as exc:
            print("STATUS: request error")
            print(f"RESPONSE BODY: {type(exc).__name__}: {exc}")
            raise ProviderLifecycleError(f"{step} request failed") from exc

        body: Any
        try:
            body = response.json()
        except json.JSONDecodeError:
            body = response.text

        print(f"STATUS: {response.status_code}")
        if isinstance(body, str):
            print(f"RESPONSE BODY: {body}")
        else:
            print(f"RESPONSE BODY: {_json_dump(body)}")

        if response.status_code not in expected_statuses:
            raise ProviderLifecycleError(f"{step} failed with status {response.status_code}")

        return StepResult(status_code=response.status_code, body=body)

    def _base_generate_payload(self, alias: str, duration_days: int) -> dict[str, Any]:
        return {
            "max_budget": self.max_budget,
            "budget_duration": "30d",
            "duration": _provider_duration(duration_days),
            "tpm_limit": self.tpm_limit,
            "rpm_limit": self.rpm_limit,
            "max_parallel_requests": 0,
            "team_id": self.team_id,
            "key_alias": alias,
            "key_type": "llm_api",
        }

    def _base_update_payload(self, key_plaintext: str, duration_days: int) -> dict[str, Any]:
        return {
            "key": key_plaintext,
            "max_budget": self.max_budget,
            "budget_duration": "30d",
            "duration": _provider_duration(duration_days),
            "tpm_limit": self.tpm_limit,
            "rpm_limit": self.rpm_limit,
            "max_parallel_requests": 0,
            "team_id": self.team_id,
            "key_type": "llm_api",
        }

    def _remember_alias(self, alias: str) -> None:
        if alias not in self.aliases_seen:
            self.aliases_seen.append(alias)

    def _extract_plaintext_key(self, step: str, body: Any) -> str:
        if not isinstance(body, dict):
            raise ProviderLifecycleError(f"{step} response is not a JSON object")
        plaintext = str(body.get("key") or "").strip()
        if not plaintext:
            raise ProviderLifecycleError(f"{step} response missing key")
        return plaintext

    def run(self) -> int:
        cleanup_needed = False
        flow_failed = False

        try:
            alias_a = f"{self.alias_prefix}_a"
            self._remember_alias(alias_a)
            generate_a = self._request(
                step="generate key A",
                path="/key/generate",
                payload=self._base_generate_payload(alias_a, self.duration_days),
            )
            self.key_a = self._extract_plaintext_key("generate key A", generate_a.body)
            cleanup_needed = True

            alias_a_updated = f"{self.alias_prefix}_a_updated"
            self._remember_alias(alias_a_updated)
            update_alias_payload = self._base_update_payload(self.key_a, self.duration_days)
            update_alias_payload["key_alias"] = alias_a_updated
            self._request(
                step="update key A alias",
                path="/key/update",
                payload=update_alias_payload,
            )

            extend_payload = self._base_update_payload(self.key_a, self.extend_duration_days)
            extend_payload["key_alias"] = alias_a_updated
            self._request(
                step="extend key A",
                path="/key/update",
                payload=extend_payload,
            )

            self._request(
                step="block key A",
                path="/key/block",
                payload={"key": self.key_a},
            )

            alias_b = f"{self.alias_prefix}_b"
            self._remember_alias(alias_b)
            generate_b = self._request(
                step="generate key B",
                path="/key/generate",
                payload=self._base_generate_payload(alias_b, self.duration_days),
            )
            self.key_b = self._extract_plaintext_key("generate key B", generate_b.body)

            team_payload = {
                "team_id": self.team_id,
                "all_keys_in_team": True,
                "update_fields": {
                    "tpm_limit": self.tpm_limit + 1,
                    "rpm_limit": self.rpm_limit + 1,
                    "max_budget": round(self.max_budget + 0.01, 4),
                    "budget_duration": "30d",
                    "max_parallel_requests": 0,
                },
            }
            self._request(
                step="update team limits",
                path="/team/key/bulk_update",
                payload=team_payload,
            )
        except ProviderLifecycleError as exc:
            flow_failed = True
            print(f"\n{FAIL_LABEL} {exc}")
        finally:
            if cleanup_needed and not (flow_failed and self.keep_on_failure):
                cleanup_ok = self._cleanup()
                if not cleanup_ok:
                    flow_failed = True
            elif cleanup_needed and flow_failed and self.keep_on_failure:
                print("\n[INFO] cleanup skipped because --keep-on-failure was set")

        if flow_failed:
            return 1

        print(f"\n{PASS_LABEL} provider key lifecycle completed successfully")
        return 0

    def _cleanup(self) -> bool:
        print("\n--- CLEANUP ---")
        aliases = list(self.aliases_seen)
        keys = [key for key in (self.key_a, self.key_b) if key]
        cleanup_ok = True

        alias_result: StepResult | None = None
        alias_confirmed = False
        alias_delete_failed = False

        if aliases:
            try:
                alias_result = self._request(
                    step="cleanup delete by aliases",
                    path="/key/delete",
                    payload={"key_aliases": aliases},
                    expected_statuses=(200, 204),
                )
            except ProviderLifecycleError as exc:
                alias_delete_failed = True
                cleanup_ok = False
                print(f"{WARN_LABEL} alias cleanup failed: {exc}")
            else:
                alias_confirmed = self._delete_response_looks_successful(alias_result.body)
                if not alias_confirmed:
                    print(f"{WARN_LABEL} alias cleanup response shape did not clearly confirm deletion")

        fallback_needed = bool(keys) and (alias_delete_failed or not alias_confirmed)
        if fallback_needed:
            try:
                self._request(
                    step="cleanup delete by keys",
                    path="/key/delete",
                    payload={"keys": keys},
                    expected_statuses=(200, 204),
                )
            except ProviderLifecycleError as exc:
                cleanup_ok = False
                print(f"{WARN_LABEL} key cleanup failed: {exc}")

        if cleanup_ok:
            print("[INFO] cleanup completed")
        else:
            print(f"{WARN_LABEL} cleanup may have left residual aliases: {aliases}")
            print(f"{WARN_LABEL} cleanup may have left residual keys: {keys}")
        return cleanup_ok

    def _delete_response_looks_successful(self, body: Any) -> bool:
        if body == "":
            return True
        if isinstance(body, dict):
            if body.get("success") is True:
                return True
            deleted = body.get("deleted")
            if isinstance(deleted, list):
                return True
            message = str(body.get("message") or "").strip().lower()
            if "deleted" in message or "success" in message:
                return True
        if isinstance(body, list):
            return True
        return False


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Test provider key lifecycle directly against provider endpoints.")
    parser.add_argument("--alias-prefix", default="", help="Alias prefix to use for generated test keys.")
    parser.add_argument("--duration", type=int, default=30, help="Initial key duration in days. Default: 30")
    parser.add_argument("--budget", type=float, default=0.01, help="max_budget for test keys. Default: 0.01")
    parser.add_argument("--tpm", type=int, default=1, help="tpm_limit for test keys. Default: 1")
    parser.add_argument("--rpm", type=int, default=1, help="rpm_limit for test keys. Default: 1")
    parser.add_argument(
        "--keep-on-failure",
        action="store_true",
        help="Skip cleanup after a failed step so the created provider keys remain for inspection.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()

    try:
        base_url = _require_env("PROVIDER_BASE_URL")
        master_key = _require_env("PROVIDER_MASTER_KEY")
        team_id = _require_env("PROVIDER_TEAM_ID")
        timeout_seconds = float((os.getenv("PROVIDER_TIMEOUT_SECONDS") or "3.0").strip())
        if args.duration <= 0:
            raise RuntimeError("--duration must be positive")
        if args.tpm < 0 or args.rpm < 0:
            raise RuntimeError("--tpm and --rpm must be zero or positive")
        if args.budget <= 0:
            raise RuntimeError("--budget must be positive")
    except Exception as exc:
        print(f"{FAIL_LABEL} configuration: {exc}")
        return 1

    alias_prefix = args.alias_prefix.strip() or (
        f"provider_lifecycle_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{os.getpid()}"
    )

    print("--- Provider Key Lifecycle Test ---")
    print(f"Base URL:        {base_url}")
    print(f"Master Key:      {master_key}")
    print(f"Team ID:         {team_id}")
    print(f"Timeout:         {timeout_seconds}s")
    print(f"Alias Prefix:    {alias_prefix}")
    print(f"Initial Days:    {args.duration}")
    print(f"Extend Days:     {_next_duration_days(args.duration)}")
    print(f"Max Budget:      {args.budget}")
    print(f"TPM Limit:       {args.tpm}")
    print(f"RPM Limit:       {args.rpm}")
    print(f"Keep On Failure: {args.keep_on_failure}")
    print("-----------------------------------")

    tester = ProviderLifecycleTester(
        base_url=base_url,
        master_key=master_key,
        team_id=team_id,
        timeout_seconds=timeout_seconds,
        alias_prefix=alias_prefix,
        duration_days=args.duration,
        max_budget=args.budget,
        tpm_limit=args.tpm,
        rpm_limit=args.rpm,
        keep_on_failure=args.keep_on_failure,
    )
    return tester.run()


if __name__ == "__main__":
    sys.exit(main())
