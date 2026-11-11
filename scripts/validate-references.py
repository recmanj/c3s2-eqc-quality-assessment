import argparse
import collections
import re
import sys
from pathlib import Path
from typing import Any

import nbformat

REFERENCE_PATTERN = r"\[\[([^\]]+)\]\]\(([^)]+)\)"
CITATION_PATTERN = r"\[\[(\d+)\]\]\("
REFERENCES_HEADING = "## ℹ️ If you want to know more"


def validate_references(path: Path, notebook: Any) -> None:
    references = collections.defaultdict(set)
    for cell in notebook.cells:
        if cell["cell_type"] != "markdown":
            continue

        matches = re.findall(REFERENCE_PATTERN, cell.get("source", ""))
        for label, reference in matches:
            references[label].add(reference)

    wrong_references = "\n".join(
        [f"{k}: {v}" for k, v in references.items() if len(v) != 1]
    )
    assert not wrong_references, (
        f"{path=!s}: Inconsistent references\n{wrong_references}"
    )


def validate_cited_references_listed(path: Path, notebook: Any) -> None:
    source = "\n".join(
        cell.get("source", "")
        for cell in notebook.cells
        if cell["cell_type"] == "markdown"
    )
    text, _, listing = source.partition(f"\n{REFERENCES_HEADING}")
    cited = {int(label) for label in re.findall(CITATION_PATTERN, text)}
    listed = {int(label) for label in re.findall(CITATION_PATTERN, listing)}
    missing = ", ".join(f"[[{label}]]" for label in sorted(cited - listed))
    assert not missing, (
        f"{path=!s}: Cited but not listed under {REFERENCES_HEADING!r}: {missing}. "
        "Add each to the References list as '[[n]](url) Authors (year) Title'"
    )


def main(paths: list[Path], strict: bool) -> int:
    rule = validate_cited_references_listed if strict else validate_references
    errors = []
    for path in paths:
        try:
            rule(path, nbformat.read(path, nbformat.NO_CONVERT))
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
