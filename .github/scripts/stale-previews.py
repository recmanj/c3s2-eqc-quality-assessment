"""List what to remove from the previews of pull requests on the gh-pages branch.

Usage: stale-previews.py CHECKOUT OPEN_PRS_FILE

Prints the paths to remove, relative to CHECKOUT, a checkout of the gh-pages branch:
- the previews of pull requests that are closed, or whose last commit is older than
  MAX_AGE_DAYS, as previews take most of the space of the site;
- the .map and .ttf files of the theme in the other previews, which the build no
  longer publishes.
Writes the numbers of the open pull requests whose previews are removed to
OPEN_PRS_FILE, so their comments can say how to get them back.
Needs GH_TOKEN and GITHUB_REPOSITORY in the environment.
"""

import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

MAX_AGE_DAYS = 90
PREVIEW = re.compile(r"pr-(\d+)")


def gh(path: str) -> dict[str, object]:
    process = subprocess.run(
        ["gh", "api", path], check=True, capture_output=True, text=True
    )
    return json.loads(process.stdout)


def is_stale(number: str, cutoff: datetime.datetime) -> tuple[bool, bool]:
    """Return whether the preview of the pull request is stale and whether it's open."""
    repo = os.environ["GITHUB_REPOSITORY"]
    pr = gh(f"repos/{repo}/pulls/{number}")
    if pr["state"] != "open":
        print(f"PR #{number} is {pr['state']}", file=sys.stderr)
        return True, False
    head = pr["head"]
    assert isinstance(head, dict)
    commit = gh(f"repos/{repo}/commits/{head['sha']}")["commit"]
    assert isinstance(commit, dict)
    date = datetime.datetime.fromisoformat(commit["committer"]["date"])
    if date < cutoff:
        print(f"PR #{number} has no commit since {date:%Y-%m-%d}", file=sys.stderr)
        return True, True
    return False, True


def main() -> None:
    checkout, open_prs_file = Path(sys.argv[1]), Path(sys.argv[2])
    cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(MAX_AGE_DAYS)
    paths: list[Path] = []
    open_prs: list[str] = []
    previews = checkout / "pr-preview"
    for preview in sorted(previews.iterdir() if previews.exists() else []):
        match = PREVIEW.fullmatch(preview.name)
        if not preview.is_dir() or not match:
            continue
        stale, is_open = is_stale(match[1], cutoff)
        if stale:
            paths.append(preview)
            if is_open:
                open_prs.append(match[1])
        else:
            paths += sorted(
                path
                for pattern in ("*.map", "*.ttf")
                for path in (preview / "_static").rglob(pattern)
            )
    for path in paths:
        print(path.relative_to(checkout))
    open_prs_file.write_text("".join(f"{number}\n" for number in open_prs))


if __name__ == "__main__":
    main()
