from datetime import UTC, datetime, timedelta
import json

from db.models.operation_audit_logs import OperationAuditLog
from db.session import get_db
from tests.conftest import api_path


def _payload(*, title: str, status: str = "active", publish_from=None, publish_to=None, body: str = "公告內容") -> dict:
    return {
        "title": title,
        "body": body,
        "status": status,
        "publish_from": publish_from,
        "publish_to": publish_to,
    }


def test_announcements_user_and_admin_only_see_active_window_items(client, admin_headers, user_headers):
    now = datetime.now(UTC)
    payloads = [
        _payload(
            title="Visible",
            publish_from=(now - timedelta(hours=1)).isoformat(),
            publish_to=(now + timedelta(hours=1)).isoformat(),
        ),
        _payload(title="Inactive", status="inactive"),
        _payload(title="Future", publish_from=(now + timedelta(days=1)).isoformat()),
        _payload(title="Expired", publish_to=(now - timedelta(minutes=1)).isoformat()),
    ]
    for payload in payloads:
        resp = client.post(api_path("/announcements"), headers=admin_headers, json=payload)
        assert resp.status_code == 201

    user_list = client.get(api_path("/announcements"), headers=user_headers)
    assert user_list.status_code == 200
    assert [item["title"] for item in user_list.json()["items"]] == ["Visible"]

    admin_default = client.get(api_path("/announcements"), headers=admin_headers)
    assert admin_default.status_code == 200
    assert [item["title"] for item in admin_default.json()["items"]] == ["Visible"]

    admin_all = client.get(api_path("/announcements?scope=all&sort_by=title&sort_dir=asc"), headers=admin_headers)
    assert admin_all.status_code == 200
    assert [item["title"] for item in admin_all.json()["items"]] == ["Expired", "Future", "Inactive", "Visible"]


def test_announcements_scope_all_forbidden_for_user(client, admin_headers, user_headers):
    created = client.post(api_path("/announcements"), headers=admin_headers, json=_payload(title="Admin Notice"))
    assert created.status_code == 201

    resp = client.get(api_path("/announcements?scope=all"), headers=user_headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_announcements_admin_only_mutations(client, admin_headers, user_headers):
    create_forbidden = client.post(api_path("/announcements"), headers=user_headers, json=_payload(title="User Create"))
    assert create_forbidden.status_code == 403

    created = client.post(api_path("/announcements"), headers=admin_headers, json=_payload(title="Admin Create"))
    assert created.status_code == 201
    announcement_id = created.json()["id"]

    update_forbidden = client.patch(
        api_path(f"/announcements/{announcement_id}"),
        headers=user_headers,
        json=_payload(title="User Update"),
    )
    assert update_forbidden.status_code == 403

    delete_forbidden = client.delete(api_path(f"/announcements/{announcement_id}"), headers=user_headers)
    assert delete_forbidden.status_code == 403


def test_announcements_reject_invalid_publish_window(client, admin_headers):
    resp = client.post(
        api_path("/announcements"),
        headers=admin_headers,
        json=_payload(
            title="Bad Window",
            publish_from="2026-06-15T10:00:00Z",
            publish_to="2026-06-14T10:00:00Z",
        ),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert resp.json()["error"]["message"] == "publish_from must be less than or equal to publish_to"


def test_announcements_list_supports_server_side_filters_sort_and_total(client, admin_headers):
    now = datetime.now(UTC)
    payloads = [
        _payload(title="Alpha Notice", publish_from=(now - timedelta(days=1)).isoformat()),
        _payload(title="Beta Notice", status="inactive"),
        _payload(title="Alpha Maintenance", publish_to=(now + timedelta(days=1)).isoformat()),
    ]
    for payload in payloads:
        resp = client.post(api_path("/announcements"), headers=admin_headers, json=payload)
        assert resp.status_code == 201

    listed = client.get(
        api_path("/announcements?scope=all&title=alpha&sort_by=title&sort_dir=asc&page=1&page_size=1"),
        headers=admin_headers,
    )
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert [item["title"] for item in body["items"]] == ["Alpha Maintenance"]

    next_page = client.get(
        api_path("/announcements?scope=all&title=alpha&sort_by=title&sort_dir=asc&page=2&page_size=1"),
        headers=admin_headers,
    )
    assert next_page.status_code == 200
    assert [item["title"] for item in next_page.json()["items"]] == ["Alpha Notice"]


def test_announcements_mutations_and_failures_write_audit_logs(client, admin_headers):
    created = client.post(api_path("/announcements"), headers=admin_headers, json=_payload(title="Audit Create"))
    assert created.status_code == 201
    announcement_id = created.json()["id"]

    updated = client.patch(
        api_path(f"/announcements/{announcement_id}"),
        headers=admin_headers,
        json=_payload(title="Audit Update", status="inactive"),
    )
    assert updated.status_code == 200

    invalid = client.patch(
        api_path(f"/announcements/{announcement_id}"),
        headers=admin_headers,
        json=_payload(
            title="Audit Update",
            publish_from="2026-06-15T10:00:00Z",
            publish_to="2026-06-14T10:00:00Z",
        ),
    )
    assert invalid.status_code == 422

    deleted = client.delete(api_path(f"/announcements/{announcement_id}"), headers=admin_headers)
    assert deleted.status_code == 204

    db = next(client.app.dependency_overrides[get_db]())
    try:
        rows = db.query(OperationAuditLog).filter(OperationAuditLog.event_type == "announcement_management").all()
    finally:
        db.close()

    actions = {(row.action, row.result) for row in rows}
    assert ("create", "success") in actions
    assert ("update", "success") in actions
    assert ("update", "failure") in actions
    assert ("delete", "success") in actions
    success_create = next(row for row in rows if row.action == "create" and row.result == "success")
    assert json.loads(success_create.metadata_json)["announcement_id"] == announcement_id
