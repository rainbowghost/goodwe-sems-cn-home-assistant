# Changelog

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

[2.0.0]: https://github.com/rainbowghost/goodwe-sems-cn-home-assistant/releases/tag/v2.0.0
[1.0.1]: https://github.com/rainbowghost/goodwe-sems-cn-home-assistant/releases/tag/v1.0.1
[1.0.0]: https://github.com/rainbowghost/goodwe-sems-cn-home-assistant/releases/tag/v1.0.0
