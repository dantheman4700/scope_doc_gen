#!/bin/bash
# Sync both backend and frontend code from dev to production

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "========================================"
echo "  Syncing Backend and Frontend"
echo "========================================"
echo ""

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

