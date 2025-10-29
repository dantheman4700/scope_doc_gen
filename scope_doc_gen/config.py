"""Configuration management for scope document generator."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
TEMPLATE_PATH = PROJECT_ROOT / "template_scope.md"
VARIABLES_SCHEMA_PATH = PROJECT_ROOT / "temp_var_schema.json"
VARIABLES_GUIDE_PATH = PROJECT_ROOT / "variables.json"
INPUT_DOCS_DIR = PROJECT_ROOT / "input_docs"
OUTPUT_DIR = PROJECT_ROOT / "generated_scopes"

# Historical scope retrieval (optional)
def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


HISTORY_ENABLED = _env_flag("HISTORY_ENABLED")
HISTORY_DB_URL = os.getenv("HISTORY_DB_URL")
HISTORY_EMBEDDING_MODEL = os.getenv("HISTORY_EMBEDDING_MODEL", "text-embedding-3-small")
HISTORY_TOPN = int(os.getenv("HISTORY_TOPN", "12"))

# Web research configuration
ENABLE_WEB_RESEARCH = _env_flag("ENABLE_WEB_RESEARCH", "true")
WEB_SEARCH_MAX_USES = int(os.getenv("WEB_SEARCH_MAX_USES", "3"))
_allowed_domains = os.getenv("WEB_SEARCH_ALLOWED_DOMAINS")
WEB_SEARCH_ALLOWED_DOMAINS = [d.strip() for d in _allowed_domains.split(",") if d.strip()] if _allowed_domains else None

# API Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = "claude-sonnet-4-5"  # Sonnet 4.5 per user preference

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

# Ensure directories exist
INPUT_DOCS_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

