"""Flask application factory."""

import os

from dotenv import load_dotenv
from flask import Flask

from app.config import config_by_name
from app.extensions import db, migrate


def create_app(config_name: str | None = None) -> Flask:
    """Build and configure the SupportIQ Flask application.

    Args:
        config_name: Key into ``config_by_name``. Defaults to the
            ``FLASK_ENV`` environment variable, falling back to
            ``development``.
    """
    load_dotenv()

    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    config_cls = config_by_name[config_name]
    if hasattr(config_cls, "init_app"):
        config_cls.init_app(app)

    db.init_app(app)
    migrate.init_app(app, db)

    from app.api import api

    app.register_blueprint(api)

    return app
