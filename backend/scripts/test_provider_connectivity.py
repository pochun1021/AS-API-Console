#!/usr/bin/env python3
import os
import sys
import json
import httpx

def _require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"missing required env var: {name}")
    return value

def main() -> int:
    try:
        base_url = _require_env("PROVIDER_BASE_URL").rstrip("/")
        master_key = _require_env("PROVIDER_MASTER_KEY")
        timeout_seconds = float((os.getenv("PROVIDER_TIMEOUT_SECONDS") or "3.0").strip())
    except Exception as exc:
        print(f"[FAIL] configuration: {exc}")
        return 1

    print(f"--- Provider Connectivity Test ---")
    print(f"Base URL:   {base_url}")
    print(f"Master Key: {master_key}")
    print(f"Timeout:    {timeout_seconds}s")
    print("----------------------------------")

    test_payload = {
        "key_alias": f"connectivity_test_{os.getpid()}",
        "duration": "30d",
        "max_budget": 0.01,
        "tpm_limit": 1,
        "rpm_limit": 1,
        "max_parallel_requests": 0,
        "budget_duration": "30d",
        "key_type": "llm_api"
    }

    url = f"{base_url}/key/generate"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {master_key}"
    }

    print(f"[INFO] sending test request to {url}...")
    
    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=False) as client:
            resp = client.post(url, json=test_payload, headers=headers)
            
            if resp.status_code == 200:
                data = resp.json()
                print(f"[PASS] connection successful!")
                print(f"[INFO] request_id: {data.get('request_id')}")
                return 0
            
            print(f"[FAIL] provider rejected request with status {resp.status_code}")
            try:
                error_detail = resp.json()
                print(f"[INFO] response body: {json.dumps(error_detail, indent=2)}")
            except:
                print(f"[INFO] raw response: {resp.text}")

            if resp.status_code == 403:
                print("\n[HINT] POSSIBLE CAUSES FOR 403:")
                print("1. PROVIDER_MASTER_KEY is incorrect or has been revoked.")
                print("2. The IP address of this server is not whitelisted by the provider.")
                print("3. The request was rejected by a gateway, WAF, or upstream policy before reaching the provider app.")
                print("4. The payload fields do not match the provider contract expected by this deployment.")
            return 1

    except httpx.TimeoutException:
        print(f"[FAIL] request timed out after {timeout_seconds}s")
        return 1
    except Exception as exc:
        print(f"[FAIL] unexpected error: {type(exc).__name__}: {exc}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
