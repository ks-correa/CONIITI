import os

_WEAK_SECRETS = {"change-me", "supersecreto123", "coniiti-internal-token", ""}
_ENV = os.getenv("ENVIRONMENT", "development")


class Settings:
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@users-db:5432/usersdb",
    )
    JWT_SECRET_KEY = os.getenv(
        "JWT_SECRET_KEY",
        os.getenv("SECRET_KEY", "change-me"),
    )
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")
    INTERNAL_SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN", "coniiti-internal-token")
    AUTH_INTROSPECTION_ENABLED = os.getenv("AUTH_INTROSPECTION_ENABLED", "true").lower() in {
        "1",
        "true",
        "yes",
    }


settings = Settings()

if _ENV == "production":
    if settings.JWT_SECRET_KEY in _WEAK_SECRETS:
        raise ValueError("JWT_SECRET_KEY no puede ser un valor por defecto en produccion.")
    if settings.INTERNAL_SERVICE_TOKEN in _WEAK_SECRETS:
        raise ValueError("INTERNAL_SERVICE_TOKEN no puede ser un valor por defecto en produccion.")
