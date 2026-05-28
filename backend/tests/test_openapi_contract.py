def test_openapi_documents_security_scan_response_codes(client):
    resp = client.get("/main/openapi.json")
    assert resp.status_code == 200

    paths = resp.json()["paths"]

    assert set(paths["/main/login"]["get"]["responses"]) >= {"302", "500"}
    assert set(paths["/main/auth/callback"]["get"]["responses"]) >= {"302", "401", "422"}
    assert set(paths["/main/api/v1/whitelists"]["post"]["responses"]) >= {"201", "403", "409", "422"}
    assert set(paths["/main/api/v1/limit-strategy-config"]["patch"]["responses"]) >= {"200", "403", "422"}
    assert set(paths["/main/api/v1/api-keys/{key_id}"]["get"]["responses"]) >= {"200", "403", "404"}
    assert set(paths["/main/api/v1/admins"]["get"]["responses"]) >= {"200", "403"}
    assert set(paths["/main/api/v1/users"]["get"]["responses"]) >= {"200", "403", "422", "503"}
