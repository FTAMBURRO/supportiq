"""CLASSIFICATION_ENABLED configuration (env_flag parsing)."""

import importlib

import pytest

import app.config as config_module


@pytest.fixture(autouse=True)
def _reload_config_after_test():
    """Reload app.config after every test here so env-driven class
    attributes never leak into the rest of the suite (test_extensions
    and create_app rely on import-time values)."""
    yield
    importlib.reload(config_module)


def _reload_with(**env: str | None):
    """Set/unset env vars (None deletes) and reload config fresh."""
    import os

    for key, value in env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    return importlib.reload(config_module)


# --- env_flag parsing -------------------------------------------------------


def test_env_flag_true_false_case_insensitive():
    for raw, expected in (
        ("true", True), ("TRUE", True), (" True ", True),
        ("false", False), ("FALSE", False),
    ):
        module = _reload_with(CLASSIFICATION_ENABLED=raw)
        assert module.env_flag("CLASSIFICATION_ENABLED", False) is expected
        assert module.DevelopmentConfig.CLASSIFICATION_ENABLED is expected


def test_env_flag_unset_uses_default():
    module = _reload_with(CLASSIFICATION_ENABLED=None)
    assert module.env_flag("CLASSIFICATION_ENABLED", True) is True


def test_env_flag_rejects_ambiguous_values():
    module = _reload_with(CLASSIFICATION_ENABLED=None)
    for raw in ("yes", "1", "0", "on", "", "maybe"):
        with pytest.raises(ValueError, match="CLASSIFICATION_ENABLED"):
            # Set the value directly to assert the parser, not the class
            # attribute evaluation (which would poison the reload).
            import os

            os.environ["CLASSIFICATION_ENABLED"] = raw
            try:
                module.env_flag("CLASSIFICATION_ENABLED", False)
            finally:
                os.environ["CLASSIFICATION_ENABLED"] = "false"


# --- per-environment defaults ----------------------------------------------


def test_development_defaults_to_false():
    module = _reload_with(CLASSIFICATION_ENABLED=None)
    assert module.DevelopmentConfig.CLASSIFICATION_ENABLED is False


def test_development_can_be_enabled_by_env():
    module = _reload_with(CLASSIFICATION_ENABLED="true")
    assert module.DevelopmentConfig.CLASSIFICATION_ENABLED is True


def test_testing_stays_false_even_if_env_says_true():
    module = _reload_with(CLASSIFICATION_ENABLED="true")
    assert module.TestingConfig.CLASSIFICATION_ENABLED is False


def test_base_and_production_default_to_true():
    module = _reload_with(CLASSIFICATION_ENABLED=None)
    assert module.Config.CLASSIFICATION_ENABLED is True
    assert module.ProductionConfig.CLASSIFICATION_ENABLED is True


# --- independence from the embedding provider -------------------------------


def test_classification_flag_never_derived_from_provider():
    """Setting EMBEDDING_PROVIDER alone must not flip the classifier."""
    module = _reload_with(
        CLASSIFICATION_ENABLED=None, EMBEDDING_PROVIDER="gemini"
    )
    assert module.Config.EMBEDDING_PROVIDER == "gemini"
    assert module.DevelopmentConfig.CLASSIFICATION_ENABLED is False

    # ...and enabling the classifier says nothing about the provider.
    module = _reload_with(
        CLASSIFICATION_ENABLED="true", EMBEDDING_PROVIDER="fake"
    )
    assert module.DevelopmentConfig.CLASSIFICATION_ENABLED is True
    assert module.DevelopmentConfig.EMBEDDING_PROVIDER == "fake"
