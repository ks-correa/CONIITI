import os


class Settings:
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@notifications-db:5432/notificationsdb",
    )
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "shared-rabbitmq")
    RABBITMQ_USER = os.getenv("RABBITMQ_USER", "user")
    RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "local-dev-rabbitmq-password")
    RABBITMQ_EXCHANGE = os.getenv("RABBITMQ_EXCHANGE", "coniiti_events")
    RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "notifications_queue_v2")
    RABBITMQ_BINDING_KEY = os.getenv("RABBITMQ_BINDING_KEY", "#")
    RABBITMQ_DLX = os.getenv("RABBITMQ_DLX", "coniiti_events_dlx")
    RABBITMQ_DLQ = os.getenv("RABBITMQ_DLQ", "notifications_dead_letter")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "local-dev-jwt-secret-change-me-32-chars")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    INTERNAL_SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN", "local-dev-internal-token")
    AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")


settings = Settings()
