"""Configuration management for scope document generator."""

import os
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project paths (two levels up from server/core/ -> repository root)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve_path(env_name: str, default: Path) -> Path:
    value = os.getenv(env_name)
    if value:
        return Path(value).expanduser().resolve()
    return default.resolve()


def _ensure_dirs(paths: Iterable[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def _env_list(name: str) -> List[str]:
    raw = os.getenv(name)
    if not raw:
        return []
    values = []
    for item in raw.split(","):
        cleaned = item.strip()
        if cleaned:
            values.append(cleaned)
    # Preserve order while removing duplicates
    seen = set()
    unique: List[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


# Keep resources with the backend to ensure deployment scripts sync them
RESOURCES_DIR = Path(__file__).resolve().parents[1] / "resources"

# Allow environment overrides while defaulting to backend-local resources
TEMPLATE_PATH = _resolve_path("TEMPLATE_PATH", RESOURCES_DIR / "template_scope.md")
VARIABLES_SCHEMA_PATH = _resolve_path("VARIABLES_SCHEMA_PATH", RESOURCES_DIR / "temp_var_schema.json")
VARIABLES_GUIDE_PATH = _resolve_path("VARIABLES_GUIDE_PATH", RESOURCES_DIR / "variables.json")

# Provider selection helpers
def _env_choice(name: str, default: str, allowed: Tuple[str, ...]) -> str:
    value = os.getenv(name, default)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized not in allowed:
        return default
    return normalized


AUTH_PROVIDER = _env_choice("AUTH_PROVIDER", "local", ("local", "supabase"))
STORAGE_PROVIDER = _env_choice("STORAGE_PROVIDER", "local", ("local", "supabase"))


# Shared data root for all project-specific files (uploads, caches, outputs) when using local storage
DATA_ROOT = _resolve_path("SCOPE_DATA_ROOT", PROJECT_ROOT / "data")
PROJECTS_DATA_DIR = DATA_ROOT / "projects"

# Legacy fallbacks for non-project runs (kept for compatibility but lives under DATA_ROOT)
INPUT_DOCS_DIR = DATA_ROOT / "legacy_input"
OUTPUT_DIR = DATA_ROOT / "legacy_outputs"

# Historical scope retrieval (optional) - now uses main database
def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


HISTORY_ENABLED = _env_flag("HISTORY_ENABLED")
HISTORY_EMBEDDING_MODEL = os.getenv("HISTORY_EMBEDDING_MODEL", "text-embedding-3-small")
HISTORY_TOPN = int(os.getenv("HISTORY_TOPN", "12"))

# Web research configuration
ENABLE_WEB_RESEARCH = _env_flag("ENABLE_WEB_RESEARCH", "true")
WEB_SEARCH_MAX_USES = int(os.getenv("WEB_SEARCH_MAX_USES", "3"))
_allowed_domains = os.getenv("WEB_SEARCH_ALLOWED_DOMAINS")
WEB_SEARCH_ALLOWED_DOMAINS = [d.strip() for d in _allowed_domains.split(",") if d.strip()] if _allowed_domains else None

# Perplexity research configuration
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY") or os.getenv("PERP_API_KEY")
# Default to a current, supported Perplexity model
# Ref: https://docs.perplexity.ai/getting-started/models/models/sonar-pro
PERPLEXITY_MODEL = os.getenv("PERPLEXITY_MODEL", "sonar-pro")
PERPLEXITY_BASE_URL = os.getenv("PERPLEXITY_BASE_URL", "https://api.perplexity.ai")

# API Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = "claude-sonnet-4-5"  # Sonnet 4.5 per user preference
CLAUDE_CONTEXT_LIMIT = int(os.getenv("CLAUDE_CONTEXT_LIMIT", "100000"))

# Session configuration
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-me")
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "scope_session")
SESSION_COOKIE_SECURE = _env_flag("SESSION_COOKIE_SECURE")
SESSION_COOKIE_MAX_AGE = int(os.getenv("SESSION_COOKIE_MAX_AGE", str(60 * 60 * 24 * 30)))

# Supabase configuration (optional; used when providers set to supabase)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_JWT_AUDIENCE = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "scope-docs")

# Artifact delivery configuration
ARTIFACT_URL_EXPIRY_SECONDS = int(os.getenv("ARTIFACT_URL_EXPIRY_SECONDS", "3600"))


_default_cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:35476",
    "http://127.0.0.1:35476",
]
CORS_ALLOW_ORIGINS = _env_list("CORS_ALLOW_ORIGINS") or _default_cors_origins
CORS_ALLOW_CREDENTIALS = _env_flag("CORS_ALLOW_CREDENTIALS", "true")


def _normalise_database_dsn(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None

    cleaned = raw.replace("postgres://", "postgresql://", 1)

    needs_ssl = (
        STORAGE_PROVIDER == "supabase"
        or AUTH_PROVIDER == "supabase"
        or (SUPABASE_URL and "supabase" in SUPABASE_URL)
        or ("supabase" in cleaned)
    )
    if needs_ssl and "sslmode" not in cleaned:
        separator = "&" if "?" in cleaned else "?"
        cleaned = f"{cleaned}{separator}sslmode=require"

    return cleaned


def _sqlalchemy_driver_dsn(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    if raw.startswith("postgresql+psycopg"):
        return raw
    if raw.startswith("postgresql+psycopg2"):
        return raw.replace("+psycopg2", "+psycopg", 1)
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw


def _psycopg_dsn(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    if "+psycopg" in raw:
        return raw.replace("+psycopg", "")
    return raw


# Database configuration (Postgres + pgvector for the web backend)
_DATABASE_DSN = _normalise_database_dsn(
    os.getenv("DATABASE_DSN") or os.getenv("APP_DATABASE_DSN") or os.getenv("POSTGRES_DSN")
)
DATABASE_DSN = _sqlalchemy_driver_dsn(_DATABASE_DSN)
VECTOR_STORE_DSN = _psycopg_dsn(_DATABASE_DSN)

# Processing settings
MAX_TOKENS = 8000
TEMPERATURE = 0.3  # Lower temperature for more consistent output

# Tier-based rate limit guidance (conservative; see docs)
# Ref: https://docs.claude.com/en/api/rate-limits
# Tier 2 typical: Sonnet 4.x ~30k ITPM, 8k OTPM, 50 RPM
RATE_LIMIT_RPM = 50
RATE_LIMIT_ITPM = 30000
RATE_LIMIT_OTPM = 8000
CHARS_PER_TOKEN_EST = 4  # heuristic

# Filtering settings
DEFAULT_PROJECT_IDENTIFIER_HINT = (
    "Provide a short descriptor to isolate one project, e.g., 'Client: X; Project: Y'."
)

def ensure_storage_dirs() -> None:
    """Ensure all required on-disk directories are present when using local storage."""

    if STORAGE_PROVIDER != "local":
        return

    _ensure_dirs(
        (
            DATA_ROOT,
            PROJECTS_DATA_DIR,
            INPUT_DOCS_DIR,
            OUTPUT_DIR,
        )
    )


def _validate_project_id(project_id: str) -> str:
    pid = project_id.strip()
    if not pid:
        raise ValueError("project_id cannot be empty")
    if any(sep in pid for sep in ("/", "\\")):
        raise ValueError("project_id must not contain path separators")
    if pid in {".", ".."}:
        raise ValueError("project_id cannot be '.' or '..'")
    return pid


def get_project_data_dir(project_id: str) -> Path:
    """Return the base directory for a project, creating it if necessary."""

    ensure_storage_dirs()
    pid = _validate_project_id(project_id)
    project_dir = PROJECTS_DATA_DIR / pid
    _ensure_dirs((project_dir,))
    return project_dir


# Ensure baseline directories on import (legacy CLI relies on this side-effect)
ensure_storage_dirs()

