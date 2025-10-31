#!/bin/bash
# Sync backend code from dev to production directory

set -e

SOURCE_DIR="/home/dan/projects/scope_doc_gen/server/"
DEST_DIR="/opt/scope_doc_gen/server/"

echo "🔄 Syncing backend from $SOURCE_DIR to $DEST_DIR"

rsync -av --delete \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='*.pyo' \
  --exclude='.env' \
  --exclude='.env.local' \
  --exclude='*.db' \
  --exclude='*.sqlite' \
  --exclude='*.sqlite3' \
  --exclude='.pytest_cache/' \
  --exclude='*.log' \
  --exclude='.venv/' \
  --exclude='venv/' \
  --exclude='env/' \
  "$SOURCE_DIR" "$DEST_DIR"

echo "✅ Backend sync complete"
echo "🔄 Restarting backend service..."

sudo systemctl restart scope-backend

echo "✅ Backend service restarted"
echo "📋 Checking service status..."
echo ""

sudo systemctl status scope-backend --no-pager -l

echo ""
echo "📋 Recent logs:"
echo ""
journalctl -xeu scope-backend.service --no-pager -n 20

