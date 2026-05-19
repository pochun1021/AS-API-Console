from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run_alembic_upgrade_head() -> None:
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("alembic upgrade head failed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Setup local development DB: run migration then optional seed data."
    )
    parser.add_argument(
        "--skip-migrate",
        action="store_true",
        help="Skip alembic migration step.",
    )
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        help="Skip seed step.",
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Seed in append mode; do not clear existing seed scope.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.skip_migrate:
        run_alembic_upgrade_head()
        print("Migration completed: alembic upgrade head")

    if not args.skip_seed:
        try:
            from scripts.seed_test_data import seed_small
        except ImportError as exc:
            raise RuntimeError(
                "Failed to import seed script. Use Python 3.11+ (or `uv run`) to execute seed flow."
            ) from exc
        reset = not args.no_reset
        result = seed_small(reset=reset)
        print(
            "Seed completed: "
            f"admins={result['admins']}, "
            f"whitelists={result['whitelists']}, "
            f"applications={result['applications']}, "
            f"api_keys={result['api_keys']}, "
            f"reset={reset}"
        )


if __name__ == "__main__":
    main()
