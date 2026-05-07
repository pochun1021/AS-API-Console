from tests.conftest import build_headers


def test_get_locale_preference_defaults_to_null(client):
    user_headers = build_headers(role="user", account="new.user", email="new.user@example.com", sysid="new-user-1")
    resp = client.get("/api/v1/users/preferences/locale", headers=user_headers)
    assert resp.status_code == 200
    assert resp.json()["preferred_locale"] is None


def test_update_and_get_locale_preference(client):
    user_headers = build_headers(role="user", account="locale.user", email="locale.user@example.com", sysid="loc-1")

    update_resp = client.patch(
        "/api/v1/users/preferences/locale",
        headers=user_headers,
        json={"preferred_locale": "zh-TW"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["preferred_locale"] == "zh-TW"

    get_resp = client.get("/api/v1/users/preferences/locale", headers=user_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["preferred_locale"] == "zh-TW"


def test_update_locale_preference_rejects_invalid_value(client):
    user_headers = build_headers(role="user", account="locale.user2", email="locale.user2@example.com", sysid="loc-2")
    resp = client.patch(
        "/api/v1/users/preferences/locale",
        headers=user_headers,
        json={"preferred_locale": "ja-JP"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
