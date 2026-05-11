"""Generate a GitHub Stats SVG card from the GraphQL API.

Renders a compact stats card (stars, commits, PRs, issues, contributed-to)
matching the visual style of the existing self-hosted top-languages card.
"""

from __future__ import annotations

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
ICON_COLOR = "#f59e0b"


def gh_graphql(query: str, variables: dict, token: str) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "kensuke-sam-stats",
        },
    )
    with urllib.request.urlopen(req) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]


STARS_QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    repositories(
      first: 100
      after: $cursor
      ownerAffiliations: OWNER
      isFork: false
    ) {
      pageInfo { hasNextPage endCursor }
      nodes { stargazerCount }
    }
  }
}
"""

SUMMARY_QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    contributionsCollection {
      totalCommitContributions
      totalRepositoriesWithContributedCommits
    }
    pullRequests(states: [OPEN, CLOSED, MERGED]) { totalCount }
    issues(states: [OPEN, CLOSED]) { totalCount }
  }
}
"""


def fetch_total_stars(token: str) -> int:
    total = 0
    cursor: str | None = None
    while True:
        data = gh_graphql(STARS_QUERY, {"login": USERNAME, "cursor": cursor}, token)
        repos = data["user"]["repositories"]
        for repo in repos["nodes"]:
            total += repo["stargazerCount"]
        if not repos["pageInfo"]["hasNextPage"]:
            return total
        cursor = repos["pageInfo"]["endCursor"]


def fetch_summary(token: str) -> dict:
    return gh_graphql(SUMMARY_QUERY, {"login": USERNAME}, token)["user"]


# Octicon-style mini SVG path data (24x24 grid, scaled).
ICONS = {
    "star": (
        "M12 .288l3.708 7.515 8.292 1.205-6 5.85 1.416 8.262L12 19.04l-7.416 "
        "3.084L6 13.858 0 8.008l8.292-1.205L12 .288z"
    ),
    "commit": (
        "M10.86 7c-.45 1.72-2.02 3-3.86 3-1.84 0-3.41-1.28-3.86-3H0V5h3.14C3.59 "
        "3.28 5.16 2 7 2c1.84 0 3.41 1.28 3.86 3H24v2H10.86zM7 8c1.66 0 3-1.34 "
        "3-3S8.66 2 7 2 4 3.34 4 5s1.34 3 3 3z"
    ),
    "pr": (
        "M6 3a3 3 0 1 1 .003 5.997A3 3 0 0 1 6 3zm0 1.5a1.5 1.5 0 1 0 0 3 1.5 "
        "1.5 0 0 0 0-3zM18 15a3 3 0 1 1 .003 5.997A3 3 0 0 1 18 15zm0 1.5a1.5 "
        "1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zM6 9.75A.75.75 0 0 1 6.75 10.5v6A.75."
        "75 0 0 1 5.25 16.5v-6A.75.75 0 0 1 6 9.75zM18 3a.75.75 0 0 1 .75.75v9"
        "a.75.75 0 0 1-1.5 0v-9A.75.75 0 0 1 18 3z"
    ),
    "issue": (
        "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 2a8 8 0 1 1 0 16 8 8 0 0 "
        "1 0-16zm1 5h-2v6h2V9zm0 7h-2v2h2v-2z"
    ),
    "people": (
        "M12 12c2.5 0 4.5-2 4.5-4.5S14.5 3 12 3 7.5 5 7.5 7.5 9.5 12 12 12zm0 "
        "2c-3.3 0-9 1.7-9 5v2h18v-2c0-3.3-5.7-5-9-5z"
    ),
}


def fmt(n: int) -> str:
    return f"{n:,}"


def build_svg(stars: int, commits: int, prs: int, issues: int, contributed: int, name: str) -> str:
    rows = [
        ("star", "Total Stars Earned", stars),
        ("commit", "Total Commits (this year)", commits),
        ("pr", "Total PRs", prs),
        ("issue", "Total Issues", issues),
        ("people", "Contributed to (last year)", contributed),
    ]

    width = 467
    title_y = 36
    first_row_y = 70
    row_h = 28
    height = first_row_y + row_h * len(rows) + 14

    body_parts = []
    for idx, (icon, label, value) in enumerate(rows):
        y = first_row_y + idx * row_h
        icon_path = ICONS[icon]
        # icons are designed on a 24x24 grid; scale to ~16 and translate.
        body_parts.append(
            f'<g transform="translate(25 {y - 13}) scale(0.7)" fill="{ICON_COLOR}">'
            f'<path d="{icon_path}" /></g>'
        )
        body_parts.append(
            f'<text x="50" y="{y}" fill="{TEXT_COLOR}" '
            f'font-family="Segoe UI, Ubuntu, Sans-Serif" font-size="13">'
            f'{label}</text>'
        )
        body_parts.append(
            f'<text x="{width - 25}" y="{y}" fill="{TEXT_COLOR}" '
            f'font-family="Segoe UI, Ubuntu, Sans-Serif" font-size="13" '
            f'text-anchor="end" font-weight="600">{fmt(value)}</text>'
        )

    title = f"{name}'s GitHub Stats" if name else f"{USERNAME}'s GitHub Stats"

    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img">
  <title>{title}</title>
  <rect width="{width}" height="{height}" rx="6" fill="{BG}" />
  <text x="25" y="{title_y}" fill="{TITLE_COLOR}" font-family="Segoe UI, Ubuntu, Sans-Serif" font-size="18" font-weight="600">{title}</text>
  {''.join(body_parts)}
</svg>
"""


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("GITHUB_TOKEN or GH_TOKEN env var is required", file=sys.stderr)
        return 1

    summary = fetch_summary(token)
    stars = fetch_total_stars(token)

    contributions = summary["contributionsCollection"]
    commits = contributions["totalCommitContributions"]
    contributed_to = contributions["totalRepositoriesWithContributedCommits"]
    prs = summary["pullRequests"]["totalCount"]
    issues = summary["issues"]["totalCount"]
    name = summary.get("name") or USERNAME

    print(
        f"name={name!r} stars={stars} commits(year)={commits} "
        f"prs={prs} issues={issues} contributed_to={contributed_to}"
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        build_svg(stars, commits, prs, issues, contributed_to, name),
        encoding="utf-8",
    )
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
