"""Tests for the SEMS+ CN API client.

Covers the SEMS+ plant API flow: login with x-signature, stations/devices/
telecounting/telemetry, rate-limit detection, inverter on/off control.
The unit tests use ``unittest.mock`` for the request layer; the integration
tests use ``requests_mock`` to exercise the real SEMS+ URL and payload
shapes documented at ``E:/Code/sems-plus-api.md``.
"""

from unittest.mock import Mock, patch

import pytest
import requests

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


def _devices_payload(sn: str = MOCK_INVERTER_SN, station_id: str = MOCK_STATION_ID) -> dict:
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
                "factors": [{"code": "proPvStatsTotal", "data": "17777.2", "unit": "kWh"}],
            },
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
        with patch.object(
            self.api, "_login", return_value=_token_dict("fresh-token")
        ) as mock_login, patch.object(
            self.api, "_do_http", side_effect=[
                {"code": "C0602", "msg": "account login abnormal"},
                {"code": "00000", "data": ["ok"]},
            ]
        ) as mock_http:
            resp = self.api._request(
                "POST", "https://hz-gateway.sems.com.cn/web/sems/x",
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
        with patch.object(
            self.api, "_do_http",
            return_value={"code": "C0602", "msg": "bad creds"},
        ) as mock_http, patch.object(self.api, "_login") as mock_login:
            resp = self.api._request(
                "POST", _LOGIN_URL,
                headers={"token": "empty"},
            )
        assert resp is None
        # Only the original HTTP call; no re-login attempt.
        assert mock_http.call_count == 1
        mock_login.assert_not_called()


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
        assert groups and any(
            g["code"] == "system" for g in groups
        )

    def test_change_status_returns_true_on_2xx(self, requests_mock):
        requests_mock.post(
            "https://hz-gateway.sems.com.cn/web/sems/PowerStation/SaveRemoteControlInverter",
            json={"code": "00000"}, status_code=200,
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
