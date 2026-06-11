"""Tests for SEMS sensor entities."""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import patch

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sems_cn.const import CONF_STATION_ID, DOMAIN

MOCK_POWER_STATION_ID = "12345678-1234-5678-9abc-123456789abc"
MOCK_OTHER_POWER_STATION_ID = "87654321-4321-8765-cba9-987654321cba"
MOCK_INVERTER_SN = "GW0000SN000TEST1"
MOCK_OTHER_INVERTER_SN = "GW0000SN000TEST2"


def _station(station_id: str = MOCK_POWER_STATION_ID) -> dict:
    return {
        "id": station_id,
        "name": f"Station {station_id[-4:]}",
        "installedPower": "10",
    }


def _devices(sn: str = MOCK_INVERTER_SN) -> list[dict]:
    return [
        {
            "deviceType": "INVERTER",
            "statusDetailList": [
                {
                    "status": 5,
                    "snList": [sn],
                    "detailMap": {
                        sn: {
                            "sn": sn,
                            "name": "Inverter 1",
                            "deviceType": "INVERTER",
                            "status": 5,
                        }
                    },
                }
            ],
        }
    ]


def _telecounting() -> list[dict]:
    return [
        {
            "code": "telecounting_real",
            "factors": [
                {"code": "pAc", "data": "6.895", "unit": "kW"},
                {"code": "ratedPower", "data": "10", "unit": "kW"},
            ],
        },
        {
            "code": "telecounting_today",
            "factors": [{"code": "proPvStatsToday", "data": "27.7", "unit": "kWh"}],
        },
        {
            "code": "telecounting_month",
            "factors": [{"code": "proPvStatsMonth", "data": "345.6", "unit": "kWh"}],
        },
        {
            "code": "telecounting_total",
            "factors": [{"code": "proPvStatsTotal", "data": "17777.2", "unit": "kWh"}],
        },
    ]


def _telemetry() -> list[dict]:
    return [
        {
            "code": "system",
            "factors": [
                {"code": "hTotal", "data": "7471", "unit": "H"},
                {"code": "Temperature", "data": "48.1", "unit": "C"},
            ],
        },
        {
            "code": "ac",
            "factors": [
                {"code": "Fac", "data": "50.01", "unit": "Hz"},
                {"code": "PHASE-A:Vac", "data": "232.1", "unit": "V"},
                {"code": "PHASE-B:Vac", "data": "231.8", "unit": "V"},
                {"code": "PHASE-C:Vac", "data": "233.0", "unit": "V"},
                {"code": "PHASE-A:Iac", "data": "12.2", "unit": "A"},
                {"code": "PHASE-B:Iac", "data": "12.0", "unit": "A"},
                {"code": "PHASE-C:Iac", "data": "12.4", "unit": "A"},
            ],
        },
        {
            "code": "pv",
            "factors": [
                {"code": "MPPT-1:Vpv", "data": "510.1", "unit": "V"},
                {"code": "MPPT-2:Vpv", "data": "511.2", "unit": "V"},
                {"code": "MPPT-1:Ipv", "data": "6.3", "unit": "A"},
                {"code": "MPPT-2:Ipv", "data": "6.4", "unit": "A"},
            ],
        },
    ]


def _information() -> list[dict]:
    return [
        {"code": "modelType", "data": "GW10K-SDT-30"},
        {"code": "safetyVersion", "data": "V1.08.08"},
    ]


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test",
        data={
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_STATION_ID: MOCK_POWER_STATION_ID,
        },
    )


def _mock_api(*, stations: list[dict] | None = None, devices_by_station=None):
    stack = ExitStack()
    stack.enter_context(
        patch(
            "custom_components.sems_cn.sems_api.SemsApi.get_stations",
            return_value=[_station()] if stations is None else stations,
        )
    )
    get_devices = stack.enter_context(
        patch("custom_components.sems_cn.sems_api.SemsApi.get_devices")
    )
    if devices_by_station is None:
        get_devices.return_value = _devices()
    else:
        get_devices.side_effect = lambda station_id: devices_by_station[station_id]
    stack.enter_context(
        patch(
            "custom_components.sems_cn.sems_api.SemsApi.get_telecounting",
            return_value=_telecounting(),
        )
    )
    stack.enter_context(
        patch(
            "custom_components.sems_cn.sems_api.SemsApi.get_telemetry",
            return_value=_telemetry(),
        )
    )
    stack.enter_context(
        patch(
            "custom_components.sems_cn.sems_api.SemsApi.get_information",
            return_value=_information(),
        )
    )
    return stack, get_devices


async def test_sensor_state_from_current_coordinator(
    hass: HomeAssistant,
    enable_custom_integrations: None,
) -> None:
    """Power and status sensors are created from SEMS+ plant API payloads."""
    del enable_custom_integrations
    entry = _entry()
    entry.add_to_hass(hass)

    stack, _ = _mock_api()
    with stack:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    power_entity_id = ent_reg.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{MOCK_INVERTER_SN}-power"
    )
    assert power_entity_id is not None

    power_state = hass.states.get(power_entity_id)
    assert power_state is not None
    assert power_state.state == "6895.0"
    assert power_state.attributes["unit_of_measurement"] == "W"
    assert power_state.attributes["statusText"] == "Running"
    assert power_state.attributes["raw_value"] == 5
    assert power_state.attributes["pac"] == "6895.0"
    assert power_state.attributes["model_type"] == "GW10K-SDT-30"
    assert power_state.attributes["safety_version"] == "V1.08.08"

    status_entity_id = ent_reg.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{MOCK_INVERTER_SN}-status"
    )
    assert status_entity_id is not None

    status_state = hass.states.get(status_entity_id)
    assert status_state is not None
    assert status_state.state == "Running"


async def test_configured_station_filters_api_calls(
    hass: HomeAssistant,
    enable_custom_integrations: None,
) -> None:
    """Only the configured station is refreshed when multiple stations exist."""
    del enable_custom_integrations
    entry = _entry()
    entry.add_to_hass(hass)

    stack, get_devices = _mock_api(
        stations=[
            _station(MOCK_POWER_STATION_ID),
            _station(MOCK_OTHER_POWER_STATION_ID),
        ],
        devices_by_station={
            MOCK_POWER_STATION_ID: _devices(MOCK_INVERTER_SN),
            MOCK_OTHER_POWER_STATION_ID: _devices(MOCK_OTHER_INVERTER_SN),
        },
    )
    with stack:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    get_devices.assert_called_once_with(MOCK_POWER_STATION_ID)

    ent_reg = er.async_get(hass)
    assert (
        ent_reg.async_get_entity_id(
            Platform.SENSOR, DOMAIN, f"{MOCK_INVERTER_SN}-power"
        )
        is not None
    )
    assert (
        ent_reg.async_get_entity_id(
            Platform.SENSOR, DOMAIN, f"{MOCK_OTHER_INVERTER_SN}-power"
        )
        is None
    )


async def test_unique_id_migration_sn_to_sn_power(
    hass: HomeAssistant,
    enable_custom_integrations: None,
) -> None:
    """The legacy power sensor unique_id `sn` migrates to `sn-power`."""
    del enable_custom_integrations
    entry = _entry()
    entry.add_to_hass(hass)

    ent_reg = er.async_get(hass)
    old_entity_id = ent_reg.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        MOCK_INVERTER_SN,
        config_entry=entry,
    ).entity_id

    stack, _ = _mock_api()
    with stack:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    migrated_entry = ent_reg.async_get(old_entity_id)
    assert migrated_entry is not None
    assert migrated_entry.unique_id == f"{MOCK_INVERTER_SN}-power"


async def test_exact_unique_ids_for_current_sensor_set(
    hass: HomeAssistant,
    enable_custom_integrations: None,
) -> None:
    """The current SEMS+ sensor set does not include removed switch/HomeKit IDs."""
    del enable_custom_integrations
    entry = _entry()
    entry.add_to_hass(hass)

    stack, _ = _mock_api()
    with stack:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    expected_unique_ids = {
        f"{MOCK_INVERTER_SN}-capacity",
        f"{MOCK_INVERTER_SN}-eday",
        f"{MOCK_INVERTER_SN}-energy",
        f"{MOCK_INVERTER_SN}-grid_ac_frequency",
        f"{MOCK_INVERTER_SN}-hour-total",
        f"{MOCK_INVERTER_SN}-iac1",
        f"{MOCK_INVERTER_SN}-iac2",
        f"{MOCK_INVERTER_SN}-iac3",
        f"{MOCK_INVERTER_SN}-ibattery1",
        f"{MOCK_INVERTER_SN}-ipv1",
        f"{MOCK_INVERTER_SN}-ipv2",
        f"{MOCK_INVERTER_SN}-power",
        f"{MOCK_INVERTER_SN}-status",
        f"{MOCK_INVERTER_SN}-temperature",
        f"{MOCK_INVERTER_SN}-thismonthetotle",
        f"{MOCK_INVERTER_SN}-vac1",
        f"{MOCK_INVERTER_SN}-vac2",
        f"{MOCK_INVERTER_SN}-vac3",
        f"{MOCK_INVERTER_SN}-vbattery1",
        f"{MOCK_INVERTER_SN}-vpv1",
        f"{MOCK_INVERTER_SN}-vpv2",
    }

    ent_reg = er.async_get(hass)
    actual_unique_ids = {
        entity.unique_id
        for entity in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    }

    assert actual_unique_ids == expected_unique_ids
