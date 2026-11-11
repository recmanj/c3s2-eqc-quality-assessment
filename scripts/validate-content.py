import argparse
import re
import sys
from pathlib import Path

import nbformat

# Text and example images that only belong in templates/template.ipynb
PLACEHOLDERS = (
    "(Delete this cell)",
    "Unique quality assessment title",
    "Use case listed here in full",
    "In most cases there should be one question listed here in bold",
    "In some cases a second related/follow-up question may be included",
    "(no title/heading)",
    "Here is my figure caption",
    "Production date: DD-MM-YYYY",
    "Describe what is done in this step/section",
    "List some key resources related to this assessment",
    "List the references used in the Notebook here",
    "76012e1e-eb2e-4973-9856-ea2d755dd01e",
    "50418e7c-3008-466c-b26e-c9033a28668d",
    "4b6a6f92-2865-4454-a23d-7e1d4a7d3a4d",
    "4cf358c8-5758-431e-bf74-dc6fdcc4e88f",
)
PLACEHOLDER_PATTERNS = (
    r"Section \d+ title",
    r"^\s*[*-]\s+Finding \d+\s*$",
)


def validate_content(path: Path) -> list[str]:
    notebook = nbformat.read(path, nbformat.NO_CONVERT)
    errors = []
    placeholders: list[str] = []
    for number, cell in enumerate(notebook.cells, start=1):
        if cell["cell_type"] == "markdown":
            text = "\n".join([cell.get("source", ""), *cell.get("attachments", {})])
            placeholders.extend(item for item in PLACEHOLDERS if item in text)
            placeholders.extend(
                match.group().strip()
                for pattern in PLACEHOLDER_PATTERNS
                for match in re.finditer(pattern, text, re.MULTILINE)
            )
        elif cell["cell_type"] == "code":
            for output in cell.get("outputs", []):
                if output.get("output_type") == "error":
                    ename = output.get("ename", "")
                    evalue = output.get("evalue", "")[:80]
                    errors.append(
                        f"{path=!s}: Code cell {number} was saved with an error "
                        f"({ename}: {evalue}). Fix it and re-run the notebook, "
                        "or clear that cell's output"
                    )
    errors.extend(
        f"{path=!s}: Template placeholder text left in: {text!r}. "
        "Replace it with your own content or delete it"
        for text in dict.fromkeys(placeholders)
    )
    return errors


def main(paths: list[Path]) -> int:
    errors = [error for path in paths for error in validate_content(path)]
    if errors:
        print("\n".join(errors), file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", action="store", type=Path, nargs="*")
    args = parser.parse_args()
    sys.exit(main(args.paths))
