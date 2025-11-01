#!/bin/bash
# Sync frontend code from dev to production directory

set -e

SOURCE_DIR="/home/dan/projects/scope_doc_gen/frontend/"
DEST_DIR="/opt/scope_doc_gen/frontend/"

echo "🔄 Syncing frontend from $SOURCE_DIR to $DEST_DIR"

rsync -av --delete \
  --exclude='.next/' \
  --exclude='node_modules/' \
  --exclude='.env' \
  --exclude='.env.local' \
  --exclude='.env*.local' \
  --exclude='out/' \
  --exclude='build/' \
  --exclude='dist/' \
  --exclude='.cache/' \
  --exclude='*.log' \
  "$SOURCE_DIR" "$DEST_DIR"

echo "✅ Frontend sync complete"
echo "🔨 Building frontend..."
echo ""

# Load nvm and select desired Node version before building
export NVM_DIR="$HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  . "$NVM_DIR/nvm.sh"
  # Prefer the user's default (higher) Node version; fall back to latest LTS
  if ! nvm use >/dev/null 2>&1; then
    nvm use --lts >/dev/null 2>&1 || true
  fi
fi

cd "$DEST_DIR"
npm install
npm run build

if [ $? -ne 0 ]; then
  echo "❌ Frontend build failed!"
  exit 1
fi

echo ""
echo "✅ Frontend build complete"
echo "🔄 Restarting frontend service..."

sudo systemctl restart scope-frontend

echo "✅ Frontend service restarted"
echo "📋 Checking service status..."
echo ""

sudo systemctl status scope-frontend --no-pager -l

echo ""
echo "📋 Recent logs:"
echo ""
journalctl -xeu scope-frontend.service --no-pager -n 20

