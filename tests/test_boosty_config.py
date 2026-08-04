from dollartl.config import Settings


def test_boosty_defaults_target_expected_tier() -> None:
    settings = Settings()
    assert settings.boosty_blog_name == "domnekromanta"
    assert settings.boosty_tier_id == "4041120"
    assert settings.boosty_grace_days == 7


def test_boosty_is_disabled_until_credentials_are_configured() -> None:
    assert Settings().boosty_enabled is False
