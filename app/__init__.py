import os

from flask import Flask

from .config import Config
from .models import db


def create_app(config_class: type = Config) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)

    from .addin import addin_bp
    from .auth import auth_bp
    from .tasks import tasks_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(addin_bp)

    @app.context_processor
    def inject_user():
        from flask import g

        return {"current_user": getattr(g, "user", None)}

    with app.app_context():
        db.create_all()

    # Under Flask's debug reloader, the parent process re-execs a child with
    # WERKZEUG_RUN_MAIN=true to actually serve requests; only start the
    # scheduler there so it doesn't run twice.
    running_under_reloader = app.debug or os.environ.get("FLASK_DEBUG") == "1"
    is_reloader_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    if app.config.get("ENABLE_SCHEDULER") and (not running_under_reloader or is_reloader_child):
        from .scheduler import init_scheduler

        init_scheduler(app)

    return app
