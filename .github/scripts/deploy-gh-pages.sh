#!/usr/bin/env bash
# Publish a directory to a path on the gh-pages branch, retrying if the branch moves.
#
# Usage: deploy-gh-pages.sh CHECKOUT TARGET MESSAGE [SOURCE]
#   CHECKOUT  local checkout of the gh-pages branch
#   TARGET    path on the branch to replace ("." for the root, which keeps pr-preview/),
#             or "-" to remove the paths listed on stdin, one per line, unless they
#             changed on the branch since CHECKOUT was checked out
#   MESSAGE   commit message
#   SOURCE    directory to publish; omit to remove TARGET
#
# Warns when the site may be too big for GitHub Pages, whose deployments then time out.
set -euo pipefail

checkout=$1
target=$2
message=$3
src=${4:+$(realpath "$4")}
attempts=5
# GitHub Pages sites are limited to 1 GB, as measured on the compressed upload
max_size=1000000000

if [[ $target == - ]]; then
    mapfile -t remove
fi

cd "$checkout"
# The paths to remove were chosen from this commit
base=$(git rev-parse HEAD)
for attempt in $(seq "$attempts"); do
    git fetch --depth 1 origin gh-pages
    git reset --hard FETCH_HEAD
    git clean -fdx

    if [[ $target == - ]]; then
        for path in "${remove[@]}"; do
            # Keep a preview deployed in the meantime
            if git diff --quiet "$base" HEAD -- "${path:?}"; then
                rm -rf -- "$path"
            else
                echo "Keeping $path, which changed since $base"
            fi
        done
    elif [[ $target == . ]]; then
        find . -mindepth 1 -maxdepth 1 ! -name .git ! -name pr-preview -exec rm -rf {} +
    else
        rm -rf "$target"
    fi
    if [[ -n $src ]]; then
        mkdir -p "$target"
        cp -r "$src/." "$target/"
    fi

    git add -A
    if git diff --cached --quiet; then
        echo "Nothing to deploy"
        exit 0
    fi
    git -c user.name="github-actions[bot]" \
        -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
        commit -q -m "$message"
    if git push origin HEAD:gh-pages; then
        # Roughly what GitHub uploads: the site without .git, compressed
        size=$(tar -c --exclude=.git . | gzip -1 | wc -c)
        echo "The site is about $((size / 1000000)) MB compressed"
        if ((size > max_size)); then
            echo "::warning title=GitHub Pages size::The site is about $((size / 1000000)) MB compressed, over the 1 GB limit of GitHub Pages, so its deployments may time out. Previews of pull requests take most of the space."
        fi
        exit 0
    fi
    if ((attempt < attempts)); then
        sleep $((attempt * 10))
    fi
done

echo "Failed to push to gh-pages" >&2
exit 1
