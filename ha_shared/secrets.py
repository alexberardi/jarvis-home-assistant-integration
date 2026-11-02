"""Secret lookup for every host: the Python node's secret service, else the SDK storage backend
(the Go node's sidecar provides one), else the environment (tests, local runs)."""

import os


def get_secret_value(key: str, scope: str = "") -> str | None:
    try:
        from services.secret_service import get_secret_value as node_secret
    except ImportError:
        node_secret = None
    if node_secret is not None:
        return node_secret(key, scope)
    try:
        from jarvis_command_sdk.storage import get_backend

        backend = get_backend()
        value = backend.get_secret(key, scope) if backend else None
    except Exception:
        value = None
    return value or os.environ.get(key)
