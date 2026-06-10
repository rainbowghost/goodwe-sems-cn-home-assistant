"""SEMS+ plant API client for the CN region.

Reverse-engineered from the SEMS+ web frontend's network traffic. Algorithm
documented at ``E:/MyCode/sems-plus-api.md`` (and the user's session captures
at ``E:/MyCode/semsplus.txt`` / ``E:/Code/semsplusweb.txt``).

Flow:
    1. POST cross-login at ``semsplus.goodwe.com`` with
       ``isChinese:true, isLocal:true`` → returns a token whose ``data.api``
       field points at the regional CN gateway (``hz-gateway.sems.com.cn``).
    2. POST /sems-plant/api/app/v2/stations/page  → station list
       (use ``simple-query`` instead when the user agent is web).
    3. GET  /sems-plant/api/stations/device/all-status?stationId=… → SN list
    4. GET  /sems-plant/api/equipments/{SN}/telecounting?… → power & history
    5. GET  /sems-plant/api/equipments/{SN}/telemetry?…     → live data
    6. POST /PowerStation/SaveRemoteControlInverter → inverter on/off

Every plant call carries a freshly-computed ``x-signature =
base64(sha256(now_ms@uid@token) + "@" + now_ms)`` header — same
anti-replay scheme upstream uses.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import time
from typing import Any

import requests
from homeassistant import exceptions
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
_LOGIN_URL = "https://semsplus.goodwe.com/web/sems/sems-user/api/v1/auth/cross-login"
_STATIONS_PATH_ANDROID = "/sems-plant/api/app/v2/stations/page"
_STATIONS_PATH_WEB = "/sems-plant/api/stations/simple-query"
_DEVICE_PATH = "/sems-plant/api/stations/device/all-status"
_TELECOUNTING_PATH = "/sems-plant/api/equipments/{sn}/telecounting"
_TELEMETRY_PATH = "/sems-plant/api/equipments/{sn}/telemetry"
_POWER_CONTROL_PATH = "/PowerStation/SaveRemoteControlInverter"

_REQUEST_TIMEOUT = 30  # seconds

# Login defaults for the empty token header (uid/timestamp/token are
# zero/empty when no session exists yet).
_LOGIN_TOKEN_ANDROID = {
    "uid": "",
    "timestamp": 0,
    "token": "",
    "client": "semsPlusAndroid",
    "version": "2.5.2",
    "language": "zh-CN",
}

_APP_VERSION = "2.5.3"  # current GoodWe mobile/web app version

_USER_AGENT_ANDROID = "okhttp/4.9.3"

# ---------------------------------------------------------------------------
# Rate limiting (from upstream v10.x + observed CN behavior)
# ---------------------------------------------------------------------------
_SUCCESS_CODES = {"0", 0, "00000"}
_RATE_LIMIT_CODE = "GY0429"               # returned by SEMS+ globally
_NO_ACCESS_CODE = "100025"               # observed on CN plant endpoints
_RATE_LIMIT_RETRY_AFTER = 300            # seconds
_MAX_TOKEN_RETRIES = 2


def _md5_then_base64(text: str) -> str:
    """SEMS+ password encoding: base64(md5_hex_string(plain_password))."""
    md5_hex = hashlib.md5(text.encode("utf-8")).hexdigest()
    return base64.b64encode(md5_hex.encode("utf-8")).decode("ascii")


def _password_for_login(plain: str) -> str:
    """Plaintext password → ``pwd`` field for cross-login."""
    return _md5_then_base64(plain)


def _encode_signature(token: dict[str, Any]) -> str:
    """Reverse-engineered SEMS+ web ``encodeSignature()``.

    Same algorithm for login + every plant call:
        r = current unix ms
        a = token.uid  (empty string for login)
        i = token.token (empty string for login)
        sig = base64(sha256(r@a@i) + "@" + r)
    """
    r = time.time_ns() // 1_000_000
    a = token.get("uid", "")
    i = token.get("token", "")
    h = hashlib.sha256(f"{r}@{a}@{i}".encode()).hexdigest()
    return base64.b64encode(f"{h}@{r}".encode()).decode()


def _fresh_traceid() -> str:
    """Per-request trace id. Server uses it to correlate calls; any
    unique hex string works."""
    import uuid
    return str(uuid.uuid4()).replace("-", "")


def _build_headers(
    token: dict[str, Any],
    *,
    with_content_type: bool = False,
    traceid: str | None = None,
) -> dict[str, str]:
    """Headers used for every authenticated plant call.

    Login itself also uses these (with the empty ``_LOGIN_TOKEN_*`` token
    dict), plus ``Content-Type`` when posting a body.
    """
    h = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
        "User-Agent": _USER_AGENT_ANDROID,
        "currentlang": "zh-CN",
        "neutral": "0",
        "appversion": _APP_VERSION,
        "traceid": traceid or _fresh_traceid(),
        "token": json.dumps(token, separators=(",", ":")),
        "x-signature": _encode_signature(token),
    }
    if with_content_type:
        h["Content-Type"] = "application/json"
    return h


def _redact_for_log(value: Any) -> Any:
    """Best-effort log redaction for tokens / passwords. Mirrors the helper
    upstream ships so debug logs don't leak credentials."""
    if isinstance(value, str):
        if "token" in value.lower() or len(value) > 32:
            return "<redacted>"
        return value
    if isinstance(value, dict):
        return {k: _redact_for_log(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_for_log(v) for v in value]
    return value


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class OutOfRetries(exceptions.HomeAssistantError):
    """Error to indicate too many failed token retries."""


class SemsRateLimitedError(exceptions.HomeAssistantError):
    """Error to indicate the SEMS API requested a backoff.

    Raised on either ``GY0429`` (global rate limit) or ``100025`` (CN
    plant endpoint: token expired or scope rejected).
    """

    def __init__(self, retry_after: int, message: str = "SEMS API rate limited"):
        super().__init__(message)
        self.retry_after = retry_after


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class SemsApi:
    """Interface to the SEMS+ plant API for the CN region."""

    def __init__(self, hass: HomeAssistant, username: str, password: str) -> None:
        self._hass = hass
        self._username = username
        self._password = password
        self._token: dict[str, Any] | None = None

    # ----- public ------------------------------------------------------------

    def test_authentication(self) -> bool:
        """Login probe used by the config flow."""
        try:
            self._token = self._login()
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            _LOGGER.exception("SEMS Authentication exception: %s", exc)
            return False
        return self._token is not None

    def get_stations(self) -> list[dict[str, Any]] | None:
        """Fetch the user's stations and return their dataList."""
        api_base = self._ensure_api_base()
        if api_base is None:
            return None
        path = _STATIONS_PATH_ANDROID
        body = {"current": 1, "size": 100}
        resp = self._request("POST", api_base + path, json_body=body)
        if resp is None:
            return None
        return (resp.get("data") or {}).get("dataList") or []

    def get_devices(self, station_id: str) -> list[dict[str, Any]] | None:
        """Return the deviceDetailList for a station."""
        api_base = self._ensure_api_base()
        if api_base is None:
            return None
        resp = self._request(
            "GET",
            api_base + _DEVICE_PATH,
            params={"stationId": station_id},
        )
        if resp is None:
            return None
        return (resp.get("data") or {}).get("deviceDetailList") or []

    def get_telecounting(self, sn: str, station_id: str) -> list[dict[str, Any]] | None:
        """Return the factor groups from telecounting for one inverter."""
        api_base = self._ensure_api_base()
        if api_base is None:
            return None
        path = _TELECOUNTING_PATH.format(sn=sn)
        resp = self._request(
            "GET",
            api_base + path,
            params={"deviceType": "INVERTER", "pwId": station_id},
        )
        if resp is None:
            return None
        return resp.get("data") or []

    def get_telemetry(self, sn: str, station_id: str) -> list[dict[str, Any]] | None:
        """Return the factor groups from telemetry for one inverter."""
        api_base = self._ensure_api_base()
        if api_base is None:
            return None
        path = _TELEMETRY_PATH.format(sn=sn)
        resp = self._request(
            "GET",
            api_base + path,
            params={"deviceType": "INVERTER", "pwId": station_id},
        )
        if resp is None:
            return None
        return resp.get("data") or []

    def change_status(self, inverter_sn: str, status: str | int) -> bool:
        """Toggle an inverter. ``status="2"``=off, ``"4"``=on.

        Uses the new /PowerStation/SaveRemoteControlInverter endpoint
        (same path as upstream / legacy).
        """
        api_base = self._ensure_api_base()
        if api_base is None:
            return False
        resp = self._request(
            "POST",
            api_base + _POWER_CONTROL_PATH,
            json_body={
                "InverterSN": inverter_sn,
                "InverterStatusSettingMark": "1",
                "InverterStatus": str(status),
            },
            validate_code=False,
        )
        return resp is not None

    # ----- token lifecycle ---------------------------------------------------

    def _ensure_api_base(self) -> str | None:
        """Return the API base from the current token, or None if not logged in."""
        if self._token is None:
            self._token = self._login()
        if self._token is None:
            return None
        return self._token.get("api")

    def _login(self) -> dict[str, Any] | None:
        """POST cross-login. Returns the response token or None."""
        headers = _build_headers(_LOGIN_TOKEN_ANDROID, with_content_type=True)
        payload = {
            "account": self._username,
            "pwd": _password_for_login(self._password),
            "agreement": 1,
            "isLocal": True,
            "isChinese": True,
        }
        resp = self._post(_LOGIN_URL, headers=headers, json_body=payload)
        if resp is None:
            return None
        if str(resp.get("code")) not in {str(c) for c in _SUCCESS_CODES}:
            _LOGGER.error(
                "SEMS login failed: code=%s msg=%s",
                resp.get("code"),
                resp.get("msg"),
            )
            return None
        token = resp.get("data")
        if not isinstance(token, dict):
            _LOGGER.error("SEMS login: missing data dict in response")
            return None
        _LOGGER.debug("SEMS login OK, token=%s", _redact_for_log(token))
        return token

    # ----- HTTP plumbing -----------------------------------------------------

    def _post(self, url: str, *, headers: dict, json_body: dict | None = None) -> dict | None:
        return self._request("POST", url, headers=headers, json_body=json_body)

    def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict | None = None,
        json_body: dict | None = None,
        params: dict | None = None,
        validate_code: bool = True,
    ) -> dict | None:
        """Single HTTP call with rate-limit detection and C0602 recovery.

        If ``headers`` is omitted, plant headers are auto-built from
        ``self._token`` (which must already be set via ``_login`` or a
        prior plant call). The login call itself passes its own headers
        (the empty login token), so this method is the right place to
        decide whether C0602 means "credentials wrong" (login) or
        "stale token" (plant call).

        Recovery: on a C0602 response with a cached ``self._token``,
        the token is invalidated, a fresh login is performed, and the
        request is retried once. On any other error code the call is
        not retried.
        """
        if headers is None:
            if not isinstance(self._token, dict):
                _LOGGER.error(
                    "SEMS %s %s: no token available for plant headers", method, url
                )
                return None
            headers = _build_headers(self._token)

        body = self._do_http(method, url, headers=headers, json_body=json_body, params=params)
        if body is None:
            return None

        # Rate limit: GY0429 (global) or 100025 (CN plant: token expired
        # or scope rejected). Propagate so the coordinator can back off.
        if str(body.get("code")) in (_RATE_LIMIT_CODE, _NO_ACCESS_CODE):
            _LOGGER.warning(
                "SEMS %s %s: rate-limited (code=%s)",
                method, url, body.get("code"),
            )
            raise SemsRateLimitedError(retry_after=_RATE_LIMIT_RETRY_AFTER)

        # C0602 on a non-login call: cached token is bad. Invalidate,
        # re-login, retry once. The login POST itself uses explicit
        # headers (no cached token), so this branch can't fire for it.
        if body.get("code") == "C0602" and isinstance(self._token, dict) and headers is not None:
            _LOGGER.info(
                "SEMS %s %s returned C0602 with cached token; re-logging in and retrying",
                method, url,
            )
            self._token = None
            new_token = self._login()
            if new_token is not None:
                retry_headers = _build_headers(
                    new_token,
                    with_content_type=json_body is not None,
                )
                body = self._do_http(
                    method, url, headers=retry_headers,
                    json_body=json_body, params=params,
                )
                if body is None:
                    return None
                if str(body.get("code")) in (_RATE_LIMIT_CODE, _NO_ACCESS_CODE):
                    raise SemsRateLimitedError(retry_after=_RATE_LIMIT_RETRY_AFTER)
            else:
                _LOGGER.warning("Re-login after C0602 failed; giving up")

        if validate_code and str(body.get("code")) not in {str(c) for c in _SUCCESS_CODES}:
            _LOGGER.error(
                "SEMS %s %s returned code=%s msg=%s",
                method, url, body.get("code"), body.get("msg"),
            )
            return None

        return body

    def _do_http(
        self,
        method: str,
        url: str,
        *,
        headers: dict,
        json_body: dict | None,
        params: dict | None,
    ) -> dict | None:
        """Pure HTTP call. Returns parsed JSON body or None on parse failure.

        Network exceptions propagate so the coordinator's UpdateFailed
        machinery can surface them.
        """
        try:
            _LOGGER.debug("SEMS %s %s", method, url)
            r = requests.request(
                method,
                url,
                headers=headers,
                json=json_body,
                params=params,
                timeout=_REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            _LOGGER.error("SEMS %s %s failed: %s", method, url, exc)
            raise

        try:
            return r.json()
        except ValueError:
            _LOGGER.error(
                "SEMS %s %s: non-JSON response (HTTP %s)", method, url, r.status_code
            )
            return None
