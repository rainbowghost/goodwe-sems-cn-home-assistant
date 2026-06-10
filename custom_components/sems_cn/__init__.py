"""The sems_cn integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .sems_api import SemsApi, SemsRateLimitedError

_LOGGER: logging.Logger = logging.getLogger(__package__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


# ---------------------------------------------------------------------------
# Public data shape (kept compatible with sensor.py / switch.py)
# ---------------------------------------------------------------------------
#
# sensors read from ``coordinator.data.inverters[sn]`` with simple key
# access (e.g. ``inverters[sn]["pac"]``, ``inverters[sn]["etotal"]``).
# The new SEMS+ plant API returns "factor groups" (arrays of
# {"code", "data", "unit", ...}), so the coordinator flattens them into
# the legacy key shape. This preserves all existing entity unique_ids.

@dataclass(slots=True)
class SemsRuntimeData:
    """Runtime data stored on the config entry."""

    api: SemsApi
    coordinator: SemsDataUpdateCoordinator


type SemsConfigEntry = ConfigEntry[SemsRuntimeData]


@dataclass(slots=True)
class SemsData:
    """Coordinator payload shape consumed by sensors / switch."""

    inverters: dict[str, dict[str, Any]]      # SN → flattened factor dict
    homekit: dict[str, Any] | None = None    # always None for SEMS+ plant API
    currency: str | None = None               # not exposed by plant API


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the sems_cn component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SemsConfigEntry) -> bool:
    """Set up sems_cn from a config entry."""
    api = SemsApi(hass, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    coordinator = SemsDataUpdateCoordinator(hass, api, entry)
    entry.runtime_data = SemsRuntimeData(api=api, coordinator=coordinator)

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SemsConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------


class SemsDataUpdateCoordinator(DataUpdateCoordinator[SemsData]):
    """Polls the SEMS+ plant API and flattens results into SemsData."""

    def __init__(
        self, hass: HomeAssistant, api: SemsApi, entry: ConfigEntry
    ) -> None:
        self.api = api
        update_interval = timedelta(
            seconds=entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> SemsData:
        """Refresh all station/inverter data and flatten to the legacy shape."""
        try:
            data = await self.hass.async_add_executor_job(self._refresh)
        except SemsRateLimitedError as err:
            raise UpdateFailed(
                f"SEMS API rate limited (retry after {err.retry_after}s)"
            ) from err
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        if not data["inverters"]:
            raise UpdateFailed(
                "SEMS API returned no inverter data — check station id or login."
            )
        return SemsData(inverters=data["inverters"], homekit=None, currency=None)

    # ----- sync refresh, run in executor ------------------------------------

    def _refresh(self) -> dict[str, Any]:
        """Pull stations, devices, telecounting, telemetry. Flatten to
        ``{sn: legacy_key_dict}`` so sensors don't need changes."""
        stations = self.api.get_stations()
        if not stations:
            return {"inverters": {}}

        inverters: dict[str, dict[str, Any]] = {}
        for station in stations:
            station_id = station.get("id")
            if not isinstance(station_id, str):
                continue
            devices = self.api.get_devices(station_id)
            if not devices:
                continue
            for entry in devices:
                if entry.get("deviceType") != "INVERTER":
                    continue
                sn_list = (
                    entry.get("statusDetailList", [{}])[0].get("snList") or []
                )
                if not sn_list:
                    continue
                sn = sn_list[0]
                detail = (
                    entry.get("detailMap", {}).get(sn) or {}
                )
                status = (detail.get("status") if isinstance(detail, dict) else None) or 0

                # Per-inverter refresh.
                telecounting = self.api.get_telecounting(sn, station_id) or []
                telemetry = self.api.get_telemetry(sn, station_id) or []

                flat = _flatten_inverter(
                    sn=sn,
                    station=station,
                    status=status,
                    telecounting_groups=telecounting,
                    telemetry_groups=telemetry,
                )
                inverters[sn] = flat

        return {"inverters": inverters}


# ---------------------------------------------------------------------------
# Flatten helpers: new plant API factor groups → legacy flat dict
# ---------------------------------------------------------------------------


def _flatten_factors(groups: list[dict]) -> dict[str, Any]:
    """Return ``{factor_code: value}`` for every factor in every group.

    Useful as a fallback for ``get_value_from_path``. Does not collapse
    duplicate codes; later groups overwrite earlier ones.
    """
    flat: dict[str, Any] = {}
    for group in groups or []:
        for factor in group.get("factors") or []:
            code = factor.get("code")
            if not code:
                continue
            flat[code] = factor.get("data")
    return flat


def _find_factor(groups: list[dict], code: str) -> Any:
    """Return ``data`` for the first factor whose ``code`` matches, else None."""
    for group in groups or []:
        for factor in group.get("factors") or []:
            if factor.get("code") == code:
                return factor.get("data")
    return None


def _flatten_inverter(
    *,
    sn: str,
    station: dict,
    status: Any,
    telecounting_groups: list[dict],
    telemetry_groups: list[dict],
) -> dict[str, Any]:
    """Build the legacy per-inverter dict shape from plant-API groups.

    Maps new factor codes → old field names that the existing sensors
    read. Everything not in this map (newly exposed data) is still
    available via the flat-factor helper at the bottom.
    """
    tc = _flatten_factors(telecounting_groups)
    tl = _flatten_factors(telemetry_groups)

    def num(value: Any) -> Any:
        """Pass-through; legacy sensors handle string→Decimal themselves."""
        return value

    flat: dict[str, Any] = {
        "sn": sn,
        "name": sn,                              # legacy used inverter name; fall back to SN
        "status": num(status),
        # telecounting (power & history)
        "capacity": num(tc.get("ratedPower")),
        "eday": num(tc.get("proPvStatsToday")),
        "etotal": num(tc.get("proPvStatsTotal")),
        "hour_total": num(tl.get("hTotal")),
        "thismonthetotle": num(tc.get("proPvStatsMonth")),
        "lastmonthetotle": num(tc.get("proPvStatsLastMonth")),
        # telemetry (live operating data)
        "pac": num(tl.get("pAc")),
        "temperature": num(tl.get("Temperature")),
        "qac": num(tl.get("qAc")),
        "gridpf": num(tl.get("gridPF")),
        "fac": num(tl.get("Fac")),
        # Three-phase voltages / currents (AC group)
        "vac1": num(tl.get("PHASE-A:Vac")),
        "vac2": num(tl.get("PHASE-B:Vac")),
        "vac3": num(tl.get("PHASE-C:Vac")),
        "iac1": num(tl.get("PHASE-A:Iac")),
        "iac2": num(tl.get("PHASE-B:Iac")),
        "iac3": num(tl.get("PHASE-C:Iac")),
        # MPPT PV inputs (PV group)
        "vpv1": num(tl.get("MPPT-1:Vpv")),
        "vpv2": num(tl.get("MPPT-2:Vpv")),
        "ipv1": num(tl.get("MPPT-1:Ipv")),
        "ipv2": num(tl.get("MPPT-2:Ipv")),
        "ppv1": num(tl.get("MPPT-1:Ppv")),
        "ppv2": num(tl.get("MPPT-2:Ppv")),
        # Pass-through for any MPPT-3 / MPPT-4 on 4-MPPT inverters.
        "vpv3": num(tl.get("MPPT-3:Vpv")),
        "vpv4": num(tl.get("MPPT-4:Vpv")),
        "ipv3": num(tl.get("MPPT-3:Ipv")),
        "ipv4": num(tl.get("MPPT-4:Ipv")),
        "ppv3": num(tl.get("MPPT-3:Ppv")),
        "ppv4": num(tl.get("MPPT-4:Ppv")),
        # Battery (single-battery fallback path for hybrid inverters)
        "vbattery1": num(tl.get("batteryVoltage")),
        "ibattery1": num(tl.get("batteryCurrent")),
        "soc": num(tl.get("soc")),
        "soh": num(tl.get("soh")),
        "pbattery": num(tl.get("pBattery")),
        # Station-level fields the legacy sensors used to read from
        # ``inverter_full``.
        "station_id": station.get("id"),
        "station_name": station.get("name"),
        "installed_power": station.get("installedPower"),
    }

    # Drop None values so legacy sensors' ``empty_value`` logic still works
    # for fields the new API doesn't return (e.g. income sensors).
    return {k: v for k, v in flat.items() if v is not None}


# Type alias to make type inference working for pylance
type SemsCoordinator = SemsDataUpdateCoordinator
