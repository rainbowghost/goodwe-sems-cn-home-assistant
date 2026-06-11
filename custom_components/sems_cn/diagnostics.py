"""Diagnostics support for the GoodWe SEMS CN integration.

Home Assistant surfaces a **Download diagnostics** button on the
integration's config-entry page (Settings → Devices & services →
GoodWe SEMS CN API → ⋯ → Download diagnostics) as soon as this
module is present. The downloaded JSON file contains everything
needed to debug a "no data" / "wrong data" report: the raw plant
API factor groups, the coordinator's flattened inverter dict, the
cached token (redacted), and the integration's runtime config.

See https://developers.home-assistant.io/docs/core/entity/diagnostics
for the contract.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import SemsConfigEntry

# Fields to redact from the downloaded JSON. Covers both
# ``config_entry.data`` (the user-typed ``password``) and the
# ``token`` dict returned by the SEMS+ cross-login API
# (``token`` field, login ``uid``/``timestamp``/``api``/``account``/
# ``pwd``).
TO_REDACT = {
    "password",
    "username",
    "uid",
    "token",
    "timestamp",
    "pwd",
    "account",
    "api",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SemsConfigEntry
) -> dict[str, Any]:
    """Return the integration's runtime data for the diagnostics file.

    Shape::

        {
            "entry":     {...},   # config entry data
            "coordinator": {
                "last_update_success": bool,
                "inverters": {<sn>: <flattened factor dict>},
                "raw_telecounting": {<sn>: [<factor-group>, ...]},
                "raw_telemetry":     {<sn>: [<factor-group>, ...]},
            },
        }
    """
    coordinator = entry.runtime_data.coordinator
    data = coordinator.data

    inverters = data.inverters if data else {}
    raw_telecounting = data.raw_telecounting if data else {}
    raw_telemetry = data.raw_telemetry if data else {}
    raw_all_status = data.raw_all_status if data else {}

    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "inverters": async_redact_data(inverters, TO_REDACT),
            "raw_telecounting": async_redact_data(raw_telecounting, TO_REDACT),
            "raw_telemetry": async_redact_data(raw_telemetry, TO_REDACT),
            "raw_all_status": async_redact_data(raw_all_status, TO_REDACT),
        },
    }
