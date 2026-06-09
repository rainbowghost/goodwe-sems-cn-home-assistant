# GoodWe SEMS CN API integration for Home Assistant

[![GitHub Repo stars](https://img.shields.io/github/stars/rainbowghost/goodwe-sems-cn-home-assistant)](https://github.com/rainbowghost/goodwe-sems-cn-home-assistant)

A Home Assistant custom integration that retrieves PV data from the **GoodWe SEMS+ (China region) cloud API**. This is an independent project that targets the Chinese GoodWe portal at `gopsapi.sems.com.cn`.

If you use the global GoodWe portal (`semsportal.com`), see the [upstream project by TimSoethout](https://github.com/TimSoethout/goodwe-sems-home-assistant) instead.

## Setup

### Easiest install method via HACS

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

Add this repository as a custom repository in HACS (Integration category), then install **GoodWe SEMS CN API** from the Integrations tab.

### Manual Setup

Copy the contents of `custom_components/sems_cn/` to your Home Assistant `config/custom_components/sems_cn/` directory.

## Configure integration

In the Home Assistant GUI, go to `Configuration` > `Integrations` and click `Add Integration`. Search for `GoodWe SEMS CN API`.

Required configuration:
- **Username** — your SEMS+ (China) account username
- **Password** — your SEMS+ (China) account password

Optional:
- **Power Station ID** — if left empty, the integration will query the SEMS API and pick the first station found.
- **Update Interval** — polling interval in seconds (default 60).

To find your Power Station ID manually, log in to the SEMS Portal with your credentials:
https://www.semsportal.com (China accounts also use this domain)

After login the ID appears in the URL, e.g.:
`https://semsportal.com/PowerStation/PowerStatusSnMin/12345678-1234-1234-1234-123456789012`

In this example the Power Station ID is `12345678-1234-1234-1234-123456789012`.

### Optional: control the inverter power output via the "switch" entity

It is possible to temporarily pause energy production via the "downtime" functionality available on the inverter. This is exposed as a switch and can be used in your own automations.

Please note it uses an undocumented API and can take a few minutes for the inverter to pick up the change. It takes approximately 60 seconds to start again when the inverter is in downtime mode.

### Recommended: use visitor account if you do not need to control the inverter

If you are only reading inverter stats, you can use a Visitor (read-only) account.

Create via the official GoodWe app, or via the web portal:
Log in to www.semsportal.com, go to https://semsportal.com/powerstation/stationInfonew and create a new visitor account. Log in to the visitor account once to accept the EULA.

## Debug info

Enable debugging in the GUI by going to the integration and selecting "Enable Debug Logging" in the top right corner. See [HA documentation](https://www.home-assistant.io/docs/configuration/troubleshooting/#enabling-debug-logging).

Or add the last line to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.sems_cn: debug
```

## Notes

* The SEMS API is sometimes slow; timeout messages may appear as `[ERROR]` in the log. The integration will continue to work normally and retry on the next poll.

## Development setup

- Set up the HA development environment: https://developers.home-assistant.io/docs/development_environment
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

## Credits

This project is an independent fork of [TimSoethout/goodwe-sems-home-assistant](https://github.com/TimSoethout/goodwe-sems-home-assistant), relicensed under MIT. The original work targeted the global GoodWe SEMS API at `semsportal.com`; this project targets the Chinese SEMS+ API at `gopsapi.sems.com.cn`.

See [CHANGELOG.md](CHANGELOG.md) for the history of divergence from the upstream project.
