import os


class Settings:
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://admin:local-dev-postgres-password@shared-db:5432/rafflesdb",
    )
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "local-dev-jwt-secret-change-me-32-chars")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    INTERNAL_SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN", "local-dev-internal-token")
    AGENDA_SERVICE_URL = os.getenv("AGENDA_SERVICE_URL", "http://agenda-service:8000")
    USERS_SERVICE_URL = os.getenv("USERS_SERVICE_URL", "http://users-service:8000")
    AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")
    UPSTREAM_TIMEOUT_SECONDS = float(os.getenv("UPSTREAM_TIMEOUT_SECONDS", "8"))
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "shared-rabbitmq")
    RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
    RABBITMQ_USER = os.getenv("RABBITMQ_USER", "user")
    RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "local-dev-rabbitmq-password")
    RABBITMQ_EXCHANGE = os.getenv("RABBITMQ_EXCHANGE", "coniiti_events")
    PREMIO_ADJUDICADO_ENABLED = os.getenv("PREMIO_ADJUDICADO_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


settings = Settings()
