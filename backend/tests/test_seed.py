"""``flask seed`` command."""

from app.models import Category, User


def test_seed_creates_reference_data(db, app):
    runner = app.test_cli_runner()

    result = runner.invoke(args=["seed"])

    assert result.exit_code == 0
    assert "6 categories" in result.output
    assert "3 users" in result.output
    assert db.session.query(Category).count() == 6
    assert db.session.query(User).count() == 3


def test_seed_is_idempotent(db, app):
    runner = app.test_cli_runner()

    runner.invoke(args=["seed"])
    second = runner.invoke(args=["seed"])

    assert second.exit_code == 0
    assert "0 categories" in second.output
    assert "0 users" in second.output
    assert db.session.query(Category).count() == 6
    assert db.session.query(User).count() == 3


def test_seed_creates_expected_categories(db, app):
    app.test_cli_runner().invoke(args=["seed"])

    slugs = {category.slug for category in db.session.query(Category)}
    assert slugs == {"access", "hardware", "software", "network", "billing", "other"}
