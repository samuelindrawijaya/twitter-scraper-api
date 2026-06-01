#!/usr/bin/env python3
"""Friendly twscrape auth helper for this project.

This wraps twscrape's cookie-based account store so you do not have to
remember raw twscrape commands. It does not bypass X/Twitter login,
CAPTCHAs, or protections; it only stores cookies from a browser session
that you already control.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import sys
from pathlib import Path
from typing import Any

from twscrape import API, AccountsPool

DEFAULT_DB = "accounts.db"
DEFAULT_VERIFY_QUERY = "from:TwitterDev"
REQUIRED_COOKIE_NAMES = {"auth_token", "ct0"}


def normalize_cookie_string(cookie_string: str) -> str:
    """Return a compact cookie string and validate required twscrape cookies."""
    cookie_string = cookie_string.strip()
    if not cookie_string:
        raise ValueError("Cookie string is empty")

    cookies: dict[str, str] = {}
    for part in cookie_string.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        value = value.strip()
        if name:
            cookies[name] = value

    missing = sorted(REQUIRED_COOKIE_NAMES - set(cookies))
    if missing:
        raise ValueError(
            "Cookie string is missing required cookie(s): "
            + ", ".join(missing)
            + ". Open x.com while logged in and copy at least auth_token and ct0."
        )

    # Keep all pasted cookies; twscrape can use auth_token/ct0 and ignores extras.
    return "; ".join(f"{name}={value}" for name, value in cookies.items())


def extract_cookies_from_json(data: Any) -> dict[str, str]:
    """Extract cookie name/value pairs from common browser export formats."""
    cookies: dict[str, str] = {}

    def visit(obj: Any) -> None:
        if isinstance(obj, dict):
            name = obj.get("name")
            value = obj.get("value")
            if isinstance(name, str) and value is not None:
                cookies[name] = str(value)

            # Common containers: {"cookies": [...]}, Playwright storageState, etc.
            for key in ("cookies", "Cookie", "cookie", "data"):
                if key in obj:
                    visit(obj[key])
        elif isinstance(obj, list):
            for item in obj:
                visit(item)

    visit(data)
    return cookies


def load_cookie_json(path: Path) -> str:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    cookies = extract_cookies_from_json(data)
    missing = sorted(REQUIRED_COOKIE_NAMES - set(cookies))
    if missing:
        raise ValueError(
            f"{path} does not contain required cookie(s): {', '.join(missing)}. "
            "Export cookies for x.com/twitter.com while logged in."
        )

    # Prefer the two required cookies to avoid storing a huge browser export.
    return "; ".join(f"{name}={cookies[name]}" for name in sorted(REQUIRED_COOKIE_NAMES))


def print_accounts(items: list[dict[str, Any]]) -> None:
    if not items:
        print("No twscrape accounts found.")
        print("Add one with: python auth.py add-cookie <username>")
        return

    headers = ["username", "active", "logged_in", "total_req", "last_used", "error_msg"]
    rows = []
    for item in items:
        rows.append(
            {
                "username": str(item.get("username", "")),
                "active": "yes" if item.get("active") else "no",
                "logged_in": "yes" if item.get("logged_in") else "no",
                "total_req": str(item.get("total_req", 0)),
                "last_used": str(item.get("last_used") or ""),
                "error_msg": str(item.get("error_msg") or ""),
            }
        )

    widths = {header: len(header) for header in headers}
    for row in rows:
        for header in headers:
            widths[header] = max(widths[header], len(row[header]))

    print("  ".join(header.ljust(widths[header]) for header in headers))
    print("  ".join("-" * widths[header] for header in headers))
    for row in rows:
        print("  ".join(row[header].ljust(widths[header]) for header in headers))


async def cmd_status(args: argparse.Namespace) -> int:
    pool = AccountsPool(args.db)
    items = [dict(item) for item in await pool.accounts_info()]
    print_accounts(items)

    active_count = sum(1 for item in items if item.get("active"))
    print()
    print(f"Database: {args.db}")
    print(f"Total accounts: {len(items)} | Active accounts: {active_count}")
    if active_count == 0:
        print("Warning: no active account is available for scraping.")
        return 1
    return 0


async def cmd_add_cookie(args: argparse.Namespace) -> int:
    cookie_string = args.cookies
    if not cookie_string:
        print("Paste your X/Twitter cookie string.")
        print("It must include at least: auth_token=...; ct0=...")
        cookie_string = getpass.getpass("cookies: ")

    cookie_string = normalize_cookie_string(cookie_string)
    pool = AccountsPool(args.db)

    existing = await pool.get_account(args.username)
    if existing is not None and not args.replace:
        print(f"Account '{args.username}' already exists in {args.db}.")
        print("Use --replace to overwrite it with new cookies.")
        return 1
    if existing is not None and args.replace:
        await pool.delete_accounts([args.username])

    await pool.add_account_cookies(args.username, cookie_string)
    account = await pool.get_account(args.username)
    print(f"Added account: {args.username}")
    print(f"Active: {'yes' if account and account.active else 'no'}")
    print("Next: python auth.py verify")
    return 0


async def cmd_import_cookie_json(args: argparse.Namespace) -> int:
    cookie_path = Path(args.path).expanduser()
    cookie_string = load_cookie_json(cookie_path)

    pool = AccountsPool(args.db)
    existing = await pool.get_account(args.username)
    if existing is not None and not args.replace:
        print(f"Account '{args.username}' already exists in {args.db}.")
        print("Use --replace to overwrite it with cookies from the JSON file.")
        return 1
    if existing is not None and args.replace:
        await pool.delete_accounts([args.username])

    await pool.add_account_cookies(args.username, cookie_string)
    account = await pool.get_account(args.username)
    print(f"Imported cookies from: {cookie_path}")
    print(f"Added account: {args.username}")
    print(f"Active: {'yes' if account and account.active else 'no'}")
    print("Next: python auth.py verify")
    return 0


async def cmd_verify(args: argparse.Namespace) -> int:
    pool = AccountsPool(args.db, raise_when_no_account=True)
    api = API(pool)

    print(f"Verifying twscrape auth using query: {args.query!r}")
    try:
        count = 0
        async for tweet in api.search(args.query, limit=args.limit):
            count += 1
            text = getattr(tweet, "rawContent", None) or getattr(tweet, "text", "") or ""
            tweet_id = getattr(tweet, "id", "")
            username = getattr(getattr(tweet, "user", None), "username", "")
            print(f"OK: @{username} tweet_id={tweet_id} text={text[:100]!r}")
            if count >= args.limit:
                break
    except Exception as exc:
        print("Verification failed.")
        print(f"Error: {exc}")
        print()
        print("Try refreshing your browser cookies and then run:")
        print("  python auth.py add-cookie <username> --replace")
        return 1

    if count == 0:
        print("Auth connected, but the verify query returned 0 tweets.")
        print("Try another public query, for example:")
        print('  python auth.py verify --query "python lang:en"')
        return 1

    print(f"Verification succeeded: fetched {count} tweet(s).")
    return 0


async def cmd_delete_account(args: argparse.Namespace) -> int:
    pool = AccountsPool(args.db)
    await pool.delete_accounts([args.username])
    print(f"Deleted account from {args.db}: {args.username}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Friendly twscrape cookie-auth helper for twitter_scraper_api."
    )
    parser.add_argument(
        "--db",
        default=DEFAULT_DB,
        help=f"twscrape accounts database path (default: {DEFAULT_DB})",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Show configured twscrape accounts")
    status.set_defaults(func=cmd_status)

    add_cookie = subparsers.add_parser("add-cookie", help="Add/update one account from a pasted cookie string")
    add_cookie.add_argument("username", help="X/Twitter username for this cookie")
    add_cookie.add_argument("cookies", nargs="?", help="Optional cookie string; omitted = secure prompt")
    add_cookie.add_argument("--replace", action="store_true", help="Replace existing account with same username")
    add_cookie.set_defaults(func=cmd_add_cookie)

    import_json = subparsers.add_parser(
        "import-cookie-json",
        help="Import auth_token and ct0 from a browser-exported cookies JSON file",
    )
    import_json.add_argument("path", help="Path to cookies JSON file, e.g. twitter_cookie.json")
    import_json.add_argument("username", help="X/Twitter username for this cookie")
    import_json.add_argument("--replace", action="store_true", help="Replace existing account with same username")
    import_json.set_defaults(func=cmd_import_cookie_json)

    verify = subparsers.add_parser("verify", help="Run a tiny public search to confirm auth works")
    verify.add_argument("--query", default=DEFAULT_VERIFY_QUERY, help=f"Public search query (default: {DEFAULT_VERIFY_QUERY!r})")
    verify.add_argument("--limit", type=int, default=1, help="Number of tweets to fetch (default: 1)")
    verify.set_defaults(func=cmd_verify)

    delete = subparsers.add_parser("delete-account", help="Delete one account from accounts.db")
    delete.add_argument("username", help="X/Twitter username to delete")
    delete.set_defaults(func=cmd_delete_account)

    return parser


async def async_main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return await args.func(args)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
