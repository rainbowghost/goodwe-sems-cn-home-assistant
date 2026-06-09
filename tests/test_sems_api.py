"""Tests for the SEMS CN API module.

Tests are split into two styles:

* ``TestSemsApiUnit`` — uses ``unittest.mock`` to verify the request flow
  (token renewal, validation, error handling) without going through the wire.
* ``TestSemsApiIntegration`` — uses ``requests_mock`` to exercise the actual
  endpoint URLs and payload shapes used by the China-region SEMS+ API at
  ``gopsapi.sems.com.cn``.
"""

from unittest.mock import Mock, patch

import pytest
import requests

from custom_components.sems_cn.sems_api import (
    _APIURL,
    OutOfRetries,
    SemsApi,
    _GetPowerStationIdByOwnerURLPart,
    _LoginURL,
    _PowerControlURLPart,
    _PowerStationURLPart,
)

MOCK_INVERTER_SN = "GW0000SN000TEST1"
MOCK_POWER_STATION_ID = "12345678-1234-5678-9abc-123456789abc"
SUCCESS_MESSAGE = "操作成功"


def _login_payload(uid: str = "test-uid", token: str = "test-token") -> dict:
    """Return a realistic SEMS+ login response payload."""
    return {
        "hasError": False,
        "msg": SUCCESS_MESSAGE,
        "code": "0",
        "data": {
            "uid": uid,
            "timestamp": 1757355815062,
            "token": token,
            "client": "ios",
            "version": "",
            "language": "en",
        },
    }


def _station_payload() -> dict:
    """Return a realistic power-station-IDs response payload."""
    return {
        "hasError": False,
        "code": "0",
        "msg": SUCCESS_MESSAGE,
        "data": MOCK_POWER_STATION_ID,
    }


def _monitor_payload() -> dict:
    """Return a realistic monitor-detail response payload."""
    return {
        "hasError": False,
        "msg": SUCCESS_MESSAGE,
        "code": "0",
        "data": {
            "info": {
                "powerstation_id": MOCK_POWER_STATION_ID,
                "stationname": "Test Solar Farm",
                "address": "Test City, Test Country",
                "capacity": 3.2,
                "status": 1,
            },
            "kpi": {
                "pac": 589.0,
                "power": 8.9,
                "total_power": 18843.2,
                "currency": "CNY",
            },
            "inverter": [
                {
                    "sn": MOCK_INVERTER_SN,
                    "name": "Inverter 1",
                    "out_pac": 589.0,
                    "eday": 8.9,
                    "emonth": 76.8,
                    "etotal": 18843.2,
                    "status": 1,
                    "tempperature": 32.0,
                }
            ],
        },
    }


class TestSemsApiUnit:
    """Unit tests for the request flow, token handling, and error paths."""

    def setup_method(self):
        self.hass = Mock()
        self.username = "test_user"
        self.password = "test_password"
        self.api = SemsApi(self.hass, self.username, self.password)

    def test_init(self):
        """SemsApi stores the hass handle and credentials, no token yet."""
        assert self.api._hass is self.hass
        assert self.api._username == self.username
        assert self.api._password == self.password
        assert self.api._token is None

    @patch("custom_components.sems_cn.sems_api.requests.post")
    def test_make_http_request_success(self, mock_post):
        """A 2xx response with code 0 and data is returned as the parsed JSON."""
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"code": 0, "data": {"k": "v"}}
        response.raise_for_status.return_value = None
        mock_post.return_value = response

        result = self.api._make_http_request(
            "http://test.com",
            {"Content-Type": "application/json"},
            data='{"test": "data"}',
            operation_name="op",
        )

        assert result == {"code": 0, "data": {"k": "v"}}

    @patch("custom_components.sems_cn.sems_api.requests.post")
    def test_make_http_request_validation_failure(self, mock_post):
        """A non-zero response code is treated as a failure (returns None)."""
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"code": 1001, "msg": "Invalid credentials"}
        response.raise_for_status.return_value = None
        mock_post.return_value = response

        result = self.api._make_http_request(
            "http://test.com",
            {"Content-Type": "application/json"},
            operation_name="op",
        )
        assert result is None

    @patch("custom_components.sems_cn.sems_api.requests.post")
    def test_make_http_request_missing_data(self, mock_post):
        """A code 0 response without data is treated as a failure (returns None)."""
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"code": 0, "data": None}
        response.raise_for_status.return_value = None
        mock_post.return_value = response

        result = self.api._make_http_request(
            "http://test.com",
            {"Content-Type": "application/json"},
            operation_name="op",
        )
        assert result is None

    @patch("custom_components.sems_cn.sems_api.requests.post")
    def test_make_http_request_no_validation(self, mock_post):
        """With validate_code=False the response is returned as-is."""
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"code": 1001, "msg": "Error"}
        response.raise_for_status.return_value = None
        mock_post.return_value = response

        result = self.api._make_http_request(
            "http://test.com",
            {"Content-Type": "application/json"},
            operation_name="op",
            validate_code=False,
        )
        assert result == {"code": 1001, "msg": "Error"}

    @patch("custom_components.sems_cn.sems_api.requests.post")
    def test_make_http_request_network_error_propagates(self, mock_post):
        """A requests exception is re-raised so the coordinator can surface it."""
        mock_post.side_effect = requests.ConnectionError("Network error")

        with pytest.raises(requests.ConnectionError):
            self.api._make_http_request(
                "http://test.com",
                {"Content-Type": "application/json"},
                operation_name="op",
            )

    @patch.object(SemsApi, "_make_http_request")
    def test_get_login_token_success(self, mock_http):
        """getLoginToken returns the data field on a successful response."""
        mock_http.return_value = {"code": 0, "data": {"uid": "u", "token": "t"}}
        assert self.api.getLoginToken("u", "p") == {"uid": "u", "token": "t"}

    @patch.object(SemsApi, "_make_http_request")
    def test_get_login_token_returns_none_on_failure(self, mock_http):
        """getLoginToken returns None when the HTTP layer signals failure."""
        mock_http.return_value = None
        assert self.api.getLoginToken("u", "p") is None

    @patch.object(SemsApi, "_make_http_request")
    def test_get_login_token_swallows_request_exception(self, mock_http):
        """A request exception during login is logged and None is returned."""
        mock_http.side_effect = requests.RequestException("boom")
        assert self.api.getLoginToken("u", "p") is None

    def test_test_authentication_success(self):
        """A successful login makes test_authentication() return True and stash the token."""
        with patch.object(self.api, "getLoginToken") as login:
            login.return_value = {"token": "t"}
            assert self.api.test_authentication() is True
            assert self.api._token == {"token": "t"}

    def test_test_authentication_failure(self):
        """A failed login makes test_authentication() return False."""
        with patch.object(self.api, "getLoginToken") as login:
            login.return_value = None
            assert self.api.test_authentication() is False

    def test_test_authentication_exception(self):
        """An exception during login makes test_authentication() return False."""
        with patch.object(self.api, "getLoginToken") as login:
            login.side_effect = Exception("boom")
            assert self.api.test_authentication() is False

    @patch.object(SemsApi, "getLoginToken")
    @patch.object(SemsApi, "_make_http_request")
    def test_make_api_call_uses_existing_token(self, mock_http, mock_login):
        """With a valid token, _make_api_call skips re-login and returns data."""
        self.api._token = {"token": "t"}
        mock_http.return_value = {"code": 0, "data": {"ok": True}}

        result = self.api._make_api_call(
            "/v1/PowerStation/GetMonitorDetailByPowerstationId",
            data='{"powerStationId":"s"}',
            operation_name="getData API call",
        )

        assert result == {"ok": True}
        mock_login.assert_not_called()

    @patch.object(SemsApi, "getLoginToken")
    @patch.object(SemsApi, "_make_http_request")
    def test_make_api_call_refreshes_missing_token(self, mock_http, mock_login):
        """A None token triggers a fresh login before the API call."""
        self.api._token = None
        mock_login.return_value = {"token": "new"}
        mock_http.return_value = {"code": 0, "data": {"ok": True}}

        self.api._make_api_call(
            "/v1/PowerStation/GetMonitorDetailByPowerstationId",
            operation_name="getData API call",
        )

        mock_login.assert_called_once_with(self.username, self.password)

    @patch.object(SemsApi, "getLoginToken")
    def test_make_api_call_returns_none_when_login_fails(self, mock_login):
        """If login returns None, _make_api_call short-circuits and returns None."""
        self.api._token = None
        mock_login.return_value = None

        result = self.api._make_api_call(
            "/v1/PowerStation/GetMonitorDetailByPowerstationId",
            operation_name="getData API call",
        )

        assert result is None

    @patch.object(SemsApi, "getLoginToken")
    @patch.object(SemsApi, "_make_http_request")
    def test_make_api_call_retries_with_new_token_on_validation_failure(
        self, mock_http, mock_login
    ):
        """A None response triggers a token refresh and one more attempt."""
        self.api._token = {"token": "old"}
        mock_http.side_effect = [None, {"code": 0, "data": {"ok": True}}]
        mock_login.return_value = {"token": "new"}

        result = self.api._make_api_call(
            "/v1/PowerStation/GetMonitorDetailByPowerstationId",
            operation_name="getData API call",
            maxTokenRetries=2,
        )

        assert result == {"ok": True}
        assert mock_http.call_count == 2

    @patch.object(SemsApi, "getLoginToken")
    def test_make_api_call_raises_when_retries_exhausted(self, mock_login):
        """maxTokenRetries=0 means we cannot try, so OutOfRetries is raised."""
        self.api._token = None

        with pytest.raises(OutOfRetries):
            self.api._make_api_call(
                "/v1/PowerStation/GetMonitorDetailByPowerstationId",
                maxTokenRetries=0,
                operation_name="getData API call",
            )

    @patch.object(SemsApi, "_make_api_call")
    def test_get_power_station_ids_delegates(self, mock_call):
        """getPowerStationIds delegates to _make_api_call with the right endpoint."""
        mock_call.return_value = MOCK_POWER_STATION_ID
        assert self.api.getPowerStationIds() == MOCK_POWER_STATION_ID
        mock_call.assert_called_once_with(
            _GetPowerStationIdByOwnerURLPart,
            data=None,
            renewToken=False,
            maxTokenRetries=2,
            operation_name="getPowerStationIds API call",
        )

    @patch.object(SemsApi, "_make_api_call")
    def test_get_data_uses_v1_endpoint(self, mock_call):
        """getData posts the station ID to the v1 monitor endpoint."""
        mock_call.return_value = {"k": "v"}
        assert self.api.getData(MOCK_POWER_STATION_ID) == {"k": "v"}
        mock_call.assert_called_once_with(
            _PowerStationURLPart,
            data=f'{{"powerStationId":"{MOCK_POWER_STATION_ID}"}}',
            renewToken=False,
            maxTokenRetries=2,
            operation_name="getData API call",
        )

    @patch.object(SemsApi, "_make_api_call")
    def test_get_data_returns_empty_when_api_returns_none(self, mock_call):
        """A None result is normalized to an empty dict for safe downstream access."""
        mock_call.return_value = None
        assert self.api.getData(MOCK_POWER_STATION_ID) == {}

    @patch.object(SemsApi, "_make_control_api_call")
    def test_change_status_passes_through(self, mock_control):
        """change_status forwards to the control API and is silent on failure."""
        mock_control.return_value = True
        self.api.change_status("inv123", 1)
        mock_control.assert_called_once()

    @patch.object(SemsApi, "_make_control_api_call")
    def test_change_status_silent_on_failure(self, mock_control):
        """change_status does not raise even if the control API call fails."""
        mock_control.return_value = False
        self.api.change_status("inv123", 1)
        mock_control.assert_called_once()


class TestSemsApiIntegration:
    """End-to-end-ish tests that hit real CN API URL paths via ``requests_mock``."""

    def setup_method(self):
        self.username = "test_user"
        self.password = "test_password"
        self.api = SemsApi(None, self.username, self.password)

    def test_successful_login(self, requests_mock):
        """A well-formed CN login response yields a usable token dict."""
        requests_mock.post(_LoginURL, json=_login_payload())

        result = self.api.getLoginToken(self.username, self.password)

        assert result is not None
        assert result["uid"] == "test-uid"
        assert result["token"] == "test-token"

    def test_failed_login_invalid_credentials(self, requests_mock):
        """A code != 0 login response surfaces as None."""
        requests_mock.post(
            _LoginURL,
            json={"code": 1001, "msg": "Invalid credentials", "data": None},
        )

        assert self.api.getLoginToken(self.username, self.password) is None

    def test_login_network_error(self, requests_mock):
        """A connection error during login is swallowed and None is returned."""
        requests_mock.post(_LoginURL, exc=requests.ConnectionError("boom"))
        assert self.api.getLoginToken(self.username, self.password) is None

    def test_authentication_success(self, requests_mock):
        """test_authentication returns True on a successful login."""
        requests_mock.post(_LoginURL, json=_login_payload())
        assert self.api.test_authentication() is True

    def test_authentication_failure(self, requests_mock):
        """test_authentication returns False when login fails."""
        requests_mock.post(
            _LoginURL, json={"code": 1001, "msg": "Invalid credentials", "data": None}
        )
        assert self.api.test_authentication() is False

    def test_get_power_station_ids(self, requests_mock):
        """getPowerStationIds returns the power station ID from the CN API."""
        requests_mock.post(_LoginURL, json=_login_payload())
        requests_mock.post(
            f"{_APIURL.rstrip('/')}{_GetPowerStationIdByOwnerURLPart}",
            json=_station_payload(),
        )

        result = self.api.getPowerStationIds()
        assert result == MOCK_POWER_STATION_ID

    def test_get_data_returns_full_payload(self, requests_mock):
        """getData returns the full monitor-detail payload, including inverters."""
        requests_mock.post(_LoginURL, json=_login_payload())
        requests_mock.post(
            f"{_APIURL.rstrip('/')}{_PowerStationURLPart}",
            json=_monitor_payload(),
        )

        result = self.api.getData(MOCK_POWER_STATION_ID)

        assert result["info"]["powerstation_id"] == MOCK_POWER_STATION_ID
        assert result["kpi"]["pac"] == 589.0
        assert len(result["inverter"]) == 1
        assert result["inverter"][0]["sn"] == MOCK_INVERTER_SN
        assert result["inverter"][0]["out_pac"] == 589.0

    def test_get_data_returns_empty_on_login_failure(self, requests_mock):
        """getData returns an empty dict when the login itself fails."""
        requests_mock.post(
            _LoginURL, json={"code": 1001, "msg": "Invalid credentials", "data": None}
        )
        assert self.api.getData("station123") == {}

    def test_change_status_success(self, requests_mock):
        """change_status completes silently when the control API returns 200."""
        requests_mock.post(_LoginURL, json=_login_payload())
        requests_mock.post(
            f"{_APIURL.rstrip('/')}{_PowerControlURLPart}",
            json={"status": "success"},
            status_code=200,
        )

        # Should not raise
        self.api.change_status(MOCK_INVERTER_SN, 1)

    def test_change_status_raises_after_exhausting_retries(self, requests_mock):
        """A persistent HTTP error on the control API surfaces as OutOfRetries."""
        requests_mock.post(_LoginURL, json=_login_payload())
        requests_mock.post(
            f"{_APIURL.rstrip('/')}{_PowerControlURLPart}", status_code=401
        )

        with pytest.raises(OutOfRetries):
            self.api.change_status(MOCK_INVERTER_SN, 1)

    def test_api_call_retries_with_new_token(self, requests_mock):
        """A stale-token failure is followed by a refresh and a successful retry."""
        requests_mock.post(
            _LoginURL,
            [
                {"json": _login_payload(uid="u1", token="old")},
                {"json": _login_payload(uid="u1", token="new")},
            ],
        )
        requests_mock.post(
            f"{_APIURL.rstrip('/')}{_GetPowerStationIdByOwnerURLPart}",
            [
                {"json": {"code": 1002, "msg": "Token expired", "data": None}},
                {"json": _station_payload()},
            ],
        )

        result = self.api.getPowerStationIds()
        assert result == MOCK_POWER_STATION_ID


class TestOutOfRetries:
    """Smoke test for the OutOfRetries exception class."""

    def test_out_of_retries_is_an_exception(self):
        exception = OutOfRetries("Test message")
        assert str(exception) == "Test message"
        assert isinstance(exception, Exception)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
