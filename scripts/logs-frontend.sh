#!/bin/bash
# View frontend logs

if [ "$1" == "-f" ] || [ "$1" == "--follow" ]; then
  echo "📋 Following frontend logs (Ctrl+C to stop)..."
  journalctl -xeu scope-frontend.service -f
else
  echo "📋 Recent frontend logs:"
  journalctl -xeu scope-frontend.service --no-pager -n 50
fi

