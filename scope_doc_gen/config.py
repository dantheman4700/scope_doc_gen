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

