#!/usr/bin/env bash
# Build the book on Read the Docs; see .readthedocs.yaml
#
# A build of a pull request is a preview: like the previews of the on-pull-request
# workflow, it only renders the notebooks and Markdown pages the pull request changes,
# with the disclaimer, and is skipped when the pull request changes none.
set -euo pipefail

base=main
# Read the Docs cancels a build, without failing it, when a command exits with this
skip=183

python -m pip install --quiet uv
PATH="$(python -c 'import sysconfig; print(sysconfig.get_path("scripts"))'):$PATH"
export UV_LOCKED=1

if [[ ${READTHEDOCS_VERSION_TYPE:-} == external ]]; then
    pr=$READTHEDOCS_VERSION
    # The clone is shallow, so get the history that leads to the merge base with
    # $base, without the contents of the files
    unshallow=()
    if [[ $(git rev-parse --is-shallow-repository) == true ]]; then
        unshallow=(--unshallow)
    fi
    git fetch --quiet --filter=blob:none "${unshallow[@]}" origin \
        "+refs/heads/$base:refs/remotes/origin/$base" \
        "+refs/pull/$pr/head:refs/remotes/origin/pr-$pr"
    changed=$(
        git diff --name-only --no-renames --diff-filter=d "origin/$base...HEAD" -- \
            '*.ipynb' '*.md' ':(top,exclude)README.md'
    )
    if [[ -z $changed ]]; then
        echo "Pull request #$pr changes no notebook or Markdown page: nothing to preview"
        exit "$skip"
    fi
    echo "Previewing:"
    echo "$changed"
    CHANGED_FILES=$changed uv run python .github/scripts/prune-notebooks.py
    # Download buttons link to the pull request's version
    SOURCE_REF=$READTHEDOCS_GIT_COMMIT_HASH make build-book PRE_BUILD_FLAGS=--disclaimer
else
    make build-book
fi

mkdir -p "$READTHEDOCS_OUTPUT/html"
cp -r _pre_build/_build/html/. "$READTHEDOCS_OUTPUT/html/"
du -sh "$READTHEDOCS_OUTPUT/html"
