from datetime import datetime
from urllib.parse import urlparse

import jwt
from flask import Blueprint, Response, current_app, jsonify, render_template, request
from jwt import PyJWKClient

from .models import Task, User, db

addin_bp = Blueprint("addin", __name__, url_prefix="/addin")

_jwks_clients = {}


def _jwks_client_for_tenant() -> PyJWKClient:
    tenant = current_app.config["TENANT_ID"]
    if tenant not in _jwks_clients:
        _jwks_clients[tenant] = PyJWKClient(
            f"https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys"
        )
    return _jwks_clients[tenant]


def _validate_sso_token(token: str) -> dict:
    """Validate an Office SSO access token (Office.js `getAccessToken`)
    presented by the task pane: correct signature, not expired, and issued
    for our add-in's Application ID URI. Returns the token's claims."""
    signing_key = _jwks_client_for_tenant().get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=current_app.config["ADDIN_APP_ID_URI"],
    )
    return claims


def _get_or_create_user(claims: dict) -> User:
    oid = claims.get("oid")
    email = (claims.get("preferred_username") or claims.get("upn") or "").lower()
    if not oid or not email:
        raise ValueError("token missing oid/preferred_username claims")

    user = User.query.filter_by(oid=oid).first()
    if not user:
        user = User(oid=oid, email=email, display_name=claims.get("name"))
        db.session.add(user)
        db.session.commit()
    return user


@addin_bp.route("/manifest.xml")
def manifest():
    cfg = current_app.config
    xml = render_template(
        "addin/manifest.xml",
        base_url=cfg["APP_BASE_URL"],
        client_id=cfg["CLIENT_ID"],
        addin_id=cfg["ADDIN_ID"],
        addin_app_id_uri=cfg["ADDIN_APP_ID_URI"],
    )
    return Response(xml, mimetype="application/xml")


@addin_bp.route("/install")
def install():
    cfg = current_app.config
    return render_template(
        "addin/install.html",
        manifest_url=f"{cfg['APP_BASE_URL']}/addin/manifest.xml",
        addin_app_id_uri=cfg["ADDIN_APP_ID_URI"],
        addin_host=urlparse(cfg["APP_BASE_URL"]).hostname,
    )


@addin_bp.route("/taskpane.html")
def taskpane():
    return render_template("addin/taskpane.html")


@addin_bp.route("/api/tasks", methods=["POST"])
def create_task_from_addin():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify(error="missing_token"), 401

    try:
        claims = _validate_sso_token(auth_header[len("Bearer ") :])
        user = _get_or_create_user(claims)
    except Exception:
        current_app.logger.exception("Add-in SSO token validation failed")
        return jsonify(error="invalid_token"), 401

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()[:500]
    if not title:
        return jsonify(error="title_required"), 400

    notes = (data.get("notes") or "").strip() or None
    remind_after_raw = (data.get("remind_after") or "").strip()
    remind_after = None
    if remind_after_raw:
        try:
            remind_after = datetime.strptime(remind_after_raw, "%Y-%m-%d").date()
        except ValueError:
            return jsonify(error="invalid_date"), 400

    task = Task(user_id=user.id, title=title, notes=notes, remind_after=remind_after)
    db.session.add(task)
    db.session.commit()
    return jsonify(id=task.id), 201
