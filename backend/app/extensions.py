"""Extension instances shared across the application.

Extensions are instantiated here without an app, then initialized inside
``create_app``. Keeping them in one place avoids circular imports and gives
each future extension (database, migrations, ...) a clear home.
"""

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

# Extension instances are created here without an app, then initialized
# inside ``create_app`` via ``init_app``.
db = SQLAlchemy()
migrate = Migrate()
