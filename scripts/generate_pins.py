"""Generate per-repository pin SVG cards for the README Featured Work section.

Mirrors the visual style of the self-hosted stats / top-languages cards so the
README has no runtime dependency on third-party rendering services.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from html import escape
from pathlib import Path

USERNAME = "Kensuke-sam"
REPOS = ["twitter-cli-bot", "twitter-ai-agent", "koteihi-zero", "catbento"]
OUT_DIR = Path(__file__).resolve().parent.parent / "assets"

BG = "#0d1117"
TITLE_COLOR = "#58a6ff"
TEXT_COLOR = "#c9d1d9"
ICON_COLOR = "#f59e0b"

LANG_COLORS = {
    "Python": "#3572A5",
    "TypeScript": "#3178c6",
    "JavaScript": "#f1e05a",
    "Swift": "#F05138",
    "Rust": "#dea584",
    "CSS": "#563d7c",
    "HTML": "#e34c26",
    "GDScript": "#355570",
    "Java": "#b07219",
    "Shell": "#89e051",
}
FALLBACK_COLOR = "#858585"

STAR_ICON = (
    "M12 .288l3.708 7.515 8.292 1.205-6 5.85 1.416 8.262L12 19.04l-7.416 "
    "3.084L6 13.858 0 8.008l8.292-1.205L12 .288z"
)
FORK_ICON = (
    "M5 5.372v.878c0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75v-.878a2.25 "
    "2.25 0 1 1 1.5 0v.878a2.25 2.25 0 0 1-2.25 2.25h-1.5v2.128a2.251 2.251 "
    "0 1 1-1.5 0V8.5h-1.5A2.25 2.25 0 0 1 3.5 6.25v-.878a2.25 2.25 0 1 1 "
    "1.5 0zM5 3.25a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0zm6.75.75a.75.75 0 "
    "1 0 0-1.5.75.75 0 0 0 0 1.5zm-3 8.75a.75.75 0 1 0-1.5 0 .75.75 0 0 0 "
    "1.5 0z"
)

QUERY = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    name
    description
    stargazerCount
    forkCount
    primaryLanguage { name color }
  }
}
"""


def gh_graphql(query: str, variables: dict, token: str) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "kensuke-sam-pins",
        },
    )
    with urllib.request.urlopen(req) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]


def _is_cjk(ch: str) -> bool:
    code = ord(ch)
    return (
        0x3000 <= code <= 0x9FFF
        or 0xAC00 <= code <= 0xD7AF
        or 0xFF00 <= code <= 0xFFEF
    )


def wrap_text(text: str, max_chars: int, max_lines: int) -> list[str]:
    if not text:
        return []
    text = text.strip()
    lines: list[str] = []
    current = ""
    pending = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == " " or _is_cjk(ch):
            chunk = pending + ch
            pending = ""
        else:
            pending += ch
            i += 1
            if i < len(text):
                continue
            chunk = pending
            pending = ""

        if len(current) + len(chunk) <= max_chars:
            current += chunk
        else:
            if current:
                lines.append(current.rstrip())
                if len(lines) == max_lines:
                    last = lines[-1]
                    if len(last) > 1:
                        lines[-1] = last[:-1] + "…"
                    return lines
            current = chunk.lstrip()
        if ch == " " or _is_cjk(ch):
            i += 1

    if pending and len(current) + len(pending) <= max_chars:
        current += pending
        pending = ""

    if current:
        lines.append(current.rstrip())
    if pending and len(lines) < max_lines:
        lines.append(pending)

    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        if len(last) > 1:
            lines[-1] = last[:-1] + "…"
    return lines


def build_svg(
    name: str,
    description: str | None,
    language: str,
    lang_color: str | None,
    stars: int,
    forks: int,
) -> str:
    width = 400
    height = 120
    title_y = 30
    desc_top = 52
    desc_line_h = 16
    footer_y = 100

    desc_lines = wrap_text(description or "", max_chars=52, max_lines=2)

    desc_parts: list[str] = []
    for idx, line in enumerate(desc_lines):
        desc_parts.append(
            f'<text x="25" y="{desc_top + idx * desc_line_h}" fill="{TEXT_COLOR}" '
            f'font-family="Segoe UI, Ubuntu, Sans-Serif" font-size="12">'
            f"{escape(line)}</text>"
        )

    lang_part = ""
    cursor_x = 25
    if language:
        color = lang_color or LANG_COLORS.get(language, FALLBACK_COLOR)
        lang_part = (
            f'<circle cx="{cursor_x + 6}" cy="{footer_y - 4}" r="6" fill="{color}" />'
            f'<text x="{cursor_x + 18}" y="{footer_y}" fill="{TEXT_COLOR}" '
            f'font-family="Segoe UI, Ubuntu, Sans-Serif" font-size="12">'
            f"{escape(language)}</text>"
        )
        cursor_x += 18 + len(language) * 7 + 20

    star_part = (
        f'<g transform="translate({cursor_x} {footer_y - 13}) scale(0.55)" fill="{ICON_COLOR}">'
        f'<path d="{STAR_ICON}" /></g>'
        f'<text x="{cursor_x + 18}" y="{footer_y}" fill="{TEXT_COLOR}" '
        f'font-family="Segoe UI, Ubuntu, Sans-Serif" font-size="12">{stars}</text>'
    )
    cursor_x += 18 + len(str(stars)) * 7 + 16

    fork_part = ""
    if forks > 0:
        fork_part = (
            f'<g transform="translate({cursor_x} {footer_y - 12}) scale(0.85)" fill="{ICON_COLOR}">'
            f'<path d="{FORK_ICON}" /></g>'
            f'<text x="{cursor_x + 18}" y="{footer_y}" fill="{TEXT_COLOR}" '
            f'font-family="Segoe UI, Ubuntu, Sans-Serif" font-size="12">{forks}</text>'
        )

    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img">
  <title>{escape(name)}</title>
  <rect width="{width}" height="{height}" rx="6" fill="{BG}" />
  <text x="25" y="{title_y}" fill="{TITLE_COLOR}" font-family="Segoe UI, Ubuntu, Sans-Serif" font-size="15" font-weight="600">{escape(name)}</text>
  {''.join(desc_parts)}
  {lang_part}
  {star_part}
  {fork_part}
</svg>
"""


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("GITHUB_TOKEN or GH_TOKEN env var is required", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for repo in REPOS:
        data = gh_graphql(QUERY, {"owner": USERNAME, "name": repo}, token)
        r = data["repository"]
        if not r:
            print(f"WARN: {repo} not found, skipping", file=sys.stderr)
            continue

        primary_lang = r.get("primaryLanguage") or {}
        svg = build_svg(
            name=r["name"],
            description=r.get("description"),
            language=primary_lang.get("name") or "",
            lang_color=primary_lang.get("color"),
            stars=r["stargazerCount"],
            forks=r["forkCount"],
        )
        out_path = OUT_DIR / f"pin-{repo}.svg"
        out_path.write_text(svg, encoding="utf-8")
        print(f"Wrote {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
