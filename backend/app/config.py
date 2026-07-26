from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path
import os


class Settings(BaseSettings):
    # ── Core ──────────────────────────────────────────────────────────────────
    DATABASE_URL:                str = "postgresql://postgres:password@localhost:5432/greenchain"
    # SECRET_KEY intentionally has NO hardcoded production-shaped default.
    # Dev/test paths supply a value via .env / .env.test. Staging/production
    # must supply a real 32+ char value or startup will refuse. See
    # validate_startup_config() below.
    SECRET_KEY:                  str = ""
    ALGORITHM:                   str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    # Deployment environment. Recognized values:
    #   development / dev / test / testing  → relaxed validation, dev CORS fallback
    #   staging / production / prod         → strict validation, no wildcard CORS
    APP_ENV:                     str = "development"
    # Comma-separated list of allowed browser origins for CORS.
    # Empty in dev/test → defaults to "*" for local convenience.
    # Empty in staging/production → refuses to start.
    CORS_ORIGINS:                str = ""

    # ── Blockchain provider selection ─────────────────────────────────────────
    # Set to "web3" in production/testnet environments.
    # Defaults to "mock" so local dev, tests, and CI work without blockchain.
    BLOCKCHAIN_MODE: str = "mock"

    # ── Web3 / real-blockchain settings ───────────────────────────────────────
    # Required when BLOCKCHAIN_MODE=web3.
    # Never hard-code values here; always load from .env.
    WEB3_RPC_URL:          str = ""   # e.g. https://rpc-amoy.polygon.technology/
    WEB3_PRIVATE_KEY:      str = ""   # 0x-prefixed hex — NEVER log or expose
    WEB3_CONTRACT_ADDRESS: str = ""   # deployed contract address
    WEB3_CHAIN_ID:         int = 80002  # default: Polygon Amoy
    WEB3_ACCOUNT_ADDRESS:  str = ""   # derived from private key; set explicitly for clarity

    # ── Payout provider settings ──────────────────────────────────────────────
    # Present in .env for future RazorpayX integration.
    RAZORPAY_MODE:                 str = "mock"
    RAZORPAY_KEY_ID:               str = ""
    RAZORPAY_KEY_SECRET:           str = ""
    RAZORPAY_ACCOUNT_NUMBER:       str = ""   # RazorpayX source account number (from Dashboard → Account Settings)
    RAZORPAY_ENABLE_TEST_PAYOUTS:  str = "false"   # "true" to allow test execution

    # ── GIS / Satellite provider settings ────────────────────────────────────
    # Copernicus Sentinel Hub — https://shapps.dataspace.copernicus.eu/
    COPERNICUS_API_KEY:    str = ""
    COPERNICUS_API_SECRET: str = ""
    COPERNICUS_INSTANCE_ID: str = ""   # optional — some endpoints need it

    # Bhuvan ISRO — https://bhuvan-app3.nrsc.gov.in/
    BHUVAN_ACCESS_TOKEN:  str = ""

    # Bhoonidhi NRSC — https://bhoonidhi.nrsc.gov.in/
    BHOONIDHI_API_KEY:    str = ""
    BHOONIDHI_USERNAME:   str = ""
    BHOONIDHI_PASSWORD:   str = ""    # NEVER log; loaded from env only

    # ── Google OAuth / Drive — Phase 15 ──────────────────────────────────────────
    # Backend uses this to verify Google tokens via userinfo endpoint.
    # Set GOOGLE_DRIVE_ENABLED=true to allow evidence import from Google Drive.
    GOOGLE_DRIVE_ENABLED: str = "false"

    # Controls whether mock fallback is allowed when all real providers fail.
    # Set to "false" in production to surface provider errors instead of silently falling back.
    GIS_MOCK_FALLBACK_ENABLED: str = "true"

    # Timeout in seconds for GIS provider HTTP calls
    GIS_PROVIDER_TIMEOUT: int = 15

    # ── AI Layer — Phase 18 ───────────────────────────────────────────────────
    # AI_MODE=rules  →  deterministic rule engine (default, no external deps)
    # AI_MODE=groq   →  Groq cloud LLM API (falls back to rules if unavailable)
    AI_MODE:        str = "rules"
    GROQ_API_KEY:   str = ""                          # Set in .env — NEVER hardcode
    GROQ_MODEL:     str = "llama-3.3-70b-versatile"  # Groq model name

    # ── Evidence upload storage ───────────────────────────────────────────────
    # Absolute path to the directory where evidence files are written and served.
    # On Render, set to the mounted persistent-disk path, e.g. /var/data/uploads/evidence
    # If empty, falls back to <backend>/uploads/evidence for local development.
    # NEVER point this at ephemeral container storage in production.
    UPLOAD_DIR: str = ""

    model_config = {
        "env_file": os.getenv("ENV_FILE", ".env"),
        "extra": "ignore"
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


# ── Environment & startup validation (Task 2) ────────────────────────────────
# Historical known-bad SECRET_KEY defaults that MUST NOT be used in staging /
# production. Kept as a set so future re-uses of an old default are caught.
_KNOWN_UNSAFE_SECRETS = frozenset({
    "supersecretkey-change-in-production",
    "replace-with-a-random-256bit-secret-key",
    "changeme",
    "secret",
    "",
})

_DEV_LIKE = frozenset({"development", "dev", "test", "testing", ""})
_PROD_LIKE = frozenset({"staging", "production", "prod"})


def is_devlike(env: str | None) -> bool:
    return (env or "").strip().lower() in _DEV_LIKE


def is_prodlike(env: str | None) -> bool:
    return (env or "").strip().lower() in _PROD_LIKE


def get_cors_origins(s: "Settings | None" = None) -> list[str]:
    """
    Parse settings.CORS_ORIGINS into a normalized list.

    * Comma-separated
    * Whitespace trimmed
    * Empty entries dropped
    * Duplicates removed (order preserved)
    * Empty raw value in dev/test  → ["*"] convenience default
    * Empty raw value in staging/prod → [] (validate_startup_config will reject)
    """
    s = s or settings
    raw = (s.CORS_ORIGINS or "").strip()
    if not raw:
        return ["*"] if is_devlike(s.APP_ENV) else []
    seen: set[str] = set()
    out: list[str] = []
    for part in raw.split(","):
        cleaned = part.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            out.append(cleaned)
    return out


class ConfigurationError(RuntimeError):
    """Raised when the process is configured in a way that is unsafe to serve."""


def validate_startup_config(s: "Settings | None" = None) -> None:
    """
    Called at application startup (imported by main.py). Refuses to serve
    when SECRET_KEY / CORS_ORIGINS are misconfigured for the current APP_ENV.

    Never prints the secret. Error messages name the variable only.
    """
    s = s or settings
    env = (s.APP_ENV or "").strip().lower()

    if is_prodlike(env):
        key = (s.SECRET_KEY or "").strip()
        if not key:
            raise ConfigurationError(
                f"SECRET_KEY must be set for APP_ENV={env!r}. Provide a random 32+ character value."
            )
        if key in _KNOWN_UNSAFE_SECRETS:
            raise ConfigurationError(
                f"SECRET_KEY matches a known-default/unsafe value for APP_ENV={env!r}. "
                "Generate a fresh secret and set it via the deployment environment."
            )
        if len(key) < 32:
            raise ConfigurationError(
                f"SECRET_KEY too short for APP_ENV={env!r}: minimum 32 characters required."
            )
        if key.isspace():
            raise ConfigurationError(
                f"SECRET_KEY is whitespace-only for APP_ENV={env!r}."
            )

        origins = get_cors_origins(s)
        if not origins:
            raise ConfigurationError(
                f"CORS_ORIGINS must list at least one explicit origin for APP_ENV={env!r}."
            )
        if "*" in origins:
            raise ConfigurationError(
                f"CORS_ORIGINS may not contain '*' when APP_ENV={env!r}; "
                "allow_credentials is enabled and wildcard is unsafe."
            )

    # Dev/test: no hard rejection. If SECRET_KEY is missing, fall back so the
    # process can boot locally, but keep JWT deterministic across restarts.
    elif not (s.SECRET_KEY or "").strip():
        # Deterministic, obviously-unsafe local-dev fallback. Never appears in
        # any real deployment because prod-like envs would have already raised.
        s.SECRET_KEY = "dev-only-unsafe-fallback-do-not-use-outside-localhost"


# ── Evidence upload directory — SINGLE SOURCE OF TRUTH ───────────────────────
# Called by main.py (StaticFiles mount) and routers/evidence.py (write path).
# NOT cached: reading the current environment each call keeps tests that
# monkey-patch UPLOAD_DIR honest, and the mkdir is cheap.

def _default_local_evidence_dir() -> Path:
    # <backend>/uploads/evidence — matches the historical local-dev layout.
    return (Path(__file__).resolve().parent.parent / "uploads" / "evidence").resolve()


def resolve_evidence_upload_dir() -> Path:
    """
    Return the absolute Path where evidence files should live.

    Order of precedence:
      1. UPLOAD_DIR env / settings, if non-empty → use as-is.
      2. Otherwise: <backend>/uploads/evidence (local-dev backward compat).

    The directory (and any missing parents) is created on first call.
    Safe on Windows and Linux; independent of the current working directory.
    """
    raw = os.environ.get("UPLOAD_DIR", "").strip() or settings.UPLOAD_DIR.strip()
    if raw:
        p = Path(raw).expanduser().resolve()
    else:
        p = _default_local_evidence_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p
