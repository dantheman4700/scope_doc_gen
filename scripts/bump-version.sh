#!/bin/bash
# Auto-increment the patch version number in frontend/lib/version.ts
# Usage: ./scripts/bump-version.sh [major|minor|patch]
# Default: patch

set -e

VERSION_FILE="frontend/lib/version.ts"
BUMP_TYPE="${1:-patch}"

if [ ! -f "$VERSION_FILE" ]; then
    echo "Error: $VERSION_FILE not found"
    exit 1
fi

# Extract current version
CURRENT_VERSION=$(grep -oP 'APP_VERSION = "\K[0-9]+\.[0-9]+\.[0-9]+' "$VERSION_FILE")

if [ -z "$CURRENT_VERSION" ]; then
    echo "Error: Could not find version in $VERSION_FILE"
    exit 1
fi

# Parse version components
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

# Increment based on type
case "$BUMP_TYPE" in
    major)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        ;;
    minor)
        MINOR=$((MINOR + 1))
        PATCH=0
        ;;
    patch)
        PATCH=$((PATCH + 1))
        ;;
    *)
        echo "Error: Unknown bump type '$BUMP_TYPE'. Use major, minor, or patch."
        exit 1
        ;;
esac

NEW_VERSION="$MAJOR.$MINOR.$PATCH"

# Update the file
sed -i "s/APP_VERSION = \"$CURRENT_VERSION\"/APP_VERSION = \"$NEW_VERSION\"/" "$VERSION_FILE"

echo "Version bumped: $CURRENT_VERSION -> $NEW_VERSION"

