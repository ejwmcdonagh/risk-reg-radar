from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # extra="ignore" so OS-level vars like SSL_CERT_FILE in .env don't cause
    # validation errors - they're consumed by the runtime, not the app config
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Supabase - or any Postgres-compatible REST endpoint that speaks the PostgREST protocol.
    # See README § "Alternative databases" if you're not using Supabase.
    supabase_url: str
    supabase_service_role_key: str

    # Optional NVD API key - increases rate limit from ~5 to 50 req/30s
    nvd_api_key: str = ""
    # Optional GitHub token - increases advisory API rate limit from 60 to 5,000 req/hour
    github_token: str = ""

    # Anthropic API key - required for signal clustering (Step 2) and card generation (Step 3)
    anthropic_api_key: str = ""

    # Voyage AI key - required for regulation chunk embeddings (RAG).
    # Free tier at voyageai.com (200M tokens, no card required).
    # If absent, card generation continues without regulatory context (graceful degradation).
    voyage_api_key: str = ""

    # How many days of signals to look back when building clusters.
    # 30 days matches the NVD ingestion window and captures enough CISA KEV
    # entries to find cross-source convergence patterns.
    clustering_window_days: int = 30
    # Cron for running the clustering job (default: daily at 08:00 UTC, after ingestion)
    clustering_cron: str = "0 8 * * *"

    # Minimum cluster score to qualify for card generation
    card_score_threshold: float = 20.0
    # Card generation runs after clustering (default: daily at 09:00 UTC)
    card_generation_cron: str = "0 9 * * *"

    # Cron expressions (UTC). Defaults match the values in .env.example.
    cisa_kev_cron: str = "0 6 * * *"
    cisa_advisories_cron: str = "0 */6 * * *"
    ncsc_cron: str = "0 */6 * * *"
    nvd_cron: str = "0 7 * * *"

    # Optional API key for protecting the API. When empty, auth is disabled.
    # Set to any secret string in production: API_KEY=your-secret-here
    api_key: str = ""

    # Set to true in production to enable the daily pipeline schedule.
    # Off by default so local dev runs stay fully manual.
    scheduler_enabled: bool = False

    # Allowed CORS origins. In production, set to your frontend domain (e.g. "https://pulse.example.com").
    # Accepts a comma-separated string via the env var: ALLOWED_ORIGINS="https://a.com,https://b.com"
    allowed_origins: list[str] = ["*"]

    log_level: str = "INFO"


settings = Settings()
