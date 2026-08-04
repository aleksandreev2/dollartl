from uuid import UUID


def test_suggestion_callbacks_fit_telegram_limit() -> None:
    value = UUID("12345678-1234-5678-1234-567812345678")
    callbacks = [
        f"sug:submit:{value}",
        f"sug:view:{value}",
        "sug:rules:accept",
        "sug:pub:completed",
    ]
    assert all(len(item.encode()) <= 64 for item in callbacks)
