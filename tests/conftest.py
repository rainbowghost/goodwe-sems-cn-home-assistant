"""pytest fixtures."""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(request):
    """Enable custom integrations defined in the test dir.

    The ``enable_custom_integrations`` fixture comes from
    ``pytest-homeassistant-custom-component``. If that plugin is unavailable
    (e.g., on Windows where ``fcntl`` is missing), the test still runs — only
    HA-integration tests will fail.
    """
    if "enable_custom_integrations" in request.fixturenames:
        yield from request.getfixturevalue("enable_custom_integrations")
        return
    yield
