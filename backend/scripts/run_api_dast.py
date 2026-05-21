from __future__ import annotations

from dataclasses import dataclass
import os

import httpx


BASE_URL = os.environ.get("DAST_BASE_URL", "http://127.0.0.1:8000")


@dataclass(slots=True)
class SessionIdentity:
    account: str
    name: str
    email: str
    department: str
    sysid: int
    role: str


class ApiDastFailure(RuntimeError):
    pass


class SessionClient:
    def __init__(self, identity: SessionIdentity) -> None:
        self.identity = identity
        self.client = httpx.Client(base_url=BASE_URL, follow_redirects=False, timeout=10.0)
        self.csrf_token = self._bootstrap()

    def _bootstrap(self) -> str:
        response = self.client.post(
            "/test/session-login",
            json={
                "account": self.identity.account,
                "name": self.identity.name,
                "email": self.identity.email,
                "department": self.identity.department,
                "sysid": self.identity.sysid,
                "role": self.identity.role,
            },
        )
        _assert_status(response, 200)
        payload = response.json()
        token = payload.get("csrf_token")
        if not token:
            raise ApiDastFailure("missing csrf token from test session bootstrap")
        return token

    def mutation_headers(self) -> dict[str, str]:
        return {"x-csrf-token": self.csrf_token}

    def close(self) -> None:
        self.client.close()


def _assert_status(response: httpx.Response, expected_status: int, expected_code: str | None = None) -> None:
    if response.status_code != expected_status:
        raise ApiDastFailure(
            f"expected status {expected_status} for {response.request.method} {response.request.url.path}, "
            f"got {response.status_code}: {response.text}"
        )
    if expected_code is not None:
        actual_code = response.json().get("error", {}).get("code")
        if actual_code != expected_code:
            raise ApiDastFailure(
                f"expected error code {expected_code} for {response.request.method} {response.request.url.path}, "
                f"got {actual_code}: {response.text}"
            )


def main() -> int:
    anonymous = httpx.Client(base_url=BASE_URL, follow_redirects=False, timeout=10.0)
    try:
        health = anonymous.get("/health")
        _assert_status(health, 200)

        unauth = anonymous.get("/api/v1/users/me")
        _assert_status(unauth, 401, "UNAUTHORIZED")

        admin = SessionClient(
            SessionIdentity(
                account="dast.admin",
                name="DAST Admin",
                email="dast.admin@example.com",
                department="Security",
                sysid=910001,
                role="admin",
            )
        )
        user = SessionClient(
            SessionIdentity(
                account="dast.user",
                name="DAST User",
                email="dast.user@example.com",
                department="QA",
                sysid=910002,
                role="user",
            )
        )
        try:
            missing_csrf = admin.client.post("/api/v1/whitelists", json={"sysid": user.identity.sysid, "note": "dast"})
            _assert_status(missing_csrf, 403, "FORBIDDEN")

            whitelist = admin.client.post(
                "/api/v1/whitelists",
                headers=admin.mutation_headers(),
                json={"sysid": user.identity.sysid, "note": "dast"},
            )
            _assert_status(whitelist, 201)

            user_profile = user.client.get("/api/v1/users/me")
            _assert_status(user_profile, 200)
            if "csrf_token" not in user_profile.json():
                raise ApiDastFailure("users/me response missing csrf_token")

            app_no_csrf = user.client.post(
                "/api/v1/api-keys/applications",
                json={
                    "application_date": "2026-05-21",
                    "duration_months": 1,
                    "purpose": "dast smoke",
                },
            )
            _assert_status(app_no_csrf, 403, "FORBIDDEN")

            create_application = user.client.post(
                "/api/v1/api-keys/applications",
                headers=user.mutation_headers(),
                json={
                    "application_date": "2026-05-21",
                    "duration_months": 1,
                    "purpose": "dast smoke",
                },
            )
            _assert_status(create_application, 201)
            created = create_application.json()
            key_id = created["application"]["id"]

            listed = user.client.get("/api/v1/api-keys")
            _assert_status(listed, 200)
            first_item = listed.json()["items"][0]
            key_id = first_item["id"]
            if "api_key_plaintext" in first_item:
                raise ApiDastFailure("list api keys unexpectedly returned api_key_plaintext")

            user_reveal = user.client.post(
                f"/api/v1/api-keys/{key_id}/reveal",
                headers=user.mutation_headers(),
            )
            _assert_status(user_reveal, 403, "FORBIDDEN")

            admin_reveal = admin.client.post(
                f"/api/v1/api-keys/{key_id}/reveal",
                headers=admin.mutation_headers(),
            )
            _assert_status(admin_reveal, 200)
            if admin_reveal.headers.get("cache-control") != "no-store":
                raise ApiDastFailure("reveal response missing Cache-Control: no-store")
            if not admin_reveal.json().get("api_key_plaintext", "").startswith("AS-"):
                raise ApiDastFailure("reveal response missing plaintext API key")

            forbidden_whitelist_read = user.client.get("/api/v1/whitelists")
            _assert_status(forbidden_whitelist_read, 403, "VALIDATION_ERROR")

            admin_audit = admin.client.get("/api/v1/operation-audit-logs")
            _assert_status(admin_audit, 200)
        finally:
            admin.close()
            user.close()
    finally:
        anonymous.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
