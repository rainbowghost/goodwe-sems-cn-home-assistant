# Changelog

## [1.0.0] - 2026-06-XX

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

- This release continues to target the **Chinese SEMS+ API** at
  `gopsapi.sems.com.cn`, the same endpoint that was added in the v9.1.x fork.
- The upstream project has continued to evolve (v10.0.0 introduces a
  dual-login flow that supports both the global `semsportal.com` API and the
  newer SEMS+ service). This project does **not** pull those changes; if you
  use the global portal, use the upstream project instead.
- The three legacy test files in `tests/` have been consolidated into
  `tests/test_sems_api.py`. The CN-specific `requests_mock`-based tests are
  preserved.

### Acknowledgments

- Original work by Tim Soethout and contributors, MIT licensed.
- All v9.1.x modifications to support the China region API were contributed
  under the same MIT terms.

[1.0.0]: https://github.com/rainbowghost/goodwe-sems-cn-home-assistant/releases/tag/v1.0.0
