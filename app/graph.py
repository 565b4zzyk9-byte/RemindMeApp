import requests
from flask import current_app


class GraphError(Exception):
    pass


def send_mail(access_token: str, to_email: str, subject: str, html_body: str) -> None:
    """Send an email via Microsoft Graph as the currently authenticated user
    (POST /me/sendMail), using a delegated access token."""
    url = f"{current_app.config['GRAPH_BASE_URL']}/me/sendMail"
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": html_body},
            "toRecipients": [{"emailAddress": {"address": to_email}}],
        },
        "saveToSentItems": "false",
    }
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    if resp.status_code >= 300:
        raise GraphError(f"Graph sendMail failed ({resp.status_code}): {resp.text}")
