#!/usr/bin/env python3
"""Smoke-test DataHub authentication and retrieval without exposing response data."""

from __future__ import annotations

import argparse

from app.services.datahub_client import DataHubClient, DataHubError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    try:
        identifiers = DataHubClient().fetch_incomplete_sso()
    except DataHubError as exc:
        print(f"[FAIL] DataHub request failed: {exc.kind.value}")
        return 1
    except Exception as exc:
        # Do not print exception details: HTTP and settings errors may contain secrets.
        print(f"[FAIL] DataHub test failed: {type(exc).__name__}")
        return 1

    print(f"[PASS] DataHub token and list requests succeeded; unique SSO count: {len(identifiers)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
