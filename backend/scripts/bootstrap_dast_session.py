from __future__ import annotations

from argparse import ArgumentParser
import json
import sys

import httpx


def build_parser() -> ArgumentParser:
    parser = ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--account", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--department", required=True)
    parser.add_argument("--sysid", type=int, required=True)
    parser.add_argument("--role", choices=("user", "admin"), default="user")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    with httpx.Client(base_url=args.base_url, follow_redirects=False, timeout=10.0) as client:
        response = client.post(
            "/test/session-login",
            json={
                "account": args.account,
                "name": args.name,
                "email": args.email,
                "department": args.department,
                "sysid": args.sysid,
                "role": args.role,
            },
        )
        response.raise_for_status()
        body = response.json()
        cookie_header = "; ".join(f"{name}={value}" for name, value in client.cookies.items())
        if not cookie_header:
            raise RuntimeError("session cookie missing after test login")
        print(
            json.dumps(
                {
                    "cookie_header": cookie_header,
                    "csrf_token": body["csrf_token"],
                    "role": body["role"],
                    "account": body["account"],
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
