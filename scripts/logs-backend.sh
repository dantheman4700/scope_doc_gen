#!/bin/bash
# View backend logs

if [ "$1" == "-f" ] || [ "$1" == "--follow" ]; then
  echo "📋 Following backend logs (Ctrl+C to stop)..."
  journalctl -xeu scope-backend.service -f
else
  echo "📋 Recent backend logs:"
  journalctl -xeu scope-backend.service --no-pager -n 50
fi

