"""Device helpers for the SEMS integration."""

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


def device_info_for_inverter(
    serial_number: str, inverter_data: dict[str, Any]
) -> DeviceInfo:
    """Build device info for an inverter.

    This is shared across platforms (sensor, switch, etc.) so entities for the
    same inverter are grouped under the same device and show a consistent name.
    """

    name = inverter_data.get("name") or serial_number

    # NOTE: We intentionally keep fallbacks here because not every SEMS payload
    # is guaranteed to contain `model_type`, `safety_version`, etc.
    return DeviceInfo(
        identifiers={(DOMAIN, serial_number)},
        name=f"Inverter {name}",
        manufacturer="GoodWe",
        # Plant API's /information endpoint returns modelType (e.g.
        # "GW10K-SDT-30"); we keep "model_type" as the legacy key name
        # so older flatten dicts still resolve.
        model=inverter_data.get("model_type", "unknown"),
        # safetyVersion is the firmware version reported by the
        # inverter (alias "firmware_version" in the API). Fall back to
        # the SN so the device card always shows something stable
        # instead of "unknown".
        sw_version=(
            inverter_data.get("safety_version")
            or inverter_data.get("firmwareversion")
            or serial_number
        ),
        configuration_url=(
            f"https://semsportal.com/PowerStation/PowerStatusSnMin/"
            f"{inverter_data.get('powerstation_id')}"
            if inverter_data.get("powerstation_id")
            else None
        ),
    )
