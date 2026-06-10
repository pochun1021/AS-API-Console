from pathlib import Path


def test_deploy_full_script_installs_usage_sync_cron() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts" / "deploy_full.sh"
    content = script.read_text(encoding="utf-8")

    assert "USAGE_JOB=" in content
    assert "run_usage_sync.sh" in content
    assert 'ensure_job "$USAGE_JOB"' in content


def test_deploy_full_script_installs_institute_sync_cron_via_wrapper_script() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts" / "deploy_full.sh"
    content = script.read_text(encoding="utf-8")

    assert 'INSTITUTE_JOB="20 0 * * * ENV_FILE=${RESOLVED_ENV_FILE_PATH} ${APP_DIR}/backend/scripts/run_institute_sync.sh"' in content
    assert 'LEGACY_INSTITUTE_JOB="20 0 * * * ${APP_DIR}/backend/scripts/run_institute_sync.sh"' in content
    assert 'ensure_job "$INSTITUTE_JOB"' in content
