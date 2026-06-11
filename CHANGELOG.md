## [2.0.8] - 2026-06-11

### Fixed

- **Diagnostics redaction now covers config-entry credentials.** The
  diagnostics download previously redacted the SEMS+ login token but
  not the user's `username` and `password` stored in
  `config_entry.data`. Both are now in the `TO_REDACT` set, so the
  downloaded JSON shows them as `**REDACTED**` instead of cleartext.

### Added

- **`raw_all_status` in diagnostics JSON.** The coordinator now keeps
  the per-station device list (the response of `get_devices`) verbatim
  and surfaces it under `coordinator.raw_all_status` in the
  diagnostics file, alongside `raw_telecounting` and `raw_telemetry`.
  Useful for debugging inverter-status mapping issues where the
  `statusDetailList` shape is unexpected.

[2.0.8]: https://github.com/rainbowghost/goodwe-sems-cn-home-assistant/releases/tag/v2.0.8

## [2.0.7] - 2026-06-10

### Added

- **Download-diagnostics button**. Home Assistant now shows a
  "Download diagnostics" entry on the GoodWe SEMS CN API integration
  card (Settings → Devices & services → ⋯ → Download diagnostics).
  The downloaded JSON file contains the integration's runtime config
  (with credentials redacted), the coordinator's flattened
  per-inverter dict, and the raw SEMS+ plant-API factor groups
  (telecounting and telemetry) for every inverter. Useful for
  bug reports when a sensor reads the wrong value or is missing
  altogether — the file shows exactly what came off the wire.
- **`<sn>-status` sensor exposes a `raw_value` attribute**. The
  status code (0-9) is now also available as a separate entity
  attribute in Developer Tools → States, alongside the existing
  `statusText` label. Handy for debugging which state the inverter
  is in.

[2.0.7]: https://github.com/rainbowghost/goodwe-sems-cn-home-assistant/releases/tag/v2.0.7

## [2.0.6] - 2026-06-10

### Fixed

- **Offline PV/AC electrical values**. The SEMS+ plant API can return
  `null` or an empty string for present live voltage/current/frequency
  factors while an inverter is offline. Present-but-empty `MPPT-N:Vpv`,
  `MPPT-N:Ipv`, `PHASE-*:Vac`, `PHASE-*:Iac`, and `Fac` values now
  normalize to `0`, so Home Assistant shows `0 V`, `0 A`, or `0 Hz`
  instead of `unknown`. Temperature remains unavailable when the API
  does not provide it.

[2.0.6]: https://github.com/rainbowghost/goodwe-sems-cn-home-assistant/releases/tag/v2.0.6

## [2.0.5] - 2026-06-10

### Fixed

- **Offline power factor values**. The SEMS+ plant API can return `null`
  or an empty string for live power factors (`pAc`, `qAc`,
  `MPPT-N:Ppv`, `pBattery`) while still reporting power units. These
  present-but-empty power values now normalize to `0` so Home
  Assistant shows `0 W` instead of `unknown`.
- **Active power fallback**. `pAc` now falls back from telemetry to the
  telecounting payload when telemetry is empty, while still leaving
  genuinely missing factors absent.

[2.0.5]: https://github.com/rainbowghost/goodwe-sems-cn-home-assistant/releases/tag/v2.0.5

## [2.0.4] - 2026-06-10

### Fixed

- **Inverter status labels**. The legacy `gopsapi` API had a 4-state
  status (Offline / Waiting / Normal / Fault). The new SEMS+ plant
  API returns an 0-indexed enumeration with 10 distinct states,
  reverse-engineered from the GoodWe web frontend's status-icons
  table:

  | code | label | (web nameKey) |
  |---|---|---|
  | 0 | Offline | `offline` |
  | 1 | Online | `online` |
  | 2 | Fault | `fault` |
  | 3 | Awaiting | `await` |
  | 4 | Shutdown | `shutdown` |
  | 5 | Running | `running` |
  | 6 | Charging | `charging_1` |
  | 7 | Discharging | `discharging` |
  | 8 | Available | `available` |
  | 9 | Maintenance | `in_maintenance_status` |

  v2.0.0–2.0.3 still had the 4-state mapping, so any status code
  outside `{-1, 0, 1, 2}` (in particular `5 = Running`, the most
  common state for an actively-producing inverter) fell through to
  `"Unknown"`. v2.0.4 replaces the mapping with the full 10-state
  table.

[2.0.4]: https://github.com/rainbowghost/goodwe-sems-cn-home-assistant/releases/tag/v2.0.4

## [2.0.3] - 2026-06-10

### Removed

- **Inverter control switch** (`switch.py` removed). The SEMS+ control
  endpoint is undocumented, region-specific, and a wrong command could
  leave the inverter stuck in downtime mode. The integration is now
  read-only — control the inverter through the official GoodWe
  app/portal instead.
- **`<sn>-lastmonthetotle` sensor**. The plant API does not expose
  per-station last-month data (only today / week / month / year /
  lifetime). The sensor could never have had a value.

### Fixed

- **Automatic re-login on `C0602`**. When a plant call returns the
  `account_login_abnormal` code (typically a stale token the server
  has invalidated), the client now invalidates the cached token, runs
  a fresh `cross-login`, and retries the request once before
  surfacing the error. The login call itself still propagates `C0602`
  immediately (re-trying a fresh login would loop forever).

[2.0.3]: https://github.com/rainbowghost/goodwe-sems-cn-home-assistant/releases/tag/v2.0.3

## [2.0.2] - 2026-06-10

### Fixed

- **Grid AC frequency sensor**. The new plant API exposes a single grid
  frequency value (factor `Fac`), not one per phase as the legacy
  gopsapi API did. v2.0.0/2.0.1 defined `<sn>-fac1`/2/3 but the
  coordinator only provided a single `fac` key, so all three sensors
  returned `None`. v2.0.2 collapses them into a single sensor
  `<sn>-grid_ac_frequency` reading the one available `Fac` factor.

### Removed

- **Income sensors** `<sn>-iday` (Income Today) and `<sn>-itotal`
  (Income Total). The SEMS+ plant API does not expose per-station
  income data, so these sensors could never have a value. Removing
  them up front avoids a `unavailable` entity in Home Assistant.

[2.0.2]: https://github.com/rainbowghost/goodwe-sems-cn-home-assistant/releases/tag/v2.0.2

# Changelog

## [2.0.1] - 2026-06-10

### Fixed

- **Power sensor unit conversion**. The new SEMS+ plant API reports
  `pAc` (active power), `qAc` (reactive power), `MPPT-N:Ppv` (per-MPPT
  power) and `pBattery` (battery power) in **kW / kVar**, but the
  legacy sensors report their `native_unit_of_measurement` as **W / var**.
  v2.0.0 stored the kW value verbatim, so HA displayed e.g.
  `pac = 2.587 W` instead of the expected `2587 W`. v2.0.1 multiplies
  the affected factors by 1000 in the coordinator
  (`__init__.py::_flatten_inverter`) before they reach the sensor
  layer, restoring the v1.x magnitude for active / reactive / per-MPPT
  power. `capacity`, energy, voltage, current and temperature were
  already in the right unit and are unchanged.
- Live-verified: `pac` now reports `2587 W` (was `2.587 W`), `ppv1`
  reports `1627 W` (was `1.627 W`).

## [2.0.0] - 2026-06-10

### Changed

- **Migrated to the SEMS+ plant API**. The integration no longer talks
  to the legacy `gopsapi.sems.com.cn/api/v1/...` endpoint. It now uses
  the four-step SEMS+ plant flow:
  1. `POST` `semsplus.goodwe.com/web/sems/sems-user/api/v1/auth/cross-login`
     with `isChinese:true, isLocal:true` for CN routing
  2. `POST` `<data.api>/sems-plant/api/app/v2/stations/page`
  3. `GET`  `<data.api>/sems-plant/api/stations/device/all-status`
  4. `GET`  `<data.api>/sems-plant/api/equipments/{SN}/telecounting`
  5. `GET`  `<data.api>/sems-plant/api/equipments/{SN}/telemetry`
- **Self-signed `x-signature` header**. Every plant call computes
  `base64(sha256(now_ms@uid@token) + "@" + now_ms)` and sends it as
  `x-signature`. The same anti-replay scheme upstream uses; reverse-
  engineered from the SEMS+ web frontend's `encodeSignature()`.
- **Rate-limit handling**. The client raises `SemsRateLimitedError` on
  either `GY0429` (global rate limit) or `100025` (CN plant endpoint:
  token expired / scope rejected). The coordinator translates to
  `UpdateFailed(retry_after=300)` so HA backs off automatically.
- **Coordinator normalizes new factor-group response shape to the legacy
  flat dict** that existing sensors already read. Unique IDs and entity
  names are preserved.
- **Removed `GOODWE_SPELLING` constants** (the old typo'd field names
  like `tempperature`, `thismonthetotle`) — the new API uses correct
  spellings.
- **Added `FACTOR_CODES`** in `const.py` — one source of truth for the
  new factor names.
- **README now bilingual** (English `README.md` + 简体中文 `README_CN.md`)
  with a language switcher at the top of each.

### Added (sensor coverage)

The plant API exposes more granular data than the legacy endpoint. New
sensors per inverter (one per MPPT for 4-MPPT inverters):

- `<sn>-vpv1` … `<sn>-vpv4` — PV string voltages (V)
- `<sn>-ipv1` … `<sn>-ipv4` — PV string currents (A)
- `<sn>-vac1` / `vac2` / `vac3` — per-phase AC voltage (V)
- `<sn>-iac1` / `iac2` / `iac3` — per-phase AC current (A)
- `<sn>-fac` — grid frequency (Hz)
- `<sn>-temperature` — chamber temperature (°C)

### Removed

- **Homekit / powerflow sensors** (`<sn>-homekit`, `<sn>-load`,
  `<sn>-pv`, `<sn>-grid`, `<sn>-battery`, `<sn>-genset`, `<sn>-soc`,
  energy-charts sensors). The SEMS+ plant API does not surface
  powerflow data; the corresponding entities become `unavailable`
  after upgrade but can be manually removed from the entity registry.
- **Income sensors** (`<sn>-iday`, `<sn>-itotal`) — plant API doesn't
  expose per-station income data.
- **Legacy `GOODWE_SPELLING` field mappings** (`tempperature` typo,
  `bettery` typo, `energeStatistics*` typos).

### Notes

- The new login uses `base64(md5_hex_string(plain_password))` for the
  `pwd` field — **not** `base64(plain_password)` (legacy) or
  `base64(md5_raw_bytes(plain_password))`.
- The token's `timestamp` field is the **expiration time** in unix ms,
  not the issue time. Tokens are valid for ~4 hours. The coordinator
  reuses the cached token until the API returns `100025`, then
  triggers a fresh login.
- The `cn.semsportal.com` host that upstream's v10.x PowerStation v3
  path tries to reach **does not resolve from CN**. This fork stays on
  the SEMS+ plant API exclusively; the global `semsportal.com` path is
  not used.
- API behaviour verified end-to-end on a live CN account
  (`18958079499`, CN gateway `hz-gateway.sems.com.cn`).

## [1.0.1] - 2026-06-10

### Changed

- Ship local brand assets (GoodWe logos) at `custom_components/sems_cn/brand/`
  so HA 2026.3+ shows the brand icon even before any HACS-side brand
  registry entry exists.

## [1.0.0] - 2026-06-09

The first release as an independent project, forked from
[TimSoethout/goodwe-sems-home-assistant](https://github.com/TimSoethout/goodwe-sems-home-assistant)
at v9.1.1.

### Changed

- **Domain renamed** from `sems` to `sems_cn` (integration directory renamed accordingly).
  Users with the upstream v9.1.1 integration installed must remove the old
  integration before installing this version — entities will not migrate
  automatically.
- **Version reset** to 1.0.0 to mark the project as independently versioned.
- **Branding and references** updated to `rainbowghost/goodwe-sems-cn-home-assistant`
  (manifest, README, issue tracker, copilot instructions).

### Notes

- This release continued to target the **Chinese SEMS+ API** at
  `gopsapi.sems.com.cn`, the same endpoint that was added in the v9.1.x fork.
- The upstream project has continued to evolve (v10.0.0 introduced a
  dual-login flow that supports both the global `semsportal.com` API and the
  newer SEMS+ service). This project did **not** pull those changes.
- The three legacy test files in `tests/` have been consolidated into
  `tests/test_sems_api.py`.

### Acknowledgments

- Original work by Tim Soethout and contributors, MIT licensed.
- All v9.1.x modifications to support the China region API were contributed
  under the same MIT terms.

[2.0.1]: https://github.com/rainbowghost/goodwe-sems-cn-home-assistant/releases/tag/v2.0.1
[2.0.0]: https://github.com/rainbowghost/goodwe-sems-cn-home-assistant/releases/tag/v2.0.0
[1.0.1]: https://github.com/rainbowghost/goodwe-sems-cn-home-assistant/releases/tag/v1.0.1
[1.0.0]: https://github.com/rainbowghost/goodwe-sems-cn-home-assistant/releases/tag/v1.0.0
