from datetime import datetime, date

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    # Microsoft "oid" claim - stable unique identifier for the signed-in account
    oid = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(320), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(255))

    # Serialized msal.SerializableTokenCache, persisted so the background
    # scheduler can silently refresh an access token and send the morning
    # digest without the user being actively logged in.
    token_cache = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tasks = db.relationship(
        "Task", backref="user", lazy="dynamic", cascade="all, delete-orphan"
    )


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    title = db.Column(db.String(500), nullable=False)
    notes = db.Column(db.Text)

    # If set, the task is snoozed and won't show up as "open" or be included
    # in the morning digest email until this date has passed.
    remind_after = db.Column(db.Date, nullable=True)

    done = db.Column(db.Boolean, default=False, nullable=False, index=True)
    done_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def is_snoozed(self, today: date = None) -> bool:
        today = today or date.today()
        return bool(self.remind_after and self.remind_after > today)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "notes": self.notes,
            "remind_after": self.remind_after.isoformat() if self.remind_after else None,
            "done": self.done,
            "done_at": self.done_at.isoformat() if self.done_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
