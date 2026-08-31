"""Generate a compact year-to-date GitHub activity card for the profile README."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import sys
import urllib.request
from pathlib import Path

USERNAME = "Kensuke-sam"
OUT_PATH = Path(__file__).resolve().parent.parent / "assets" / "stats.svg"

BG = "#0d1117"
TITLE_COLOR = "#58a6ff"
TEXT_COLOR = "#c9d1d9"
MUTED_COLOR = "#8b949e"
DIVIDER_COLOR = "#30363d"

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { totalContributions }
      totalCommitContributions
      totalPullRequestContributions
      totalRepositoriesWithContributedCommits
    }
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
            "User-Agent": "kensuke-sam-profile-activity",
        },
    )
    with urllib.request.urlopen(req) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]


def fetch_summary(token: str, year: int) -> dict:
    now = datetime.now(timezone.utc)
    return gh_graphql(
        QUERY,
        {
            "login": USERNAME,
            "from": f"{year}-01-01T00:00:00Z",
            "to": now.isoformat().replace("+00:00", "Z"),
        },
        token,
    )["user"]["contributionsCollection"]


def fmt(value: int) -> str:
    return f"{value:,}"


def build_svg(
    contributions: int,
    commits: int,
    pull_requests: int,
    repositories: int,
    year: int,
) -> str:
    metrics = [
        ("Contributions", contributions),
        ("Commits", commits),
        ("Pull requests", pull_requests),
        ("Repos contributed", repositories),
    ]

    width = 800
    height = 134
    padding = 28
    col_width = (width - padding * 2) / len(metrics)
    title_y = 34
    subtitle_y = 54
    value_y = 92
    label_y = 115

    cells: list[str] = []
    for index, (label, value) in enumerate(metrics):
        x = padding + col_width * index
        center_x = x + col_width / 2
        if index:
            cells.append(
                f'<line x1="{x:.1f}" y1="67" x2="{x:.1f}" y2="116" '
                f'stroke="{DIVIDER_COLOR}" />'
            )
        cells.append(
            f'<text x="{center_x:.1f}" y="{value_y}" fill="{TEXT_COLOR}" '
            f'font-family="Segoe UI, Ubuntu, Sans-Serif" font-size="27" '
            f'font-weight="700" text-anchor="middle">{fmt(value)}</text>'
        )
        cells.append(
            f'<text x="{center_x:.1f}" y="{label_y}" fill="{MUTED_COLOR}" '
            f'font-family="Segoe UI, Ubuntu, Sans-Serif" font-size="12" '
            f'text-anchor="middle">{label}</text>'
        )

    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img">
  <title>GitHub Activity · {year}</title>
  <rect width="{width}" height="{height}" rx="8" fill="{BG}" />
  <text x="{padding}" y="{title_y}" fill="{TITLE_COLOR}" font-family="Segoe UI, Ubuntu, Sans-Serif" font-size="18" font-weight="600">GitHub Activity · {year}</text>
  <text x="{padding}" y="{subtitle_y}" fill="{MUTED_COLOR}" font-family="Segoe UI, Ubuntu, Sans-Serif" font-size="12">Year to date</text>
  {''.join(cells)}
</svg>
"""


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("GITHUB_TOKEN or GH_TOKEN env var is required", file=sys.stderr)
        return 1

    year = datetime.now(timezone.utc).year
    summary = fetch_summary(token, year)
    svg = build_svg(
        contributions=summary["contributionCalendar"]["totalContributions"],
        commits=summary["totalCommitContributions"],
        pull_requests=summary["totalPullRequestContributions"],
        repositories=summary["totalRepositoriesWithContributedCommits"],
        year=year,
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
