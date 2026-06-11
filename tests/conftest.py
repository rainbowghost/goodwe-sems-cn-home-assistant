"""pytest fixtures."""

import asyncio

import pytest


@pytest.fixture(autouse=True)
def _ensure_event_loop(request):
    """Ensure an asyncio event loop exists before upstream HA fixtures run.

    ``pytest-homeassistant-custom-component``'s ``enable_event_loop_debug``
    fixture calls ``asyncio.get_event_loop().set_debug(True)`` during
    setup. With Python 3.13's Home Assistant ``HassEventLoopPolicy`` and
    the asyncio 3.13 deprecation behaviour, ``get_event_loop()`` raises
    ``RuntimeError: There is no current event loop in thread 'MainThread'``
    when no loop has been set yet, even on the main thread.

    Creating a fresh loop and binding it via ``set_event_loop`` here means
    the upstream fixture sees a current loop and doesn't trip the error.
    We don't try to *use* the loop — pytest-asyncio's ``auto`` mode
    handles the test-scoped loop itself.
    """
    try:
        prior = asyncio.get_event_loop_policy().get_event_loop()
    except RuntimeError:
        prior = None
    if prior is None or prior.is_closed():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        except Exception:
            pass
    yield
    # Don't close the loop on teardown — pytest-asyncio's auto mode and
    # any subsequent test need to set up its own loop. Just leave the
    # policy/loop state in place; the next test will rebind or replace
    # it as needed.


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
