"""Extension instances shared across the application.

Extensions are instantiated here without an app, then initialized inside
``create_app``. Keeping them in one place avoids circular imports and gives
each future extension (database, migrations, ...) a clear home.
"""

# No extensions yet. PostgreSQL and SQLAlchemy arrive in a later phase.
