# GoodWe SEMS CN API 集成（Home Assistant）

[![GitHub Repo stars](https://img.shields.io/github/stars/rainbowghost/goodwe-sems-cn-home-assistant)](https://github.com/rainbowghost/goodwe-sems-cn-home-assistant)

**语言**: [English](README.md) · [简体中文](README_CN.md)

一个 Home Assistant 自定义集成，从 **GoodWe SEMS+ plant API**（中国区）获取光伏数据。这是独立项目，目标是中国版 GoodWe 平台。

如果你使用国际版 GoodWe 平台（`semsportal.com`），请参考 [TimSoethout 的上游项目](https://github.com/TimSoethout/goodwe-sems-home-assistant)。

## 2.0 版新特性

从 v2.0.0 开始，本集成改用 **SEMS+ plant API**（`sems-plant/api/...`），
替代了老的 `gopsapi.sems.com.cn/api/v1/...` 接口。SEMS+ 返回更细粒度的数据
（每路 MPPT 电压、每相 AC 测量、电腔温度），并使用自签的 `x-signature`
防重放 header。前端的实体不变——现有传感器保留原 unique_id。

完整变更历史见 [CHANGELOG.md](CHANGELOG.md)。

## 安装

### 通过 HACS（推荐）

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

把本仓库作为 HACS 自定义仓库添加（集成类目），然后在集成页签安装
**GoodWe SEMS CN API**。

### 手动安装

把 `custom_components/sems_cn/` 整个目录拷贝到 Home Assistant 的
`config/custom_components/sems_cn/` 目录下。

## 配置

在 HA 界面，**设置** → **设备与服务** → **添加集成**，搜索
`GoodWe SEMS CN API`。

必填：
- **用户名** — 你的 SEMS+（中国）账号（手机号或邮箱）
- **密码** — 你的 SEMS+（中国）账号密码

可选：
- **电站 ID** — 留空则集成会查 API 自动取第一个电站
- **更新间隔** — 轮询秒数（默认 60）

手动找电站 ID：登录 [https://semsplus.goodwe.com](https://semsplus.goodwe.com)，
URL 里的 UUID 就是电站 ID。

### 可选：通过 switch 实体控制逆变器开关

可以通过逆变器的"停机"功能临时停止发电。集成以 switch 实体的形式暴露，
可以在自动化里调用。

注意：这个调用的是非公开接口，逆变器端要几分钟才会响应。从停机状态恢复
到发电大约需要 60 秒。

### 推荐：只读场景用 Visitor 账号

如果你只需要读数据，不要控制开关，建议创建一个 Visitor（只读）账号。

在官方 GoodWe app 或网页端创建：登录
[https://semsplus.goodwe.com](https://semsplus.goodwe.com)，到 visitor 账号页面
新建一个 visitor 账号，然后用该账号登录一次接受 EULA。

## 传感器

每台逆变器会创建以下实体：

| 实体 | 单位 | 说明 |
|---|---|---|
| `<sn>-status` | — | 逆变器状态（离线/待机/正常/故障）|
| `<sn>-capacity` | kW | 额定功率 |
| `<sn>-power` | W | 当前有功功率 |
| `<sn>-energy` | kWh | 累计发电量 |
| `<sn>-energy-today` | kWh | 今日发电量 |
| `<sn>-energy-month` | kWh | 本月发电量 |
| `<sn>-temperature` | °C | 电腔温度 |
| `<sn>-vpv1` … `<sn>-vpv4` | V | 各路 MPPT 电压 |
| `<sn>-ipv1` … `<sn>-ipv4` | A | 各路 MPPT 电流 |
| `<sn>-vac1` … `<sn>-vac3` | V | 三相电压（A/B/C）|
| `<sn>-iac1` … `<sn>-iac3` | A | 三相电流（A/B/C）|
| `<sn>-fac` | Hz | 电网频率 |

> 注意：老 `gopsapi` 接口里的 `<sn>-income-today` / `<sn>-income-total`
> 在 SEMS+ plant API 里没有数据，所以 v2 不再暴露。

## 调试

在集成页点 **启用调试日志**，参考 [HA 文档](https://www.home-assistant.io/docs/configuration/troubleshooting/#enabling-debug-logging)。

或者在 `configuration.yaml` 里加：

```yaml
logger:
  default: info
  logs:
    custom_components.sems_cn: debug
```

## 注意事项

- SEMS API 有时会慢，超时可能以 `[ERROR]` 出现在日志里。集成会自动在
  下一次轮询重试，**不需要手动干预**。
- `100025 "no_access_or_permission"`（token过期）和 `GY0429`（限流）
  都会触发集成自动 5 分钟退避，期间 HA 不重试。

## 开发设置

- 搭 HA 开发环境：
  https://developers.home-assistant.io/docs/development_environment
- 克隆本仓库到 HA `config` 目录：
  - `cd core/config/custom_components`
  - `git clone git@github.com:rainbowghost/goodwe-sems-cn-home-assistant.git`
- 建符号链接：
  - `cd core/config/custom_components`
  - `ln -s ../goodwe-sems-cn-home-assistant/custom_components/sems_cn sems_cn`

## Lint

```bash
ruff check custom_components/
ruff format --check custom_components/
mypy custom_components/ --ignore-missing-imports --python-version 3.13
```

本地自动修复：

```bash
ruff check --fix custom_components/
ruff format custom_components/
```

## API 文档

完整逆向 API 参考（含登录流程、x-signature 算法、plant 端点、错误码）
放在 `E:/Code/sems-plus-api.md`。这份文档不放在仓库里，保持 repo 精简。

## 致谢

本项目是独立 fork 自
[TimSoethout/goodwe-sems-home-assistant](https://github.com/TimSoethout/goodwe-sems-home-assistant)，
使用 MIT 协议。原项目针对国际版 GoodWe SEMS API（`semsportal.com`）；
本项目针对中国版 SEMS+ plant API。

完整历史见 [CHANGELOG.md](CHANGELOG.md)。