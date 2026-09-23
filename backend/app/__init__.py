"""Flask application factory."""

import os

from dotenv import load_dotenv
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from app.config import config_by_name
from app.extensions import db, migrate
from app.spa import register_spa


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

    # Register ORM models so Alembic autogenerate and db.create_all see them.
    from app import models  # noqa: F401

    from app.api import api

    app.register_blueprint(api)
    _register_error_handlers(app)
    _register_commands(app)
    # SPA serving (Option B): registered last so /api/* rules always
    # take precedence over the catch-all fallback.
    register_spa(app)

    return app


def _register_error_handlers(app: Flask) -> None:
    """Keep every error response in the approved JSON envelope."""

    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        code = (
            error.name.upper().replace(" ", "_")
            if error.code != 404
            else "NOT_FOUND"
        )
        return (
            jsonify(error={"code": code, "message": error.description}),
            error.code,
        )


def _register_commands(app: Flask) -> None:
    """Attach Flask CLI commands (``flask seed``, ``flask embeddings``,
    ``flask classification``)."""
    from app import commands

    app.cli.add_command(commands.seed)
    app.cli.add_command(commands.embeddings)
    app.cli.add_command(commands.classification)
