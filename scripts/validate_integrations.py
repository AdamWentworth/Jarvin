from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config as cfg  # noqa: E402
from backend.agent.integration_facade import (  # noqa: E402
    browse_search_results,
    google_calendar_credentials_configured,
    google_calendar_token_available,
    google_search_is_configured,
)


def _mask_secret(value: str, *, visible: int = 4) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "(missing)"
    if len(raw) <= visible:
        return "*" * len(raw)
    return f"{raw[:visible]}{'*' * max(4, len(raw) - visible)}"


def _print_header(title: str) -> None:
    print()
    print(f"[{title}]")


def _validate_search(query: str) -> int:
    _print_header("search-config")
    print(f"provider={cfg.settings.agent_web_search_provider}")
    print(f"api_key={_mask_secret(cfg.settings.google_search_api_key)}")
    print(f"search_engine_id={_mask_secret(cfg.settings.google_search_engine_id)}")

    provider = str(cfg.settings.agent_web_search_provider or "").strip().lower()
    if provider == "google_cse" and not google_search_is_configured():
        print("status=fail")
        print("reason=Google CSE is the active provider, but the API key or Search Engine ID is missing.")
        return 1

    _print_header("search-request")
    print(f"query={query}")

    try:
        research = browse_search_results(query)
    except requests.HTTPError as exc:
        print("status=fail")
        print(f"reason={exc}")
        response = getattr(exc, "response", None)
        if response is not None:
            body = (response.text or "").strip()
            if body:
                print(f"response_body={body[:1200]}")
        return 1
    except Exception as exc:
        print("status=fail")
        print(f"reason={exc}")
        return 1

    print("status=ok")
    print(f"provider={research.provider}")
    print(f"results={len(research.items)}")
    print(f"pages_read={len(research.pages)}")

    _print_header("top-results")
    for index, item in enumerate(research.items[:5], start=1):
        snippet = item.snippet.strip() if item.snippet else ""
        print(f"{index}. {item.title}")
        print(f"   url={item.url}")
        if snippet:
            print(f"   snippet={snippet}")

    if research.pages:
        _print_header("page-excerpts")
        for index, page in enumerate(research.pages[:3], start=1):
            excerpt = " ".join(page.excerpt.split())
            excerpt = excerpt[:280].rstrip()
            print(f"{index}. {page.title}")
            print(f"   url={page.url}")
            print(f"   excerpt={excerpt}")

    return 0


def _validate_calendar() -> int:
    _print_header("calendar-config")
    print(f"credentials_file={Path(cfg.settings.google_calendar_credentials_file).resolve()}")
    print(f"token_file={Path(cfg.settings.google_calendar_token_file).resolve()}")
    print(f"calendar_id={cfg.settings.google_calendar_id}")

    creds_ok = google_calendar_credentials_configured()
    token_ok = google_calendar_token_available()

    print(f"credentials_present={str(creds_ok).lower()}")
    print(f"token_present={str(token_ok).lower()}")

    if not creds_ok:
        print("status=fail")
        print("reason=Missing Google Calendar OAuth client JSON.")
        return 1

    if not token_ok:
        print("status=warn")
        print("reason=Calendar credentials exist, but the host has not been authorized yet.")
        return 0

    print("status=ok")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Jarvin external integrations like Google search and Google Calendar."
    )
    parser.add_argument(
        "--query",
        default="llama.cpp windows cuda docs",
        help="Search query to use when validating web search.",
    )
    parser.add_argument(
        "--search-only",
        action="store_true",
        help="Only validate web search.",
    )
    parser.add_argument(
        "--calendar-only",
        action="store_true",
        help="Only validate Google Calendar configuration.",
    )
    args = parser.parse_args()

    if args.search_only and args.calendar_only:
        print("Choose either --search-only or --calendar-only, not both.")
        return 2

    exit_code = 0
    if not args.calendar_only:
        exit_code = max(exit_code, _validate_search(args.query))
    if not args.search_only:
        exit_code = max(exit_code, _validate_calendar())
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

