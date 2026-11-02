from jarvis_command_sdk.storage import set_backend

from ha_shared.secrets import get_secret_value


class _Backend:
    def get_secret(self, key, scope, user_id=None):
        return {"HOME_ASSISTANT_REST_URL": "http://from-backend"}.get(key)


def test_sdk_backend_before_environment(monkeypatch):
    monkeypatch.setenv("HOME_ASSISTANT_REST_URL", "http://from-env")
    monkeypatch.setenv("HOME_ASSISTANT_API_KEY", "env-key")
    set_backend(_Backend())
    try:
        assert get_secret_value("HOME_ASSISTANT_REST_URL", "integration") == "http://from-backend"
        assert get_secret_value("HOME_ASSISTANT_API_KEY", "integration") == "env-key"  # backend has none
    finally:
        set_backend(None)
    assert get_secret_value("HOME_ASSISTANT_REST_URL", "integration") == "http://from-env"
