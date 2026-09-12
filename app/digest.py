import logging
from datetime import date
from html import escape

from .auth import get_access_token_for_user
from .graph import GraphError, send_mail
from .models import Task, User

logger = logging.getLogger(__name__)


def open_tasks_query(user: User, today: date = None):
    """Tasks that are not done and not currently snoozed past their
    remind-after date."""
    from sqlalchemy import or_

    today = today or date.today()
    return user.tasks.filter(
        Task.done.is_(False),
        or_(Task.remind_after.is_(None), Task.remind_after <= today),
    ).order_by(Task.created_at.asc())


def build_digest_html(user: User, tasks) -> str:
    rows = []
    for t in tasks:
        notes = f"<div style='color:#555;font-size:13px;margin-top:2px'>{escape(t.notes)}</div>" if t.notes else ""
        rows.append(
            f"<li style='margin-bottom:12px'>"
            f"<strong>{escape(t.title)}</strong>{notes}"
            f"</li>"
        )
    items = "\n".join(rows) if rows else "<li>No open tasks. Nice work!</li>"
    return f"""
    <div style="font-family:Segoe UI,Arial,sans-serif;max-width:600px">
      <h2>Your open reminders</h2>
      <p>Here are your open tasks as of today:</p>
      <ul>{items}</ul>
      <p style="color:#888;font-size:12px">
        This is your automated morning digest from RemindMeApp. Mark items done
        or snooze them with a "remind after" date in the app.
      </p>
    </div>
    """


def send_digest_for_user(user: User, force: bool = False) -> bool:
    """Send the morning digest email to a single user. Returns True if an
    email was sent. If force is False and the user has no open tasks, no
    email is sent."""
    tasks = list(open_tasks_query(user))
    if not tasks and not force:
        return False

    access_token = get_access_token_for_user(user)
    if not access_token:
        logger.warning("No valid Graph token for user %s; skipping digest", user.email)
        return False

    html = build_digest_html(user, tasks)
    count = len(tasks)
    subject = f"Your reminders: {count} open task{'s' if count != 1 else ''}"
    try:
        send_mail(access_token, user.email, subject, html)
        return True
    except GraphError:
        logger.exception("Failed to send digest to %s", user.email)
        return False


def send_daily_digests(app) -> None:
    """Entry point for the scheduled job: iterate all users and send each
    one their morning digest of open tasks."""
    with app.app_context():
        for user in User.query.all():
            send_digest_for_user(user)
