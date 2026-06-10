"""Constants for the SEMS+ CN integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME

DOMAIN = "sems_cn"

PLATFORMS = ["sensor", "switch"]

CONF_STATION_ID = "powerstation_id"

DEFAULT_SCAN_INTERVAL = 60  # seconds

# Validation of the user's configuration
SEMS_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_STATION_ID): str,
        vol.Optional(
            CONF_SCAN_INTERVAL, description={"suggested_value": 60}
        ): int,
    }
)

# Sentinel values the old gopsapi API used to mark "sensor absent".
# Kept for any sensors that still compare against these constants.
AC_EMPTY = 6553.5
AC_CURRENT_EMPTY = 6553.5
AC_FEQ_EMPTY = 655.35

STATUS_LABELS = {-1: "Offline", 0: "Waiting", 1: "Normal", 2: "Fault"}


# Plant API factor codes. One source of truth for the new factor names
# so the coordinator's flattening stays in sync with sensor.py. Add new
# factors here when they appear in the API.
FACTOR_CODES = {
    # telecounting group aliases
    "rated_power": "ratedPower",
    "energy_today": "proPvStatsToday",
    "energy_total": "proPvStatsTotal",
    "energy_month": "proPvStatsMonth",
    "energy_last_month": "proPvStatsLastMonth",
    "energy_week": "proPvStatsWeek",
    "energy_year": "proPvStatsYear",
    # telemetry group aliases
    "active_power": "pAc",
    "reactive_power": "qAc",
    "power_factor": "gridPF",
    "grid_frequency": "Fac",
    "total_hours": "hTotal",
    "chamber_temperature": "Temperature",
    # three-phase voltages / currents
    "voltage_a": "PHASE-A:Vac",
    "voltage_b": "PHASE-B:Vac",
    "voltage_c": "PHASE-C:Vac",
    "current_a": "PHASE-A:Iac",
    "current_b": "PHASE-B:Iac",
    "current_c": "PHASE-C:Iac",
    # MPPT inputs (up to 4 MPPTs on quad-MPPT inverters)
    "vpv1": "MPPT-1:Vpv",
    "vpv2": "MPPT-2:Vpv",
    "vpv3": "MPPT-3:Vpv",
    "vpv4": "MPPT-4:Vpv",
    "ipv1": "MPPT-1:Ipv",
    "ipv2": "MPPT-2:Ipv",
    "ipv3": "MPPT-3:Ipv",
    "ipv4": "MPPT-4:Ipv",
    "ppv1": "MPPT-1:Ppv",
    "ppv2": "MPPT-2:Ppv",
    "ppv3": "MPPT-3:Ppv",
    "ppv4": "MPPT-4:Ppv",
    # battery (hybrid inverters)
    "battery_voltage": "batteryVoltage",
    "battery_current": "batteryCurrent",
    "battery_power": "pBattery",
    "battery_soc": "soc",
    "battery_soh": "soh",
    "battery_temperature": "batteryTemperature",
    "bms_temperature": "bmsTemperature",
    "bms_charge_i_max": "bmsChargeIMax",
    "bms_discharge_i_max": "bmsDischargeIMax",
}
