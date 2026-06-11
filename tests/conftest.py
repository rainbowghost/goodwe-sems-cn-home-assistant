"""pytest fixtures."""

import pytest


# Override fixtures from ``pytest-homeassistant-custom-component`` that
# call ``asyncio.get_event_loop()`` during setup/teardown. Under Python
# 3.13's ``HassEventLoopPolicy`` the policy's
# ``set_event_loop(new_event_loop())`` path silently fails to bind the
# loop, so the final ``if _local._loop is None`` check raises
# ``RuntimeError: There is no current event loop in thread 'MainThread'``.
# All three fixtures are about asyncio debug / cleanup state, not test
# correctness, so replacing them with no-ops is safe. Sensor tests
# request ``enable_custom_integrations`` purely for its presence (and
# then ``del`` it); they do not depend on its value.
@pytest.fixture
def enable_event_loop_debug():
    return None


@pytest.fixture
def verify_cleanup():
    return None


@pytest.fixture
def enable_custom_integrations():
    return None


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(request):
    """No-op replacement for the upstream autouse wrapper.

    The upstream wrapper called ``getfixturevalue`` to forward the
    upstream ``enable_custom_integrations`` fixture, which is now
    overridden above to a no-op. This stub stays in place so the
    autouse chain keeps a known fixture for any test that lists
    ``enable_custom_integrations`` in its ``fixturenames``.
    """
    yield
