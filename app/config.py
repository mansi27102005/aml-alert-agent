"""Configuration and budget settings for AML Alert Investigator (Role A).
Loads environment variables, manages API credentials, and defines execution guardrails.
"""

import os
from pathlib import Path
from typing import Optional
try:
    from dotenv import load_dotenv
    _has_dotenv = True
except ImportError:
    _has_dotenv = False

# Load .env file from project root if present
root_dir = Path(__file__).resolve().parent.parent
dotenv_path = root_dir / ".env"
if _has_dotenv and dotenv_path.exists():
    load_dotenv(dotenv_path)


class Settings:
    """Central configuration for agent runtime and budget boundaries."""
    # LLM Settings
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "mock").lower()
    LLM_API_KEY: Optional[str] = os.getenv("LLM_API_KEY")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-1.5-flash")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))

    # Execution & Cost Guardrails (Role A Trust Core)
    MAX_STEPS: int = int(os.getenv("MAX_STEPS", "15"))
    MAX_COST_USD: float = float(os.getenv("MAX_COST_USD", "0.50"))
    MAX_REDRAFTS: int = int(os.getenv("MAX_REDRAFTS", "1"))
    TOOL_TIMEOUT_SECONDS: int = int(os.getenv("TOOL_TIMEOUT_SECONDS", "10"))

    # Storage Paths
    DATA_DIR: Path = root_dir / "data"
    POLICIES_DIR: Path = root_dir / "data" / "policies"
    REPORTS_DIR: Path = root_dir / "eval" / "reports"


settings = Settings()
