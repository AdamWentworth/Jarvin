from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import requests

import config as cfg
from backend.agent.integration_models import WebPageExtract, WebResearchResult, WebSearchItem, WebSearchResult

DUCKDUCKGO_LITE_URL = "https://lite.duckduckgo.com/lite/"
GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"
SEARCH_USER_AGENT = "Jarvin/1.0 (+https://jarvin.local)"
MAX_WEB_PAGE_CHARS = 7000
MAX_WEB_PAGES_PER_QUERY = 3

_RESULT_LINK_RE = re.compile(r'<a[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>', re.IGNORECASE | re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def google_search_is_configured() -> bool:
    return bool(str(cfg.settings.google_search_api_key or "").strip() and str(cfg.settings.google_search_engine_id or "").strip())


def search_web(query: str, *, max_results: int = 5) -> WebSearchResult:
    q = str(query or "").strip()
    if not q:
        raise ValueError("Search query cannot be empty.")

    provider = str(cfg.settings.agent_web_search_provider or "duckduckgo_lite").strip().lower()
    if provider == "google_cse":
        return _google_cse_search(q, max_results=max_results)
    return _duckduckgo_lite_search(q, max_results=max_results)


def browse_search_results(
    query: str,
    *,
    max_results: int = 5,
    max_pages: int = MAX_WEB_PAGES_PER_QUERY,
) -> WebResearchResult:
    results = search_web(query, max_results=max(max_results, max_pages))
    pages: list[WebPageExtract] = []
    for item in results.items:
        if len(pages) >= max(1, int(max_pages)):
            break
        try:
            page = fetch_web_page(item.url, fallback_title=item.title)
        except Exception:
            continue
        if page.excerpt:
            pages.append(page)
    return WebResearchResult(
        provider=results.provider,
        query=results.query,
        items=results.items,
        pages=pages,
    )


def fetch_web_page(url: str, *, fallback_title: str = "") -> WebPageExtract:
    target = str(url or "").strip()
    if not target:
        raise ValueError("Web page URL cannot be empty.")

    response = requests.get(
        target,
        timeout=cfg.settings.agent_command_timeout_sec,
        headers={"User-Agent": SEARCH_USER_AGENT},
    )
    response.raise_for_status()
    content_type = str(response.headers.get("content-type") or "").lower()
    text = response.text or ""
    if "html" in content_type or "<html" in text.lower():
        parsed_title, excerpt = _extract_html_page(text)
    else:
        parsed_title = fallback_title or target
        excerpt = _normalize_text_block(text)

    excerpt = excerpt[:MAX_WEB_PAGE_CHARS].strip()
    if not excerpt:
        raise ValueError(f"No readable text was extracted from {target}.")

    return WebPageExtract(
        url=target,
        title=parsed_title or fallback_title or _display_url(target),
        excerpt=excerpt,
    )


def _duckduckgo_lite_search(query: str, *, max_results: int) -> WebSearchResult:
    response = requests.post(
        DUCKDUCKGO_LITE_URL,
        data={"q": query},
        timeout=cfg.settings.agent_command_timeout_sec,
        headers={"User-Agent": "Jarvin/1.0"},
    )
    response.raise_for_status()
    items: list[WebSearchItem] = []
    for match in _RESULT_LINK_RE.finditer(response.text):
        href = match.group("href")
        if not href.startswith("http"):
            continue
        title = _clean_html(match.group("title"))
        items.append(WebSearchItem(title=title or href, url=href, snippet=""))
        if len(items) >= max_results:
            break
    if not items:
        raise ValueError("No web results were returned by the configured search provider.")
    return WebSearchResult(provider="duckduckgo_lite", query=query, items=items)


def _google_cse_search(query: str, *, max_results: int) -> WebSearchResult:
    api_key = str(cfg.settings.google_search_api_key or "").strip()
    search_engine_id = str(cfg.settings.google_search_engine_id or "").strip()
    if not api_key or not search_engine_id:
        raise ValueError(
            "Google web search is configured, but the host is missing JARVIN_GOOGLE_SEARCH_API_KEY "
            "or JARVIN_GOOGLE_SEARCH_ENGINE_ID."
        )

    response = requests.get(
        GOOGLE_CSE_URL,
        params={"key": api_key, "cx": search_engine_id, "q": query, "num": max(1, min(max_results, 10))},
        timeout=cfg.settings.agent_command_timeout_sec,
    )
    response.raise_for_status()
    payload = response.json()
    items = [
        WebSearchItem(
            title=item.get("title") or item.get("link") or "(untitled result)",
            url=item.get("link") or "",
            snippet=item.get("snippet") or "",
        )
        for item in payload.get("items", [])
        if item.get("link")
    ]
    if not items:
        raise ValueError("Google search did not return any results.")
    return WebSearchResult(provider="google_cse", query=query, items=items)


class _ReadableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._capture_title = False
        self._title_chunks: list[str] = []
        self._text_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "svg", "noscript"}:
            self._skip_depth += 1
            return
        if lowered == "title":
            self._capture_title = True
        if lowered in {"p", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "blockquote", "pre", "br"}:
            self._text_chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "svg", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if lowered == "title":
            self._capture_title = False
        if lowered in {"p", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "blockquote", "pre"}:
            self._text_chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        cleaned = str(data or "").strip()
        if not cleaned:
            return
        if self._capture_title:
            self._title_chunks.append(cleaned)
        self._text_chunks.append(cleaned)

    @property
    def title(self) -> str:
        return _normalize_text_block(" ".join(self._title_chunks))

    @property
    def text(self) -> str:
        return _normalize_text_block("\n".join(self._text_chunks))


def _clean_html(text: str) -> str:
    stripped = _HTML_TAG_RE.sub("", text)
    return stripped.replace("&amp;", "&").replace("&quot;", '"').strip()


def _extract_html_page(html: str) -> tuple[str, str]:
    parser = _ReadableHTMLParser()
    parser.feed(html)
    parser.close()
    return parser.title, _select_relevant_excerpt(parser.text)


def _select_relevant_excerpt(text: str, *, max_blocks: int = 8) -> str:
    lines = [line.strip() for line in text.splitlines()]
    kept: list[str] = []
    seen: set[str] = set()
    for line in lines:
        normalized = _normalize_text_block(line)
        if len(normalized) < 35:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        if any(
            noise in lowered
            for noise in (
                "cookie",
                "privacy policy",
                "terms of service",
                "sign in",
                "log in",
                "all rights reserved",
                "advertisement",
                "subscribe",
            )
        ):
            continue
        kept.append(normalized)
        seen.add(lowered)
        if len(kept) >= max_blocks:
            break
    return "\n".join(kept)


def _normalize_text_block(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _display_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc or url
    path = parsed.path.rstrip("/")
    return f"{host}{path}"

