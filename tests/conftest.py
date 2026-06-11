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
#
# We do NOT override ``enable_custom_integrations``: that fixture pops
# the custom-components cache so HA re-reads the test directory on
# next setup. Skipping it leaves HA without ``sems_cn`` registered and
# the sensor tests fail with "Integration not found".
@pytest.fixture
def enable_event_loop_debug():
    return None


@pytest.fixture
def verify_cleanup():
    return None


@pytest.fixture(autouse=True)
def auto_enable_custom integratings(request):
    """Stub for the upstream autouse wrapper.

    The upstream wrapper drove the upstream ``enable_custom integratings``
    fixture via ``yield from request.getfixturevalue(...)``. We let
    the upstream fixture run on its own when a test requests it
    directly (the four sensor tests do); the autouse chain is just a
    no-op here so the upstream fixture's ``asyncio.get_event_loop`` call
    (in the chain that the wrapper used to drive) is bypassed entirely.
    """
    yield
