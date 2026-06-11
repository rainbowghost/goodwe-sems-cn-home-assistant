"""pytest fixtures."""

import pytest


# Override fixtures from ``pytest-homeassistant-custom-component`` that
# call ``asyncio.get_event_loop()`` during setup/teardown. Under Python
# 3.13's ``HassEventLoopPolicy`` the policy's
# ``set_event_loop(new_event_loop())`` path silently fails to bind the
# loop, so the final ``if _local._loop is None`` check raises
# ``RuntimeError: There is no current event loop in thread 'MainThread'``.
# Both fixtures are about asyncio debug / cleanup state, not test
# correctness, so replacing them with no-ops is safe.
@pytest.fixture
def enable_event_loop_debug():
    return None


@pytest.fixture
def verify_cleanup():
    return None


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
