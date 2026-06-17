from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from app.core.auth import CurrentUser
from app.core.config import get_settings
from app.core.errors import ApiError


LOG_TZ = ZoneInfo("Asia/Taipei")
ALLOWED_JOBS = {
    "sync_expired_api_keys",
    "sync_api_key_usage",
    "send_expiration_reminders",
}
ALLOWED_FILE_MODES = {"date", "all", "latest"}
ALLOWED_LEVELS = {"INFO", "WARNING", "ERROR", "CRITICAL"}
LINE_PATTERN = re.compile(r"^\[(?P<timestamp>[^\]]+)\]\s+level=(?P<level>[A-Z]+)\s*(?P<message>.*)$")
LOG_FILE_PATTERN = re.compile(r"^(?P<log_date>\d{4}-\d{2}-\d{2})\.log$")


@dataclass(slots=True)
class SchedulerLogRow:
    id: str
    job: str
    log_date: date
    source_file: str
    timestamp: datetime
    level: str
    message: str
    raw_line: str


class SchedulerLogQueryService:
    def __init__(self) -> None:
        settings = get_settings()
        self.log_root = Path(settings.scheduler_log_root)

    def list_logs(
        self,
        *,
        current_user: CurrentUser,
        page: int,
        page_size: int,
        job: str | None,
        file_mode: str,
        from_date: date | None,
        to_date: date | None,
        level: str | None,
        keyword: str | None,
        sort_dir: str,
    ) -> dict:
        if current_user.role != "admin":
            raise ApiError("FORBIDDEN", "admin role required", 403)
        if job is not None and job not in ALLOWED_JOBS:
            raise ApiError("VALIDATION_ERROR", "job is invalid", 422)
        if file_mode not in ALLOWED_FILE_MODES:
            raise ApiError("VALIDATION_ERROR", "file_mode is invalid", 422)
        if level is not None and level not in ALLOWED_LEVELS:
            raise ApiError("VALIDATION_ERROR", "level is invalid", 422)
        if sort_dir not in {"asc", "desc"}:
            raise ApiError("VALIDATION_ERROR", "sort_dir must be asc or desc", 422)

        jobs = [job] if job else sorted(ALLOWED_JOBS)
        rows: list[SchedulerLogRow] = []
        available_files = self._build_available_files(job_name=job) if job else []
        for job_name in jobs:
            rows.extend(
                self._read_job_logs(
                    job_name=job_name,
                    file_mode=file_mode,
                    from_date=from_date,
                    to_date=to_date,
                )
            )

        if level:
            rows = [row for row in rows if row.level == level]

        normalized_keyword = keyword.strip().lower() if keyword and keyword.strip() else None
        if normalized_keyword:
            rows = [
                row
                for row in rows
                if normalized_keyword in row.message.lower() or normalized_keyword in row.raw_line.lower()
            ]

        reverse = sort_dir == "desc"
        rows.sort(key=lambda row: (row.timestamp, row.id), reverse=reverse)

        total = len(rows)
        start = (page - 1) * page_size
        end = start + page_size
        page_rows = rows[start:end]
        return {
            "available_files": available_files,
            "items": [
                {
                    "id": row.id,
                    "job": row.job,
                    "log_date": row.log_date,
                    "source_file": row.source_file,
                    "timestamp": row.timestamp,
                    "level": row.level,
                    "message": row.message,
                    "raw_line": row.raw_line,
                }
                for row in page_rows
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    def _build_available_files(self, *, job_name: str) -> list[dict]:
        log_dir = self.log_root / job_name
        files = self._list_all_log_files(log_dir)
        files.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                "log_date": log_date,
                "source_file": log_file.name,
            }
            for log_date, log_file in files
        ]

    def _resolve_date_window(self, *, from_date: date | None, to_date: date | None) -> tuple[date, date]:
        if from_date is None and to_date is None:
            to_date = datetime.now(LOG_TZ).date()
            from_date = to_date - timedelta(days=6)
        elif from_date is None:
            from_date = to_date
        elif to_date is None:
            to_date = from_date
        if from_date is None or to_date is None or from_date > to_date:
            raise ApiError("VALIDATION_ERROR", "from must be earlier than or equal to to", 422)
        return from_date, to_date

    def _read_job_logs(
        self,
        *,
        job_name: str,
        file_mode: str,
        from_date: date | None,
        to_date: date | None,
    ) -> list[SchedulerLogRow]:
        log_dir = self.log_root / job_name
        if file_mode == "all":
            log_files = self._list_all_log_files(log_dir)
        elif file_mode == "latest":
            latest_file = self._find_latest_log_file(log_dir)
            log_files = [latest_file] if latest_file is not None else []
        else:
            resolved_from_date, resolved_to_date = self._resolve_date_window(from_date=from_date, to_date=to_date)
            log_files = self._expand_date_window_files(log_dir=log_dir, from_date=resolved_from_date, to_date=resolved_to_date)

        rows: list[SchedulerLogRow] = []
        for log_date, log_file in log_files:
            rows.extend(self._parse_log_file(job_name=job_name, log_date=log_date, log_file=log_file))
        return rows

    def _expand_date_window_files(
        self,
        *,
        log_dir: Path,
        from_date: date,
        to_date: date,
    ) -> list[tuple[date, Path]]:
        files: list[tuple[date, Path]] = []
        current = from_date
        while current <= to_date:
            log_file = log_dir / f"{current.isoformat()}.log"
            if log_file.exists():
                files.append((current, log_file))
            current += timedelta(days=1)
        return files

    def _list_all_log_files(self, log_dir: Path) -> list[tuple[date, Path]]:
        if not log_dir.exists():
            return []
        files: list[tuple[date, Path]] = []
        for entry in sorted(log_dir.iterdir()):
            parsed = self._parse_log_filename(entry)
            if parsed is not None:
                files.append(parsed)
        return files

    def _find_latest_log_file(self, log_dir: Path) -> tuple[date, Path] | None:
        files = self._list_all_log_files(log_dir)
        if not files:
            return None
        return max(files, key=lambda item: item[0])

    def _parse_log_filename(self, entry: Path) -> tuple[date, Path] | None:
        if not entry.is_file():
            return None
        matched = LOG_FILE_PATTERN.match(entry.name)
        if matched is None:
            return None
        try:
            parsed_date = date.fromisoformat(matched.group("log_date"))
        except ValueError:
            return None
        return parsed_date, entry

    def _parse_log_file(self, *, job_name: str, log_date: date, log_file: Path) -> list[SchedulerLogRow]:
        rows: list[SchedulerLogRow] = []
        with log_file.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                normalized_raw_line = raw_line.rstrip("\r\n")
                if not normalized_raw_line:
                    continue
                parsed = self._parse_log_line(normalized_raw_line)
                if parsed is None:
                    continue
                timestamp, level, message = parsed
                rows.append(
                    SchedulerLogRow(
                        id=f"{job_name}:{log_date.isoformat()}:{line_number}",
                        job=job_name,
                        log_date=log_date,
                        source_file=log_file.name,
                        timestamp=timestamp,
                        level=level,
                        message=message,
                        raw_line=normalized_raw_line,
                    )
                )
        return rows

    def _parse_log_line(self, raw_line: str) -> tuple[datetime, str, str] | None:
        matched = LINE_PATTERN.match(raw_line)
        if matched is None:
            return None
        timestamp_text = matched.group("timestamp").strip()
        level = matched.group("level").strip()
        if level not in ALLOWED_LEVELS:
            return None
        try:
            timestamp = datetime.fromisoformat(timestamp_text)
        except ValueError:
            return None
        message = matched.group("message").strip() or raw_line
        return timestamp, level, message
