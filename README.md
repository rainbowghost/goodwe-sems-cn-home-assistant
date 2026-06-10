# GoodWe SEMS CN API integration for Home Assistant

[![GitHub Repo stars](https://img.shields.io/github/stars/rainbowghost/goodwe-sems-cn-home-assistant)](https://github.com/rainbowghost/goodwe-sems-cn-home-assistant)

**Languages**: [English](README.md) · [简体中文](README_CN.md)

A Home Assistant custom integration that retrieves PV data from the **GoodWe SEMS+ plant API** (China region). This is an independent project that targets the Chinese GoodWe portal.

If you use the global GoodWe portal (`semsportal.com`), see the [upstream project by TimSoethout](https://github.com/TimSoethout/goodwe-sems-home-assistant) instead.

## What's new in 2.0

Starting with v2.0.0, the integration targets the **SEMS+ plant API** (`sems-plant/api/...`)
instead of the legacy `gopsapi.sems.com.cn/api/v1/...` endpoint. The SEMS+ path
returns more granular data (per-MPPT voltages, per-phase AC measurements,
chamber temperature) and uses a self-signed anti-replay `x-signature` header.
The user-facing entities are unchanged — existing sensors keep their
unique IDs.

See [CHANGELOG.md](CHANGELOG.md) for the full history.

## Setup

### Easiest install method via HACS

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

Add this repository as a custom repository in HACS (Integration category),
then install **GoodWe SEMS CN API** from the Integrations tab.

### Manual Setup

Copy the contents of `custom_components/sems_cn/` to your Home Assistant
`config/custom_components/sems_cn/` directory.

## Configure integration

In the Home Assistant GUI, go to **Settings** → **Devices & Services** →
**Add Integration**. Search for `GoodWe SEMS CN API`.

Required configuration:
- **Username** — your SEMS+ (China) account phone number or email
- **Password** — your SEMS+ (China) account password

Optional:
- **Power Station ID** — if left empty, the integration will query the
  SEMS API and pick the first station found.
- **Update Interval** — polling interval in seconds (default 60).

To find your Power Station ID manually, log in to
[https://semsplus.goodwe.com](https://semsplus.goodwe.com) with your
credentials. The Power Station ID is the UUID in the URL after login.

### Optional: control the inverter power output via the switch entity

It is possible to temporarily pause energy production via the "downtime"
functionality available on the inverter. This is exposed as a switch and
can be used in your own automations.

Please note this calls an undocumented endpoint and can take a few minutes
for the inverter to pick up the change. It takes approximately 60 seconds
to start again when the inverter is in downtime mode.

### Recommended: use visitor account if you do not need to control the inverter

If you are only reading inverter stats, you can use a Visitor (read-only)
account.

Create via the official GoodWe app, or via the web portal:
log in to [https://semsplus.goodwe.com](https://semsplus.goodwe.com), go
to the visitor-account page and create a new visitor account. Log in to
the visitor account once to accept the EULA.

## Sensors

The integration creates the following entities per inverter:

| Entity | Unit | Description |
|---|---|---|
| `<sn>-status` | — | Inverter status (Offline/Waiting/Normal/Fault) |
| `<sn>-capacity` | kW | Rated capacity |
| `<sn>-power` | W | Active power output |
| `<sn>-energy` | kWh | Lifetime energy generation |
| `<sn>-energy-today` | kWh | Today's energy |
| `<sn>-energy-month` | kWh | This month's energy |
| `<sn>-temperature` | °C | Chamber temperature |
| `<sn>-vpv1` … `<sn>-vpv4` | V | PV string voltages (per MPPT) |
| `<sn>-ipv1` … `<sn>-ipv4` | A | PV string currents (per MPPT) |
| `<sn>-vac1` … `<sn>-vac3` | V | Phase voltages (A/B/C) |
| `<sn>-iac1` … `<sn>-iac3` | A | Phase currents (A/B/C) |
| `<sn>-fac` | Hz | Grid frequency |

> Note: legacy `<sn>-income-today` / `<sn>-income-total` sensors from the
> old `gopsapi` API are not exposed — the SEMS+ plant API does not
> surface per-station income data.

## Debug info

Enable debugging in the GUI by going to the integration and selecting
**Enable Debug Logging**. See the [HA documentation](https://www.home-assistant.io/docs/configuration/troubleshooting/#enabling-debug-logging).

Or add to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.sems_cn: debug
```

## Notes

- The SEMS API is sometimes slow; timeout messages may appear as
  `[ERROR]` in the log. The integration continues to work normally and
  retries on the next poll.
- The integration handles `100025 "no_access_or_permission"` and
  `GY0429` rate-limit responses by triggering a back-off refresh
  (5 minutes) — no manual intervention needed.

## Development setup

- Set up the HA development environment:
  https://developers.home-assistant.io/docs/development_environment
- Clone this repo into your HA `config` directory:
  - `cd core/config/custom_components`
  - `git clone git@github.com:rainbowghost/goodwe-sems-cn-home-assistant.git`
- Symlink the integration:
  - `cd core/config/custom_components`
  - `ln -s ../goodwe-sems-cn-home-assistant/custom_components/sems_cn sems_cn`

## Linting

```bash
ruff check custom_components/
ruff format --check custom_components/
mypy custom_components/ --ignore-missing-imports --python-version 3.13
```

To fix lint issues locally:

```bash
ruff check --fix custom_components/
ruff format custom_components/
```

## API documentation

See `E:/Code/sems-plus-api.md` for the full reverse-engineered API
reference (login flow, x-signature algorithm, plant endpoints, error
codes). Out-of-tree to keep the repo slim.

## Credits

This project is an independent fork of
[TimSoethout/goodwe-sems-home-assistant](https://github.com/TimSoethout/goodwe-sems-home-assistant),
relicensed under MIT. The original work targeted the global GoodWe SEMS
API at `semsportal.com`; this project targets the Chinese SEMS+ plant API.

See [CHANGELOG.md](CHANGELOG.md) for the full history.