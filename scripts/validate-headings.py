import argparse
import datetime
import re
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import nbformat

HEADINGS = (
    "## 🌍 Use case:",
    "## ❓ Quality assessment question",
    "## 📢 Quality assessment statement",
    "## 📋 Methodology",
    "## 📈 Analysis and results",
    "## ℹ️ If you want to know more",
)

ADMONITION_TITLE = "These are the key outcomes of this assessment"

DATE = r"\d{2}-\d{2}-\d{4}"
PRODUCTION_DATE = rf"Production date: ({DATE})(?: \(updated ({DATE})\))?"
BOLD_BULLET = r"(?:[*+-]|\d+[.)])\s+(?:\*\*|__)\S"

Rule = Callable[[Path, Any], None]


def validate_headers(path: Path, notebook: Any) -> None:
    title_count = 0
    admonition_count = 0
    admonition_is_note = False
    headings_count = dict.fromkeys(HEADINGS, 0)
    headings_order = []
    previous_level = 0

    anchors = set()
    references = set()
    is_analysis = False
    for cell in notebook.cells:
        if cell["cell_type"] != "markdown":
            continue

        source = cell.get("source", "")
        anchors.update(re.findall(r"\((.*?)\)=(?!`)", source))
        references.update(re.findall(r"\[\]\((.*?)\)", source))

        prev_line = ""
        for line in source.splitlines():
            line = line.strip()
            is_analysis = (
                not line == HEADINGS[-1] if is_analysis else line == HEADINGS[-2]
            )
            if is_analysis and line.startswith("### "):
                assert prev_line.endswith(")="), f"{path=!s}: Missing anchor for {line}"

            if line.startswith("# "):
                title_count += 1
            elif line == f"```{{admonition}} {ADMONITION_TITLE}":
                admonition_count += 1
            elif admonition_count and not admonition_is_note:
                admonition_is_note = line.startswith(":class: note")
                assert admonition_is_note, f"{path=!s}: The admonition is not a note"

            if line.startswith(("# ", "## ")):
                assert not line.lstrip("#").lstrip()[:1].isdigit(), (
                    f"{path=!s}: First two header levels cannot start with numbers"
                )

            if not path.name.startswith("template"):
                assert title_count, f"{path=!s}: The first line is not a title."

            if match := re.match(r"(#{1,6})\s", line):
                level = len(match.group(1))
                assert level <= previous_level + 1, (
                    f"{path=!s}: Heading {line!r} skips a level after a "
                    f"level-{previous_level} heading; "
                    f"use {'#' * (previous_level + 1)} instead"
                )
                previous_level = level

            for heading in headings_count:
                if line.startswith(heading):
                    headings_count[heading] += 1
                    headings_order.append(heading)
                    break
            else:
                assert not line.startswith("## "), f"{path=!s}: Invalid H2 {line=}"

            prev_line = line

    assert title_count == 1, f"{path=!s}: Invalid {title_count=}"
    assert admonition_count == 1, f"{path=!s}: Invalid {admonition_count=}"
    assert anchors and anchors <= references, (
        f"{path=!s}: Missing section references {anchors - references}"
    )
    for heading, header_count in headings_count.items():
        assert header_count == 1, f"{path=!s}: Invalid {header_count=} of {heading=}"
    assert headings_order == list(HEADINGS), (
        f"{path=!s}: Put the sections in this order: {', '.join(HEADINGS)}; "
        f"found: {', '.join(headings_order)}"
    )


def iter_lines(notebook: Any) -> Iterator[tuple[str, str]]:
    """Yield the cell type and each stripped line of every cell, in order."""
    for cell in notebook.cells:
        for line in cell.get("source", "").splitlines() or [""]:
            yield cell["cell_type"], line.strip()


def get_title(notebook: Any) -> str | None:
    for cell_type, line in iter_lines(notebook):
        if cell_type == "markdown" and line.startswith("# "):
            return line.removeprefix("# ").strip()
    return None


def normalise_title(title: str) -> str:
    return " ".join(title.casefold().split())


def validate_production_date(path: Path, notebook: Any) -> None:
    expected = (
        f"{path=!s}: The first line after the title must be "
        "'Production date: DD-MM-YYYY', optionally followed by "
        "' (updated DD-MM-YYYY)'"
    )
    after_title = False
    found = None
    for cell_type, line in iter_lines(notebook):
        if not after_title:
            after_title = cell_type == "markdown" and line.startswith("# ")
            continue
        assert cell_type == "markdown", f"{expected}; found a {cell_type} cell"
        if line:
            found = line
            break
    assert found is not None, f"{expected}; found nothing"

    match = re.fullmatch(PRODUCTION_DATE, found)
    assert match, f"{expected}; found {found!r}"
    try:
        produced, updated = (
            datetime.datetime.strptime(date, "%d-%m-%Y") if date else None
            for date in match.groups()
        )
    except ValueError:
        raise AssertionError(f"{expected}; {found!r} is not a real date") from None
    assert not (produced and updated) or updated >= produced, (
        f"{path=!s}: The update date is earlier than the production date: {found!r}"
    )


def validate_question(path: Path, notebook: Any) -> None:
    is_question = False
    for cell_type, line in iter_lines(notebook):
        if cell_type != "markdown":
            continue
        if line.startswith("## "):
            is_question = line.startswith(HEADINGS[1])
        elif is_question and re.match(BOLD_BULLET, line):
            return
    raise AssertionError(
        f"{path=!s}: Write the question(s) under {HEADINGS[1]!r} as bold bullet "
        "points, e.g. '* **How …?**'"
    )


def get_titles(paths: list[Path]) -> dict[str, set[Path]]:
    """Map the normalised title of every notebook in the repository to its paths."""
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.ipynb"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.split("\0")
    titles: dict[str, set[Path]] = {}
    for path in {Path(name) for name in tracked if name} | set(paths):
        if path.parts[0] == "templates" or not path.exists():
            continue
        title = get_title(nbformat.read(path, nbformat.NO_CONVERT))
        if title:
            titles.setdefault(normalise_title(title), set()).add(path)
    return titles


def make_validate_unique_title(paths: list[Path]) -> Rule:
    titles = get_titles(paths)

    def validate_unique_title(path: Path, notebook: Any) -> None:
        title = get_title(notebook)
        if title is None:
            return
        others = sorted(
            str(other)
            for other in titles.get(normalise_title(title), set())
            if not other.samefile(path)
        )
        assert not others, (
            f"{path=!s}: Title {title!r} is also used by {', '.join(others)}. "
            "Titles appear in the table of contents and the CDS quality tab, "
            "so make this one unique"
        )

    return validate_unique_title


def main(paths: list[Path], strict: bool) -> int:
    rules: list[Rule]
    if strict:
        rules = [
            validate_production_date,
            validate_question,
            make_validate_unique_title(paths),
        ]
    else:
        rules = [validate_headers]

    errors = []
    for path in paths:
        notebook = nbformat.read(path, nbformat.NO_CONVERT)
        for rule in rules:
            try:
                rule(path, notebook)
            except AssertionError as error:
                errors.append(str(error))
    if errors:
        print("\n".join(errors), file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", action="store", type=Path, nargs="*")
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Check the rules that existing notebooks do not all follow yet "
            "(manual stage), instead of the default ones."
        ),
    )
    args = parser.parse_args()
    sys.exit(main(args.paths, args.strict))
