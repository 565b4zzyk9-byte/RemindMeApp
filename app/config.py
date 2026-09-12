import os
from urllib.parse import urlparse


def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() not in ("0", "false", "no", "off", "")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    # Relative sqlite URLs (e.g. "sqlite:///app.db") are resolved by
    # Flask-SQLAlchemy relative to the app's instance folder.
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    CLIENT_ID = os.environ.get("CLIENT_ID", "")
    CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "")
    TENANT_ID = os.environ.get("TENANT_ID", "common")
    AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
    GRAPH_SCOPES = os.environ.get("GRAPH_SCOPES", "User.Read Mail.Send offline_access").split()
    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:5000").rstrip("/")
    REDIRECT_PATH = "/auth/callback"

    DIGEST_HOUR = int(os.environ.get("DIGEST_HOUR", "8"))
    DIGEST_MINUTE = int(os.environ.get("DIGEST_MINUTE", "0"))
    TIMEZONE = os.environ.get("TIMEZONE", "UTC")

    ENABLE_SCHEDULER = _env_bool("ENABLE_SCHEDULER", True)

    # Outlook add-in. ADDIN_ID identifies the add-in itself (distinct from
    # the Azure AD CLIENT_ID) and can be any stable GUID; the default below
    # is fine for internal sideloading.
    ADDIN_ID = os.environ.get("ADDIN_ID", "8f2b6b9a-8a2b-4b7e-9b8b-8b6b9a8a2b4b")
    # Office SSO identifies the add-in's backing API by this Application ID
    # URI. It must match what you set under Azure AD -> Expose an API.
    ADDIN_APP_ID_URI = os.environ.get(
        "ADDIN_APP_ID_URI",
        f"api://{urlparse(APP_BASE_URL).hostname}/{CLIENT_ID}",
    )
