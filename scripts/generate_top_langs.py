"""Generate a recent-languages SVG card from active GitHub repositories.

Counts bytes per language across non-fork, non-archived repositories the user
has pushed to in the last 30 days. This avoids letting old large repositories
misrepresent the languages used in current work.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

USERNAME = "Kensuke-sam"
EXCLUDE_REPOS = {
    "baito-kuchikomi",
    "claw-wrap",
    "claw-code",
    "floorp-ios",
}
EXCLUDE_LANGUAGES = {
    "Jupyter Notebook",
}
TOP_N = 5
RECENT_DAYS = 30
OUT_PATH = Path(__file__).resolve().parent.parent / "assets" / "top-langs.svg"

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
    "PLpgSQL": "#336790",
    "Dockerfile": "#384d54",
    "Makefile": "#427819",
    "GDShader": "#7a37b8",
    "Ruby": "#701516",
    "C": "#555555",
    "Objective-C": "#438eff",
}
FALLBACK_COLOR = "#858585"


def gh_graphql(query: str, variables: dict, token: str) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "kensuke-sam-top-langs",
        },
    )
    with urllib.request.urlopen(req) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]


QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    repositories(
      first: 100
      after: $cursor
      ownerAffiliations: OWNER
      isFork: false
      isArchived: false
      orderBy: {field: UPDATED_AT, direction: DESC}
    ) {
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        pushedAt
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def fetch_language_totals(
    token: str, now: datetime | None = None
) -> tuple[dict[str, int], int]:
    totals: dict[str, int] = {}
    active_repositories = 0
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=RECENT_DAYS)
    cursor: str | None = None
    while True:
        data = gh_graphql(QUERY, {"login": USERNAME, "cursor": cursor}, token)
        repos = data["user"]["repositories"]
        for repo in repos["nodes"]:
            pushed_at = repo["pushedAt"]
            if (
                repo["name"] in EXCLUDE_REPOS
                or pushed_at is None
                or datetime.fromisoformat(pushed_at.replace("Z", "+00:00")) < cutoff
            ):
                continue
            active_repositories += 1
            for edge in repo["languages"]["edges"]:
                name = edge["node"]["name"]
                if name in EXCLUDE_LANGUAGES:
                    continue
                totals[name] = totals.get(name, 0) + edge["size"]
        if not repos["pageInfo"]["hasNextPage"]:
            break
        cursor = repos["pageInfo"]["endCursor"]
    return totals, active_repositories


def render_svg(top: list[tuple[str, int, float]]) -> str:
    width = 467
    title_y = 34
    subtitle_y = 53
    bar_y = 72
    bar_height = 8
    bar_inner_width = width - 50
    legend_top = bar_y + bar_height + 28

    legend_cols = 2
    legend_col_w = (width - 50) // legend_cols
    legend_row_h = 28
    legend_rows = (len(top) + legend_cols - 1) // legend_cols
    height = legend_top + legend_rows * legend_row_h + 18

    bar_segments = []
    x_cursor = 25
    for name, _bytes, pct in top:
        seg_w = bar_inner_width * pct / 100
        color = LANG_COLORS.get(name, FALLBACK_COLOR)
        bar_segments.append(
            f'<rect x="{x_cursor:.2f}" y="{bar_y}" width="{seg_w:.2f}" '
            f'height="{bar_height}" fill="{color}" />'
        )
        x_cursor += seg_w

    legend_items = []
    for idx, (name, _bytes, pct) in enumerate(top):
        col = idx % legend_cols
        row = idx // legend_cols
        cx = 25 + col * legend_col_w + 6
        cy = legend_top + row * legend_row_h
        color = LANG_COLORS.get(name, FALLBACK_COLOR)
        legend_items.append(
            f'<circle cx="{cx}" cy="{cy}" r="5" fill="{color}" />'
            f'<text x="{cx + 12}" y="{cy + 4}" fill="#c9d1d9" '
            f'font-family="Segoe UI, Ubuntu, Sans-Serif" font-size="12">'
            f'{name} {pct:.2f}%</text>'
        )

    bg = "#0d1117"
    title_color = "#58a6ff"
    track_color = "#1f2933"

    svg = f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img">
  <title>Recently Used Languages</title>
  <rect width="{width}" height="{height}" rx="6" fill="{bg}" />
  <text x="25" y="{title_y}" fill="{title_color}" font-family="Segoe UI, Ubuntu, Sans-Serif" font-size="18" font-weight="600">Recently Used Languages</text>
  <text x="25" y="{subtitle_y}" fill="#8b949e" font-family="Segoe UI, Ubuntu, Sans-Serif" font-size="12">Repositories pushed in the last {RECENT_DAYS} days</text>
  <rect x="25" y="{bar_y}" width="{bar_inner_width}" height="{bar_height}" rx="4" fill="{track_color}" />
  {''.join(bar_segments)}
  {''.join(legend_items)}
</svg>
"""
    return svg


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("GITHUB_TOKEN or GH_TOKEN env var is required", file=sys.stderr)
        return 1

    totals, active_repositories = fetch_language_totals(token)
    if not totals:
        print("No language data found", file=sys.stderr)
        return 1

    total_bytes = sum(totals.values())
    sorted_langs = sorted(totals.items(), key=lambda x: -x[1])
    top_raw = sorted_langs[:TOP_N]
    top_total = sum(size for _, size in top_raw)
    top = [(name, size, size / top_total * 100) for name, size in top_raw]

    print(f"Active repositories scanned: {active_repositories}")
    print(f"Total bytes scanned: {total_bytes:,}")
    for name, size, pct in top:
        print(f"  {name:<14} {size:>10,} bytes  {pct:6.2f}%")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(render_svg(top), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
