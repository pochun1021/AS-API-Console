from __future__ import annotations

import argparse
import importlib
import logging
from pathlib import Path

import pytest


sync_module = importlib.import_module("scripts.sync_expired_api_keys")


@pytest.fixture()
def isolated_logger(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    logger_name = f"{sync_module.LOGGER_NAME}.test"
    monkeypatch.setattr(sync_module, "LOGGER_NAME", logger_name)
    monkeypatch.setattr(sync_module, "LOG_DIR", tmp_path / "log" / "sync_expired_api_keys")
    logger = logging.getLogger(logger_name)
    logger.handlers.clear()
    return sync_module.LOG_DIR


def test_main_writes_console_and_daily_log_success(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], isolated_logger: Path
) -> None:
    monkeypatch.setattr(sync_module, "parse_args", lambda: argparse.Namespace(batch_size=123, dry_run=False))
    monkeypatch.setattr(sync_module, "run_once", lambda **kwargs: 9)

    sync_module.main()

    captured = capsys.readouterr()
    assert "expired-key-sync updated_count=9 batch_size=123" in captured.out

    log_files = list(isolated_logger.glob("*.log"))
    assert len(log_files) == 1
    content = log_files[0].read_text(encoding="utf-8")
    assert "level=INFO" in content
    assert "event=expired_key_sync mode=sync updated_count=9 batch_size=123 dry_run=False status=success" in content


def test_main_writes_daily_log_on_failure(monkeypatch: pytest.MonkeyPatch, isolated_logger: Path) -> None:
    monkeypatch.setattr(sync_module, "parse_args", lambda: argparse.Namespace(batch_size=77, dry_run=True))

    def raise_error(**kwargs: object) -> int:
        raise RuntimeError("db broken")

    monkeypatch.setattr(sync_module, "run_once", raise_error)

    with pytest.raises(SystemExit) as exc:
        sync_module.main()
    assert exc.value.code == 1

    log_files = list(isolated_logger.glob("*.log"))
    assert len(log_files) == 1
    content = log_files[0].read_text(encoding="utf-8")
    assert "level=ERROR" in content
    assert "event=expired_key_sync mode=dry-run batch_size=77 dry_run=True status=failed" in content
    assert "RuntimeError: db broken" in content
