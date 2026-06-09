from pathlib import Path


def test_deploy_full_script_installs_usage_sync_cron() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts" / "deploy_full.sh"
    content = script.read_text(encoding="utf-8")

    assert "USAGE_JOB=" in content
    assert "run_usage_sync.sh" in content
    assert 'ensure_job "$USAGE_JOB"' in content
