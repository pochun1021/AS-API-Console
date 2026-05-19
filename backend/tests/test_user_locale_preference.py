from tests.conftest import build_headers


def test_get_locale_preference_defaults_to_null(client):
    user_headers = build_headers(role="user", account="new.user", email="new.user@example.com", sysid=8001)
    resp = client.get("/api/v1/users/preferences/locale", headers=user_headers)
    assert resp.status_code == 200
    assert resp.json() == {"preferred_locale": None}


def test_update_and_get_locale_preference(client):
    user_headers = build_headers(role="user", account="locale.user", email="locale.user@example.com", sysid=8002)

    update_resp = client.patch(
        "/api/v1/users/preferences/locale",
        headers=user_headers,
        json={"preferred_locale": "zh-TW"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json() == {"preferred_locale": "zh-TW"}

    get_resp = client.get("/api/v1/users/preferences/locale", headers=user_headers)
    assert get_resp.status_code == 200
    assert get_resp.json() == {"preferred_locale": "zh-TW"}


def test_update_locale_preference_rejects_invalid_value(client):
    user_headers = build_headers(role="user", account="locale.user2", email="locale.user2@example.com", sysid=8003)
    resp = client.patch(
        "/api/v1/users/preferences/locale",
        headers=user_headers,
        json={"preferred_locale": "ja-JP"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_locale_preferences_are_isolated_by_sysid(client):
    user_1_headers = build_headers(role="user", account="u1", email="u1@example.com", sysid=8004)
    user_2_headers = build_headers(role="user", account="u2", email="u2@example.com", sysid=8005)

    client.patch("/api/v1/users/preferences/locale", headers=user_1_headers, json={"preferred_locale": "en"})
    client.patch("/api/v1/users/preferences/locale", headers=user_2_headers, json={"preferred_locale": "zh-TW"})

    user_1 = client.get("/api/v1/users/preferences/locale", headers=user_1_headers)
    user_2 = client.get("/api/v1/users/preferences/locale", headers=user_2_headers)

    assert user_1.status_code == 200
    assert user_1.json() == {"preferred_locale": "en"}
    assert user_2.status_code == 200
    assert user_2.json() == {"preferred_locale": "zh-TW"}
