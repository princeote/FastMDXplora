#!/bin/bash
# Helper for semantic version bumps



#scripts/bump_version.sh patch
#scripts/bump_version.sh minor
#scripts/bump_version.sh major


# Change to project root directory
cd "$(dirname "$0")/.."

current_version=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')

major=$(echo $current_version | cut -d. -f1)
minor=$(echo $current_version | cut -d. -f2)
patch=$(echo $current_version | cut -d. -f3)

case "${1:-}" in
    "major")
        new_version="$((major + 1)).0.0"
        echo "Bumping MAJOR version: $current_version → $new_version"
        ;;
    "minor")
        new_version="$major.$((minor + 1)).0"
        echo "Bumping MINOR version: $current_version → $new_version"
        ;;
    "patch"|"")
        new_version="$major.$minor.$((patch + 1))"
        echo "Bumping PATCH version: $current_version → $new_version"
        ;;
    *)
        echo "Usage: scripts/bump_version.sh [major|minor|patch]"
        exit 1
        ;;
esac

# Update version
sed -i.bak "s/^version = \".*\"/version = \"$new_version\"/" pyproject.toml
rm -f pyproject.toml.bak

echo "Version updated to $new_version"
