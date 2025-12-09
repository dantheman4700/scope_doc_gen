#!/bin/bash
# Sync both backend and frontend code from dev to production

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================"
echo "  Syncing Backend and Frontend"
echo "========================================"
echo ""

# Auto-bump patch version
if [ -f "$SCRIPT_DIR/bump-version.sh" ]; then
    echo "Bumping version..."
    cd "$PROJECT_DIR" && "$SCRIPT_DIR/bump-version.sh" patch
    echo ""
fi

# Sync backend
"$SCRIPT_DIR/sync-backend.sh"

echo ""
echo "========================================"
echo ""

# Sync frontend
"$SCRIPT_DIR/sync-frontend.sh"

echo ""
echo "========================================"
echo "  ✅ All services synced and restarted"
echo "========================================"

