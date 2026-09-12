import uuid

import msal
from flask import Blueprint, current_app, redirect, request, session, url_for

from .models import User, db

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _msal_app(token_cache: msal.SerializableTokenCache = None) -> msal.ConfidentialClientApplication:
    cfg = current_app.config
    return msal.ConfidentialClientApplication(
        cfg["CLIENT_ID"],
        authority=cfg["AUTHORITY"],
        client_credential=cfg["CLIENT_SECRET"],
        token_cache=token_cache,
    )


def _redirect_uri() -> str:
    cfg = current_app.config
    return cfg["APP_BASE_URL"] + cfg["REDIRECT_PATH"]


def current_user() -> User:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


def load_token_cache(user: User) -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    if user and user.token_cache:
        cache.deserialize(user.token_cache)
    return cache


def save_token_cache(user: User, cache: msal.SerializableTokenCache) -> None:
    if cache.has_state_changed:
        user.token_cache = cache.serialize()
        db.session.commit()


def get_access_token_for_user(user: User) -> str:
    """Silently acquire (refreshing if needed) a Graph access token for a
    user, using their persisted MSAL token cache. Returns None if no valid
    token/refresh token is available (e.g. user revoked consent)."""
    cache = load_token_cache(user)
    app = _msal_app(cache)
    accounts = app.get_accounts()
    if not accounts:
        return None
    result = app.acquire_token_silent(current_app.config["GRAPH_SCOPES"], account=accounts[0])
    save_token_cache(user, cache)
    if not result or "access_token" not in result:
        return None
    return result["access_token"]


@auth_bp.route("/login")
def login():
    session["flow_state"] = str(uuid.uuid4())
    app = _msal_app()
    auth_url = app.get_authorization_request_url(
        current_app.config["GRAPH_SCOPES"],
        state=session["flow_state"],
        redirect_uri=_redirect_uri(),
    )
    return redirect(auth_url)


@auth_bp.route("/callback")
def callback():
    if request.args.get("state") != session.get("flow_state"):
        return redirect(url_for("auth.login"))

    if "error" in request.args:
        return f"Login failed: {request.args.get('error_description', request.args['error'])}", 400

    code = request.args.get("code")
    if not code:
        return redirect(url_for("auth.login"))

    cache = msal.SerializableTokenCache()
    app = _msal_app(cache)
    result = app.acquire_token_by_authorization_code(
        code,
        scopes=current_app.config["GRAPH_SCOPES"],
        redirect_uri=_redirect_uri(),
    )
    if "access_token" not in result:
        return f"Login failed: {result.get('error_description', 'unknown error')}", 400

    claims = result.get("id_token_claims", {})
    oid = claims.get("oid") or claims.get("sub")
    email = claims.get("preferred_username") or claims.get("email")
    name = claims.get("name")

    if not oid or not email:
        return "Login failed: could not read account details from Microsoft.", 400

    user = User.query.filter_by(oid=oid).first()
    if not user:
        user = User(oid=oid, email=email, display_name=name)
        db.session.add(user)
    else:
        user.email = email
        user.display_name = name

    user.token_cache = cache.serialize()
    db.session.commit()

    session.clear()
    session["user_id"] = user.id
    return redirect(url_for("tasks.index"))


@auth_bp.route("/logout")
def logout():
    session.clear()
    cfg = current_app.config
    logout_url = (
        f"{cfg['AUTHORITY']}/oauth2/v2.0/logout"
        f"?post_logout_redirect_uri={cfg['APP_BASE_URL']}"
    )
    return redirect(logout_url)
