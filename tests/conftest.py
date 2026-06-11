"""pytest fixtures."""

import pytest


# Override ``enable_event_loop_debug`` from
# ``pytest-homeassistant-custom-component``. The upstream fixture calls
# ``asyncio.get_event_loop().set_debug(True)`` during setup, which under
# Python 3.13's ``HassEventLoopPolicy`` raises
# ``RuntimeError: There is no current event loop in thread 'MainThread'``
# — the policy's ``set_event_loop(new_event_loop())`` path silently fails
# to bind the loop, so the final ``if _local._loop is None`` check
# raises. asyncio debug mode has no effect on our functional tests, so
# the override is a no-op.
@pytest.fixture
def enable_event_loop_debug():
    """Override the upstream HA plugin's debug-enabling fixture.

    The upstream implementation is broken under Python 3.13 + HA's
    HassEventLoopPolicy, and the debug flag is irrelevant to the
    assertions these tests make.
    """
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
