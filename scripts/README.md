# Development Scripts

Helper scripts for syncing code from development to production directory and managing services.

## Quick Reference

```bash
# Sync and restart backend
./scripts/sync-backend.sh

# Sync and restart frontend
./scripts/sync-frontend.sh

# Sync and restart both
./scripts/sync-all.sh

# View backend logs (last 50 lines)
./scripts/logs-backend.sh

# View frontend logs (last 50 lines)
./scripts/logs-frontend.sh

# Follow backend logs in real-time
./scripts/logs-backend.sh -f

# Follow frontend logs in real-time
./scripts/logs-frontend.sh -f
```

## What Gets Excluded

### Backend Sync
- `__pycache__/` and `*.pyc` files
- `.env` and `.env.local` files (preserved in destination)
- Database files (`*.db`, `*.sqlite`)
- Virtual environments (`venv/`, `.venv/`, `env/`)
- Log files and pytest cache

### Frontend Sync
- `node_modules/` directory
- `.next/` build directory
- `.env*` files (preserved in destination)
- Build outputs (`out/`, `build/`, `dist/`)
- Cache and log files

## Setup

Make scripts executable (first time only):

```bash
chmod +x scripts/*.sh
```

## Notes

- Scripts use `rsync` with `--delete` to remove files in destination that don't exist in source
- Excluded files in destination are preserved (like `.env` files)
- Scripts require `sudo` privileges to restart systemd services
- All scripts show service status and recent logs after sync

