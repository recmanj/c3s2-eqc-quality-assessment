import argparse
import re
import sys
from collections.abc import Iterator
from pathlib import Path

import nbformat

# The space before {figure} and colon fences are both used in notebooks
FIGURE_OPENING = r" {0,3}(`{3,}|:{3,})\s*\{figure\}\s*(.*)"


def iter_figures(source: str) -> Iterator[tuple[str, set[str], str]]:
    """Yield the target, option names and caption of each {figure} in a cell."""
    lines = source.splitlines()
    index = 0
    while index < len(lines):
        match = re.match(FIGURE_OPENING, lines[index])
        index += 1
        if not match:
            continue
        fence, target = match.groups()

        body = []
        while index < len(lines):
            line = lines[index].strip()
            index += 1
            if line and set(line) == {fence[0]} and len(line) >= len(fence):
                break
            body.append(line)

        options = set()
        if body and body[0] == "---":
            end = body.index("---", 1) if "---" in body[1:] else len(body)
            options = {line.partition(":")[0].strip() for line in body[1:end]}
            body = body[end + 1 :]
        else:
            while body and (option := re.match(r":([\w-]+):", body[0])):
                options.add(option.group(1))
                body = body[1:]

        yield target.strip(), options, "\n".join(body).strip()


def validate_figures(path: Path) -> list[str]:
    notebook = nbformat.read(path, nbformat.NO_CONVERT)
    errors = []
    for number, cell in enumerate(notebook.cells, start=1):
        if cell["cell_type"] != "markdown":
            continue
        for target, options, caption in iter_figures(cell.get("source", "")):
            figure = f"{path=!s}: Figure {target} (cell {number})"
            if not caption:
                errors.append(
                    f"{figure} has no caption: write it inside the figure block "
                    "after the options, or use ![](attachment:…) if the image "
                    "already contains its caption"
                )
            if {"height", "width"} <= options:
                errors.append(
                    f"{figure} sets both height and width, which can distort it; "
                    "keep one"
                )
    return errors


def main(paths: list[Path]) -> int:
    errors = [error for path in paths for error in validate_figures(path)]
    if errors:
        print("\n".join(errors), file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", action="store", type=Path, nargs="*")
    args = parser.parse_args()
    sys.exit(main(args.paths))
