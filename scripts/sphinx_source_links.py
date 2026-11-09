"""Sphinx extension: point the download button at the page's source on GitHub.

The book doesn't publish copies of its sources (html_copy_source is off) to stay
within the size limit of GitHub Pages, so the button that would download them from
_sources/ links to the file in the repository instead. The link uses the commit in
SOURCE_REF when set, as for the previews of pull requests, and otherwise the branch
of the book's repository configuration.
"""

import os
from typing import Any
from urllib.parse import quote


def link_sources(
    app: Any, pagename: str, templatename: str, context: dict[str, Any], doctree: Any
) -> None:
    options = app.config.html_theme_options
    ref = os.environ.get("SOURCE_REF") or options.get("repository_branch", "main")
    path = quote(app.env.doc2path(pagename, False))
    url = f"{options['repository_url']}/blob/{ref}/{path}"
    for group in context.get("header_buttons", []):
        if group.get("label") != "download-buttons":
            continue
        for button in group["buttons"]:
            if button.get("label") == "download-source-button":
                button["url"] = url
        # A notebook generated from a text file only exists in _sources
        group["buttons"] = [
            button
            for button in group["buttons"]
            if button.get("label") != "download-notebook-button"
        ]


def setup(app: Any) -> dict[str, Any]:
    # After sphinx-book-theme adds its buttons, at priority 501
    app.connect("html-page-context", link_sources, priority=600)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
