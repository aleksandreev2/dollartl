from dollartl.config import Settings


def test_default_user_upload_limit_is_twenty_megabytes() -> None:
    settings = Settings(_env_file=None)
    assert settings.user_upload_max_bytes == 20 * 1024 * 1024
    assert "donation/818248" in settings.boosty_donate_url
