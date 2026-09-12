from datetime import date, datetime

from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from sqlalchemy import or_

from .auth import current_user
from .digest import send_digest_for_user
from .models import Task, db

tasks_bp = Blueprint("tasks", __name__)


@tasks_bp.before_app_request
def load_logged_in_user():
    g.user = current_user()


@tasks_bp.route("/")
def index():
    if not g.user:
        return render_template("login.html")

    today = date.today()
    open_tasks = (
        g.user.tasks.filter(
            Task.done.is_(False),
            or_(Task.remind_after.is_(None), Task.remind_after <= today),
        )
        .order_by(Task.created_at.asc())
        .all()
    )
    snoozed_tasks = (
        g.user.tasks.filter(Task.done.is_(False), Task.remind_after > today)
        .order_by(Task.remind_after.asc())
        .all()
    )
    return render_template(
        "index.html", open_tasks=open_tasks, snoozed_tasks=snoozed_tasks, today=today
    )


def _parse_task_form():
    """Read and validate title/notes/remind_after from request.form. Returns
    (title, notes, remind_after) or None if validation failed (a flash
    message has already been set)."""
    title = (request.form.get("title") or "").strip()
    notes = (request.form.get("notes") or "").strip() or None
    remind_after_raw = (request.form.get("remind_after") or "").strip()

    if not title:
        flash("Title is required.", "error")
        return None

    remind_after = None
    if remind_after_raw:
        try:
            remind_after = datetime.strptime(remind_after_raw, "%Y-%m-%d").date()
        except ValueError:
            flash("Remind-after date must be a valid date.", "error")
            return None

    return title, notes, remind_after


@tasks_bp.route("/tasks", methods=["POST"])
def create_task():
    if not g.user:
        return redirect(url_for("tasks.index"))

    parsed = _parse_task_form()
    if parsed is None:
        return redirect(url_for("tasks.index"))
    title, notes, remind_after = parsed

    task = Task(user_id=g.user.id, title=title, notes=notes, remind_after=remind_after)
    db.session.add(task)
    db.session.commit()
    flash("Reminder added.", "success")
    return redirect(url_for("tasks.index"))


@tasks_bp.route("/tasks/<int:task_id>/edit", methods=["GET"])
def edit_task(task_id):
    if not g.user:
        return redirect(url_for("tasks.index"))

    task = g.user.tasks.filter_by(id=task_id).first_or_404()
    return render_template("edit.html", task=task)


@tasks_bp.route("/tasks/<int:task_id>/edit", methods=["POST"])
def update_task(task_id):
    if not g.user:
        return redirect(url_for("tasks.index"))

    task = g.user.tasks.filter_by(id=task_id).first_or_404()

    parsed = _parse_task_form()
    if parsed is None:
        return redirect(url_for("tasks.edit_task", task_id=task.id))
    title, notes, remind_after = parsed

    task.title = title
    task.notes = notes
    task.remind_after = remind_after
    db.session.commit()
    flash("Reminder updated.", "success")
    return redirect(url_for("tasks.index"))


@tasks_bp.route("/tasks/<int:task_id>/delete", methods=["POST"])
def delete_task(task_id):
    if not g.user:
        return redirect(url_for("tasks.index"))

    task = g.user.tasks.filter_by(id=task_id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    flash("Reminder deleted.", "success")
    return redirect(request.referrer or url_for("tasks.index"))


@tasks_bp.route("/tasks/<int:task_id>/toggle-done", methods=["POST"])
def toggle_done(task_id):
    if not g.user:
        return redirect(url_for("tasks.index"))

    task = g.user.tasks.filter_by(id=task_id).first_or_404()
    task.done = not task.done
    task.done_at = datetime.utcnow() if task.done else None
    db.session.commit()
    return redirect(request.referrer or url_for("tasks.index"))


@tasks_bp.route("/search")
def search():
    if not g.user:
        return redirect(url_for("tasks.index"))

    q = (request.args.get("q") or "").strip()
    status = request.args.get("status", "all")

    query = g.user.tasks
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Task.title.ilike(like), Task.notes.ilike(like)))
    if status == "open":
        query = query.filter(Task.done.is_(False))
    elif status == "done":
        query = query.filter(Task.done.is_(True))

    results = query.order_by(Task.created_at.desc()).all()
    return render_template("search.html", results=results, q=q, status=status)


@tasks_bp.route("/digest/send-now", methods=["POST"])
def send_now():
    if not g.user:
        return redirect(url_for("tasks.index"))

    sent = send_digest_for_user(g.user, force=True)
    if sent:
        flash("Digest email sent to your inbox.", "success")
    else:
        flash(
            "Could not send the digest email. Try logging out and back in "
            "to refresh your Microsoft Graph permission.",
            "error",
        )
    return redirect(url_for("tasks.index"))
