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

# Load nvm and build
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

cd "$DEST_DIR"
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

