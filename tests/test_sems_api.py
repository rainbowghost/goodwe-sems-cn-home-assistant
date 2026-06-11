"""Tests for the SEMS+ CN API client.

Covers the SEMS+ plant API flow: login with x-signature, stations/devices/
telecounting/telemetry, rate-limit detection, inverter on/off control.
The unit tests use ``unittest.mock`` for the request layer; the integration
tests use ``requests_mock`` to exercise the real SEMS+ URL and payload
shapes documented at ``E:/Code/sems-plus-api.md``.
"""

import json
from unittest.mock import Mock, patch

import pytest
import requests

from custom_components.sems_cn import _flatten_inverter
from custom_components.sems_cn.sems_api import (
    _APP_VERSION,
    _LOGIN_URL,
    SemsApi,
    SemsRateLimitedError,
    _encode_signature,
    _md5_then_base64,
)

MOCK_INVERTER_SN = "4010KDTG245G0340"
MOCK_STATION_ID = "ed172b80-e50f-45e4-9493-72c0abbfa9d6"


def _login_payload(token: str = "freshtoken") -> dict:
    """Realistic SEMS+ login response."""
    return {
        "code": "00000",
        "description": "成功",
        "data": {
            "uid": "eb36ccee-28af-489d-a7f7-1944e967eeb7",
            "timestamp": "1781072044763",
            "token": token,
            "client": "semsPlusAndroid",
            "version": "2.5.2",
            "language": "zh-CN",
            "api": "https://hz-gateway.sems.com.cn/web/sems",
            "region": "cn",
        },
    }


def _token_dict(token: str = "freshtoken") -> dict:
    return _login_payload(token)["data"]


def _stations_payload(station_id: str = MOCK_STATION_ID) -> dict:
    return {
        "code": "00000",
        "data": {
            "dataList": [
                {
                    "id": station_id,
                    "name": "Test Station",
                    "installedPower": 10.0,
                    "status": 1,
                }
            ],
            "size": 2,
            "current": 1,
            "total": 1,
        },
    }


def _devices_payload(
    sn: str = MOCK_INVERTER_SN, station_id: str = MOCK_STATION_ID
) -> dict:
    return {
        "code": "00000",
        "data": {
            "total": 1,
            "deviceDetailList": [
                {
                    "deviceType": "INVERTER",
                    "total": 1,
                    "statusDetailList": [
                        {
                            "status": 5,
                            "total": 1,
                            "snList": [sn],
                            "isHemsMap": {sn: False},
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
            ],
        },
    }


def _telecounting_payload() -> dict:
    return {
        "code": "00000",
        "data": [
            {
                "code": "telecounting_real",
                "alias": "realtime_data",
                "factors": [
                    {"code": "pAc", "data": "6.895", "unit": "kW"},
                    {"code": "ratedPower", "data": "10", "unit": "kW"},
                ],
            },
            {
                "code": "telecounting_today",
                "alias": "day",
                "factors": [{"code": "proPvStatsToday", "data": "27.7", "unit": "kWh"}],
            },
            {
                "code": "telecounting_total",
                "alias": "total",
                "factors": [
                    {"code": "proPvStatsTotal", "data": "17777.2", "unit": "kWh"}
                ],
            },
        ],
    }


def _information_payload(
    model_type: str = "GW10K-SDT-30", safety_version: str = "V1.08.08"
) -> dict:
    """Mirror the /sems-plant/api/equipments/<sn>/information response.

    The real endpoint returns a flat list of ``{code, data, ...}`` factor
    entries covering static inverter metadata. Anonymized to a real
    GoodWe model from ``E:/MyCode/semsplus.txt`` line 45.
    """
    return {
        "code": "00000",
        "data": [
            {"code": "status", "data": "5", "alias": "status"},
            {"code": "deviceName", "data": "Inverter 1", "alias": "name_1"},
            {"code": "sn", "data": MOCK_INVERTER_SN, "alias": "serial_number_1"},
            {"code": "deviceType", "data": "INVERTER_GRID", "alias": "type"},
            {"code": "modelType", "data": model_type, "alias": "model"},
            {"code": "safetyVersion", "data": safety_version, "alias": "firmware_version"},
            {"code": "ratedPower", "data": "10.0", "unit": "kW", "alias": "rated_power"},
        ],
    }


def _telemetry_payload() -> dict:
    return {
        "code": "00000",
        "data": [
            {
                "code": "system",
                "alias": "system_parameters",
                "factors": [
                    {"code": "hTotal", "data": "7471", "unit": "H"},
                    {"code": "Temperature", "data": "48.1", "unit": "℃"},
                ],
            },
            {
                "code": "ac",
                "alias": "ac_parameters",
                "factors": [
                    {"code": "pAc", "data": "6.895", "unit": "kW"},
                    {"code": "PHASE-A:Vac", "data": "232.1", "unit": "V"},
                    {"code": "PHASE-A:Iac", "data": "12.2", "unit": "A"},
                ],
            },
        ],
    }


# ---------------------------------------------------------------------------
# Unit tests — pure functions, no network
# ---------------------------------------------------------------------------


class TestSignatures:
    """Password encoding and x-signature algorithm."""

    def test_md5_then_base64_known_value(self):
        # Verified against the SEMS+ web frontend's MD5-then-base64-of-hex
        # encoding for the password "R15@goodwe".
        expected = "YjYzZjc5MDFiYTExZDE4NTJkODU0ZTdlMDQ4YjNhMGU="
        assert _md5_then_base64("R15@goodwe") == expected

    def test_encode_signature_format(self):
        # Output must be base64, decode to "<64hex>@<digits>"
        import base64

        token = {"uid": "abc", "token": "xyz"}
        sig = _encode_signature(token)
        decoded = base64.b64decode(sig).decode()
        assert "@" in decoded
        hash_part, _, ts = decoded.rpartition("@")
        assert len(hash_part) == 64
        assert ts.isdigit()


class TestFlattenInverter:
    """Plant API factor flattening."""

    def test_empty_live_power_is_zero_watts(self):
        """Offline inverters can return empty strings for kW power factors."""
        flat = _flatten_inverter(
            sn=MOCK_INVERTER_SN,
            station={"id": MOCK_STATION_ID, "name": "Test", "installedPower": 10},
            status=0,
            telecounting_groups=[],
            telemetry_groups=[
                {
                    "code": "ac",
                    "factors": [
                        {"code": "pAc", "data": "", "unit": "kW"},
                        {"code": "qAc", "data": "", "unit": "kVar"},
                    ],
                },
                {
                    "code": "pv",
                    "factors": [{"code": "MPPT-1:Ppv", "data": "", "unit": "kW"}],
                },
            ],
        )

        assert flat["pac"] == "0"
        assert flat["qac"] == "0"
        assert flat["ppv1"] == "0"

    def test_null_live_power_is_zero_watts_without_creating_missing_fields(self):
        """Offline inverters can return null for present power factors."""
        flat = _flatten_inverter(
            sn=MOCK_INVERTER_SN,
            station={"id": MOCK_STATION_ID, "name": "Test", "installedPower": 10},
            status=0,
            telecounting_groups=[],
            telemetry_groups=[
                {
                    "code": "ac",
                    "factors": [
                        {"code": "pAc", "data": None, "unit": "kW"},
                        {"code": "qAc", "data": None, "unit": "kVar"},
                    ],
                },
                {
                    "code": "pv",
                    "factors": [{"code": "MPPT-1:Ppv", "data": None, "unit": "kW"}],
                },
            ],
        )

        assert flat["pac"] == "0"
        assert flat["qac"] == "0"
        assert flat["ppv1"] == "0"
        assert "ppv2" not in flat
        assert "pbattery" not in flat

    def test_power_uses_telecounting_fallback_when_telemetry_is_empty(self):
        """pAc can appear in both telemetry and telecounting groups."""
        flat = _flatten_inverter(
            sn=MOCK_INVERTER_SN,
            station={"id": MOCK_STATION_ID, "name": "Test", "installedPower": 10},
            status=5,
            telecounting_groups=[
                {
                    "code": "telecounting_real",
                    "factors": [{"code": "pAc", "data": "6.895", "unit": "kW"}],
                }
            ],
            telemetry_groups=[
                {
                    "code": "ac",
                    "factors": [{"code": "pAc", "data": None, "unit": "kW"}],
                }
            ],
        )

        assert flat["pac"] == "6895.0"

    def test_null_live_voltage_current_and_frequency_are_zero(self):
        """Offline inverters can return null for present electrical factors."""
        flat = _flatten_inverter(
            sn=MOCK_INVERTER_SN,
            station={"id": MOCK_STATION_ID, "name": "Test", "installedPower": 10},
            status=0,
            telecounting_groups=[],
            telemetry_groups=[
                {
                    "code": "ac",
                    "factors": [
                        {"code": "Fac", "data": None, "unit": "Hz"},
                        {"code": "PHASE-A:Vac", "data": None, "unit": "V"},
                        {"code": "PHASE-A:Iac", "data": None, "unit": "A"},
                    ],
                },
                {
                    "code": "pv",
                    "factors": [
                        {"code": "MPPT-1:Vpv", "data": None, "unit": "V"},
                        {"code": "MPPT-1:Ipv", "data": None, "unit": "A"},
                    ],
                },
                {
                    "code": "system",
                    "factors": [{"code": "Temperature", "data": None, "unit": "C"}],
                },
            ],
        )

        assert flat["fac"] == "0"
        assert flat["vac1"] == "0"
        assert flat["iac1"] == "0"
        assert flat["vpv1"] == "0"
        assert flat["ipv1"] == "0"
        assert "temperature" not in flat
        assert "vac2" not in flat
        assert "ipv2" not in flat

    def test_information_factors_populate_model_type_and_safety_version(self):
        """The /information endpoint exposes modelType and safetyVersion;
        the flatten step must surface both under stable keys for device.py."""
        info = _information_payload()["data"]
        flat = _flatten_inverter(
            sn=MOCK_INVERTER_SN,
            station={"id": MOCK_STATION_ID, "name": "Test", "installedPower": 10},
            status=5,
            telecounting_groups=[],
            telemetry_groups=[],
            information_factors=info,
        )
        assert flat["model_type"] == "GW10K-SDT-30"
        assert flat["safety_version"] == "V1.08.08"

    def test_missing_information_omits_model_and_safety_version(self):
        """If the /information call failed, neither key should appear in
        the flat dict (sensor code and device.py both check for absence)."""
        flat = _flatten_inverter(
            sn=MOCK_INVERTER_SN,
            station={"id": MOCK_STATION_ID, "name": "Test", "installedPower": 10},
            status=5,
            telecounting_groups=[],
            telemetry_groups=[],
            information_factors=None,
        )
        assert "model_type" not in flat
        assert "safety_version" not in flat


class TestSemsApiUnit:
    """Request-level unit tests."""

    def setup_method(self):
        self.hass = Mock()
        self.username = "test_user"
        self.password = "test_password"
        self.api = SemsApi(self.hass, self.username, self.password)

    def test_init(self):
        assert self.api._hass is self.hass
        assert self.api._username == self.username
        assert self.api._password == self.password
        assert self.api._token is None

    @patch("custom_components.sems_cn.sems_api.requests.request")
    def test_login_success(self, mock_request):
        """A successful login stores the token and exposes data.api as base."""
        mock_response = Mock()
        mock_response.json.return_value = _login_payload()
        mock_request.return_value = mock_response

        result = self.api._login()

        assert result is not None
        assert result["api"] == "https://hz-gateway.sems.com.cn/web/sems"
        # Token should be cached so subsequent calls reuse it.
        assert self.api._token["token"] == "freshtoken"

    @patch("custom_components.sems_cn.sems_api.requests.request")
    def test_login_failure_returns_none(self, mock_request):
        mock_response = Mock()
        mock_response.json.return_value = {"code": "C0602", "msg": "bad"}
        mock_request.return_value = mock_response

        assert self.api._login() is None
        assert self.api._token is None

    @patch("custom_components.sems_cn.sems_api.requests.request")
    def test_login_uses_isChinese_flag(self, mock_request):
        """Login body must include isChinese+isLocal for CN routing."""
        mock_response = Mock()
        mock_response.json.return_value = _login_payload()
        mock_request.return_value = mock_response

        self.api._login()
        kwargs = mock_request.call_args.kwargs
        body = kwargs["json"]
        assert body["isChinese"] is True
        assert body["isLocal"] is True
        assert body["agreement"] == 1
        # Password must be encoded as base64(md5_hex(plain)), not base64(plain).
        assert body["pwd"] == _md5_then_base64("test_password")

    @patch("custom_components.sems_cn.sems_api.requests.request")
    def test_login_sends_appversion_and_traceid(self, mock_request):
        mock_response = Mock()
        mock_response.json.return_value = _login_payload()
        mock_request.return_value = mock_response

        self.api._login()
        headers = mock_request.call_args.kwargs["headers"]
        assert headers["appversion"] == _APP_VERSION
        assert "traceid" in headers
        assert len(headers["traceid"]) == 32  # uuid hex, no dashes

    @patch("custom_components.sems_cn.sems_api.requests.request")
    def test_request_sends_x_signature(self, mock_request):
        """Every plant call must carry a fresh x-signature."""
        mock_response = Mock()
        mock_response.json.return_value = _stations_payload()
        mock_request.return_value = mock_response

        self.api._token = _token_dict()
        self.api.get_stations()

        headers = mock_request.call_args.kwargs["headers"]
        assert "x-signature" in headers
        # Verify x-signature decodes to "<hash>@<ms>"
        import base64

        decoded = base64.b64decode(headers["x-signature"]).decode()
        assert "@" in decoded

    @patch("custom_components.sems_cn.sems_api.requests.request")
    def test_rate_limit_GY0429_raises(self, mock_request):
        mock_response = Mock()
        mock_response.json.return_value = {"code": "GY0429", "msg": "rate limited"}
        mock_request.return_value = mock_response

        self.api._token = _token_dict()
        with pytest.raises(SemsRateLimitedError) as exc_info:
            self.api.get_stations()
        assert exc_info.value.retry_after == 300

    @patch("custom_components.sems_cn.sems_api.requests.request")
    def test_rate_limit_100025_raises(self, mock_request):
        """CN plant endpoints return 100025 when token expired."""
        mock_response = Mock()
        mock_response.json.return_value = {"code": "100025", "msg": "no_access"}
        mock_request.return_value = mock_response

        self.api._token = _token_dict()
        with pytest.raises(SemsRateLimitedError) as exc_info:
            self.api.get_telemetry(MOCK_INVERTER_SN, MOCK_STATION_ID)
        assert exc_info.value.retry_after == 300

    @patch("custom_components.sems_cn.sems_api.requests.request")
    def test_non_success_response_returns_none(self, mock_request):
        """Unknown error codes (not rate-limit) return None, not raise."""
        mock_response = Mock()
        mock_response.json.return_value = {"code": "999", "msg": "???"}
        mock_request.return_value = mock_response

        self.api._token = _token_dict()
        assert self.api.get_stations() is None

    @patch("custom_components.sems_cn.sems_api.requests.request")
    def test_network_error_propagates(self, mock_request):
        mock_request.side_effect = requests.ConnectionError("network down")
        self.api._token = _token_dict()
        with pytest.raises(requests.ConnectionError):
            self.api.get_stations()

    @patch("custom_components.sems_cn.sems_api.requests.request")
    def test_get_stations_uses_correct_path(self, mock_request):
        mock_response = Mock()
        mock_response.json.return_value = _stations_payload()
        mock_request.return_value = mock_response

        self.api._token = _token_dict()
        self.api.get_stations()

        url = mock_request.call_args.kwargs["url"] or mock_request.call_args.args[0]
        assert "/sems-plant/api/app/v2/stations/page" in url
        body = mock_request.call_args.kwargs["json"]
        assert body == {"current": 1, "size": 100}

    @patch("custom_components.sems_cn.sems_api.requests.request")
    def test_get_devices_passes_station_id_as_query(self, mock_request):
        mock_response = Mock()
        mock_response.json.return_value = _devices_payload()
        mock_request.return_value = mock_response

        self.api._token = _token_dict()
        self.api.get_devices(MOCK_STATION_ID)

        params = mock_request.call_args.kwargs["params"]
        assert params == {"stationId": MOCK_STATION_ID}

    @patch("custom_components.sems_cn.sems_api.requests.request")
    def test_get_information_returns_data_list(self, mock_request):
        """A successful /information call returns the parsed data list
        and stamps the cache so the second call doesn't hit the wire."""
        mock_response = Mock()
        mock_response.json.return_value = _information_payload()
        mock_request.return_value = mock_response

        self.api._token = _token_dict()

        first = self.api.get_information(MOCK_INVERTER_SN, MOCK_STATION_ID)
        second = self.api.get_information(MOCK_INVERTER_SN, MOCK_STATION_ID)

        # Endpoint hit exactly once thanks to the 24h cache.
        assert mock_request.call_count == 1
        # Path and query string match the captured plant API.
        url = mock_request.call_args.args[1]
        assert url.endswith(f"/sems-plant/api/equipments/{MOCK_INVERTER_SN}/information")
        assert mock_request.call_args.kwargs["params"] == {
            "deviceType": "INVERTER",
            "pwId": MOCK_STATION_ID,
        }
        # Returned data is the unwrapped list from resp["data"].
        assert isinstance(first, list)
        assert any(f["code"] == "modelType" for f in first)
        # Second call is the cached payload (same object).
        assert first is second

    @patch("custom_components.sems_cn.sems_api.requests.request")
    def test_get_information_caches_none_on_failure(self, mock_request):
        """If /information returns a non-success response, the cache stores
        ``None`` for the full TTL so a transient failure doesn't trigger
        a tight retry loop on the next coordinator tick."""
        mock_response = Mock()
        mock_response.json.return_value = {"code": "99999", "msg": "boom"}
        mock_request.return_value = mock_response

        self.api._token = _token_dict()
        assert self.api.get_information(MOCK_INVERTER_SN, MOCK_STATION_ID) is None
        # Second call must not hit the wire — None is cached too.
        assert self.api.get_information(MOCK_INVERTER_SN, MOCK_STATION_ID) is None
        assert mock_request.call_count == 1

    @patch("custom_components.sems_cn.sems_api.requests.request")
    def test_change_status_off(self, mock_request):
        """change_status('2') sends InverterStatus=2 (turn off)."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": "00000"}
        mock_request.return_value = mock_response

        self.api._token = _token_dict()
        self.api.change_status(MOCK_INVERTER_SN, "2")

        body = mock_request.call_args.kwargs["json_body"]
        assert body == {
            "InverterSN": MOCK_INVERTER_SN,
            "InverterStatusSettingMark": "1",
            "InverterStatus": "2",
        }

    def test_ensure_api_base_logs_in_if_needed(self):
        """First call to a plant endpoint triggers login."""
        with patch.object(self.api, "_login") as mock_login:
            mock_login.return_value = _token_dict()
            base = self.api._ensure_api_base()
            assert base == "https://hz-gateway.sems.com.cn/web/sems"
            mock_login.assert_called_once()

    def test_ensure_api_base_uses_cached_token(self):
        """Subsequent calls reuse the cached token without re-login."""
        self.api._token = _token_dict()
        with patch.object(self.api, "_login") as mock_login:
            base = self.api._ensure_api_base()
            assert base == "https://hz-gateway.sems.com.cn/web/sems"
            mock_login.assert_not_called()

    def test_request_C0602_triggers_relogin_and_retry(self):
        """C0602 on a plant call with a cached token should invalidate the
        token, re-login, and retry the request once."""
        self.api._token = _token_dict("stale-token")

        # First call: C0602 (stale token). Second call (after re-login):
        # success. Login is mocked so the test stays offline.
        with (
            patch.object(
                self.api, "_login", return_value=_token_dict("fresh-token")
            ) as mock_login,
            patch.object(
                self.api,
                "_do_http",
                side_effect=[
                    {"code": "C0602", "msg": "account login abnormal"},
                    {"code": "00000", "data": ["ok"]},
                ],
            ) as mock_http,
        ):
            resp = self.api._request(
                "POST",
                "https://hz-gateway.sems.com.cn/web/sems/x",
            )

        assert resp == {"code": "00000", "data": ["ok"]}
        # Two HTTP calls: failed first, then retry after re-login.
        assert mock_http.call_count == 2
        # Re-login was triggered exactly once.
        mock_login.assert_called_once()
        # Token was refreshed.
        assert self.api._token["token"] == "fresh-token"

    def test_request_C0602_without_cached_token_does_not_retry(self):
        """C0602 on the login call itself should not trigger another login
        (would loop forever). The call returns None."""
        self.api._token = None
        with (
            patch.object(
                self.api,
                "_do_http",
                return_value={"code": "C0602", "msg": "bad creds"},
            ) as mock_http,
            patch.object(self.api, "_login") as mock_login,
        ):
            resp = self.api._request(
                "POST",
                _LOGIN_URL,
                headers={"token": "empty"},
            )
        assert resp is None
        # Only the original HTTP call; no re-login attempt.
        assert mock_http.call_count == 1
        mock_login.assert_not_called()

    def test_diagnostics_redacts_password(self):
        """The downloaded diagnostics must not include the user's password
        or API token in cleartext. The config_entry.data dict holds the
        password under the ``password`` key; the SEMS+ token dict holds
        it under ``pwd``/``token``."""
        import asyncio
        from unittest.mock import MagicMock

        from custom_components.sems_cn.diagnostics import (
            async_get_config_entry_diagnostics,
        )

        class FakeCoord:
            def __init__(self, d):
                self.data = d
                self.last_update_success = True

        class FakeEntry:
            def __init__(self):
                self.data = {
                    "username": "user@example.com",
                    "password": "supersecret",
                }
                self.runtime_data = None

        class FakeData:
            def __init__(self):
                self.inverters = {"sn1": {"status": 5, "pac": "1000"}}
                self.raw_telecounting = {
                    "sn1": [{"code": "telecounting_real", "factors": []}]
                }
                self.raw_telemetry = {"sn1": [{"code": "system", "factors": []}]}
                self.raw_all_status = {"station1": []}

        fake = FakeEntry()
        fake.runtime_data = type("RD", (), {"coordinator": FakeCoord(FakeData())})()
        result = asyncio.run(
            async_get_config_entry_diagnostics(MagicMock(), fake)
        )

        # entry.username + entry.password must be redacted
        assert result["entry"]["username"] == "**REDACTED**"
        assert result["entry"]["password"] == "**REDACTED**"
        # the secrets must not appear anywhere in the dump
        assert "supersecret" not in json.dumps(result)
        assert "user@example.com" not in json.dumps(result)
        # inverters values are NOT credentials, so they should pass
        # through unchanged
        assert result["coordinator"]["inverters"]["sn1"]["status"] == 5
        assert result["coordinator"]["inverters"]["sn1"]["pac"] == "1000"


# ---------------------------------------------------------------------------
# Integration tests — request against a mocked server
# ---------------------------------------------------------------------------


class TestSemsApiIntegration:
    """requests_mock exercises real URL paths and response shapes."""

    def setup_method(self):
        self.hass = Mock()
        self.api = SemsApi(self.hass, "u", "p")
        # Pre-seed token so tests don't have to log in first.
        self.api._token = _token_dict()

    def test_login_returns_token(self, requests_mock):
        requests_mock.post(_LOGIN_URL, json=_login_payload("login1"))
        token = self.api._login()
        assert token["token"] == "login1"
        assert token["api"].endswith("/web/sems")

    def test_get_stations_returns_dataList(self, requests_mock):
        requests_mock.post(
            "https://hz-gateway.sems.com.cn/web/sems/sems-plant/api/app/v2/stations/page",
            json=_stations_payload(),
        )
        stations = self.api.get_stations()
        assert stations and stations[0]["id"] == MOCK_STATION_ID

    def test_get_devices_returns_devices(self, requests_mock):
        requests_mock.get(
            "https://hz-gateway.sems.com.cn/web/sems/sems-plant/api/stations/device/all-status",
            json=_devices_payload(),
        )
        devices = self.api.get_devices(MOCK_STATION_ID)
        assert devices and devices[0]["deviceType"] == "INVERTER"

    def test_get_telecounting_returns_data(self, requests_mock):
        requests_mock.get(
            "https://hz-gateway.sems.com.cn/web/sems/sems-plant/api/equipments/"
            f"{MOCK_INVERTER_SN}/telecounting",
            json=_telecounting_payload(),
        )
        groups = self.api.get_telecounting(MOCK_INVERTER_SN, MOCK_STATION_ID)
        assert groups and groups[0]["code"] == "telecounting_real"

    def test_get_telemetry_returns_data(self, requests_mock):
        requests_mock.get(
            "https://hz-gateway.sems.com.cn/web/sems/sems-plant/api/equipments/"
            f"{MOCK_INVERTER_SN}/telemetry",
            json=_telemetry_payload(),
        )
        groups = self.api.get_telemetry(MOCK_INVERTER_SN, MOCK_STATION_ID)
        assert groups and any(g["code"] == "system" for g in groups)

    def test_change_status_returns_true_on_2xx(self, requests_mock):
        requests_mock.post(
            "https://hz-gateway.sems.com.cn/web/sems/PowerStation/SaveRemoteControlInverter",
            json={"code": "00000"},
            status_code=200,
        )
        assert self.api.change_status(MOCK_INVERTER_SN, "2") is True

    def test_change_status_returns_false_on_error(self, requests_mock):
        requests_mock.post(
            "https://hz-gateway.sems.com.cn/web/sems/PowerStation/SaveRemoteControlInverter",
            status_code=500,
        )
        assert self.api.change_status(MOCK_INVERTER_SN, "2") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
