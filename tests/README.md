# SEMS CN API Tests

Tests for the GoodWe SEMS CN API module.

## Test Files

- `test_sems_api.py` - The single consolidated test suite, split into:
  - `TestSemsApiUnit` — `unittest.mock`-based unit tests for the request flow,
    token handling, and error paths.
  - `TestSemsApiIntegration` — `requests_mock`-based tests that hit the real
    CN API URL paths (`gopsapi.sems.com.cn`).
  - `TestOutOfRetries` — smoke test for the `OutOfRetries` exception.
- `test_sensor_entities.py` - Home Assistant entity tests (config entry + entity registry)
- `fixtures.py` - Anonymized SEMS API response data for test fixtures
- `test-data/` - Larger JSON fixtures captured from real SEMS API responses
- `__init__.py` - Package initialization for tests
- `requirements.txt` - Test dependencies

## Running Tests

To run all tests:

```bash
pytest tests/ -v
```

If you are running these tests inside the Home Assistant core repository
workspace (where `/workspaces/home-assistant/pyproject.toml` exists), pytest
may try to load Home Assistant's own `tests/conftest.py` and fail. In that
case, run with `--confcutdir`:

```bash
pytest config/goodwe-sems-cn-home-assistant/tests/ -v \
  --confcutdir=config/goodwe-sems-cn-home-assistant
```

To run a specific test file:

```bash
pytest tests/test_sems_api.py -v
```

To run a specific test class:

```bash
pytest tests/test_sems_api.py::TestSemsApiIntegration -v
```

To run a specific test:

```bash
pytest tests/test_sems_api.py::TestSemsApiIntegration::test_successful_login -v
```

## Test Coverage

The test suite covers:

### Authentication
- Successful login with valid credentials
- Failed login with invalid credentials
- Network errors during login
- Authentication test success/failure

### Data Retrieval
- Get power station IDs successfully
- Get monitoring data successfully with real JSON structure
- Handle failures gracefully (return empty data)

### Control Commands
- Successful inverter status change
- HTTP error handling with retry mechanism

### Retry Logic
- Token refresh and retry on expired tokens
- Maximum retry limits with `OutOfRetries` exception

### Error Handling
- Network connection errors
- HTTP status code errors
- API response validation
- Token expiration handling

## Test Architecture

The tests use two complementary strategies:

- **`unittest.mock`** for fast unit tests that don't touch the network — these
  verify the request flow, validation, and error handling.
- **`requests-mock`** for integration tests that exercise the actual endpoint
  URLs and payload shapes used by the China-region SEMS+ API at
  `gopsapi.sems.com.cn`.

Each integration test follows the pattern:
1. Setup mock responses for login and API calls using anonymized SEMS+ JSON structures
2. Execute the API method under test
3. Assert expected results or exceptions

## Test Data

The test suite uses anonymized API response structures based on real SEMS+ API
data (Chinese region). All personally identifiable information has been
replaced with neutral placeholders.

This ensures tests validate against the actual API response format while
protecting user privacy.

## Dependencies

See `requirements.txt`:

- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `requests-mock` - HTTP request mocking
- `requests` - HTTP library (tested dependency)
- `pytest-homeassistant-custom-component` - Home Assistant test fixtures
