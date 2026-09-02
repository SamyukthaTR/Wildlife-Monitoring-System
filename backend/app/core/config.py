from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Wildlife Population Intelligence System"
    DEBUG: bool = True
    DATABASE_URL: str
    # Empty by default: integration tests derive it from DATABASE_URL (same
    # host/credentials, "_test" suffix on the database name) unless overridden.
    TEST_DATABASE_URL: str = ""
    SECRET_KEY: str = "super-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- Storage ---
    UPLOAD_DIR: str = "/app/uploads"
    MODEL_CACHE_DIR: str = "/app/model_cache"

    # --- AI / ML ---
    # Set false to run the API without loading any models (analysis endpoints
    # then report a disabled status rather than failing).
    ENABLE_ML: bool = True
    # Minimum YOLO objectness score for a box to count as a detected animal.
    DETECTION_CONF_THRESHOLD: float = 0.25
    # Below this the classifier's answer is recorded as "unknown species"
    # rather than being asserted as an identification.
    CLASSIFICATION_CONF_THRESHOLD: float = 0.25
    # Minimum AudioSet score for an acoustic label to be recorded.
    AUDIO_CONF_THRESHOLD: float = 0.20

    # --- Google OAuth2 ---
    # Empty by default: /auth/google/login returns 501 until real credentials
    # (from Google Cloud Console) are supplied via environment variables.
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"
    FRONTEND_URL: str = "http://localhost:3000"

    # --- Security ---
    # Comma-separated list of allowed CORS origins. Defaults to local dev only.
    CORS_ORIGINS: str = "http://localhost:3000"
    LOGIN_RATE_LIMIT: str = "10/minute"
    REGISTER_RATE_LIMIT: str = "5/minute"

    # --- Logging ---
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
