# ServiceCatalogue Test Documentation

This document walks through the test suite for the [`ServiceCatalogue`](../../src/hmpps/clients/service_catalogue.py) class, defined in [`tests/clients/test_service_catalogue.py`](../../tests/clients/test_service_catalogue.py).

All tests use **mocked HTTP sessions** — no real API calls are made. The mock session is injected via the `session=` parameter on `ServiceCatalogue`, replacing the real `requests.Session`.

---

## How the Tests Work

### Test Fixtures (shared setup)

| Fixture | Purpose |
|---|---|
| `mock_session` | A `Mock(spec=requests.Session)` — every test that touches the network uses this instead of a real HTTP session. |
| `sc_url` / `sc_key` | Hardcoded test URL and API key strings, kept as separate fixtures so they can be referenced in assertions. |
| `service_catalogue` | A fully constructed `ServiceCatalogue` instance wired to `mock_session`. The `head` call made by `test_connection()` during `__init__` is pre-mocked to return 200. |
| `mock_job` | A `Mock(spec=Jobs)` for testing `update_scheduled_job`. |
| Response fixtures (`single_page_response`, `multi_page_response_page1/2/3`, `single_record_response`) | Canned JSON payloads that mimic the Strapi pagination structure the real API returns. |

### General test patterns

- **Happy path** — call the method with valid inputs, assert correct return value.
- **Error status codes** — parameterised with `@pytest.mark.parametrize` across typical failure codes (400, 404, 500, etc.), assert the method handles them gracefully (returns `False`, `None`, or `[]`).
- **Exception handling** — simulate `ConnectionError`, `Timeout`, or `HTTPError` on the mock session, assert the method doesn't crash.
- **Timeout propagation** — assert that `self.timeout` is passed through to every underlying `session.get/put/post/delete/head` call.
- **Ampersand encoding** — where user input could contain `&`, assert it's encoded as `&amp;` in the query string to avoid breaking Strapi filters.

---

## Tests Grouped by Function

### 1. Helper Functions (module-level)

**Source:** [`_set_page()`](../../src/hmpps/clients/service_catalogue.py) and [`_basename()`](../../src/hmpps/clients/service_catalogue.py)

#### `TestSetPage`
| Test | What it checks |
|---|---|
| `test_set_page_various_urls` (parameterised, 4 cases) | Adds/overwrites `pagination[page]` on URLs with no params, existing params, existing pagination, and multiple params. |
| `test_set_page_preserves_other_params` | Other query parameters survive after setting the page. |

#### `TestBasename`
| Test | What it checks |
|---|---|
| `test_basename_various_urls` (parameterised, 4 cases) | Strips query string from URL; handles empty string and complex queries. |

---

### 2. `__init__`

**Source:** [`ServiceCatalogue.__init__()`](../../src/hmpps/clients/service_catalogue.py)

#### `TestServiceCatalogueInit`
| Test | What it checks |
|---|---|
| `test_init_with_valid_params` | `url`, `key`, `filter`, `timeout`, `connection_ok`, and `Authorization` header are all set correctly. |
| `test_init_with_filter` | The `filter` string appears in `components_get` query string. |
| `test_init_with_custom_timeout` | A non-default timeout (30) is stored on the instance. |
| `test_init_connection_failure` | When `head()` raises `ConnectionError`, `connection_ok` is `False`. |
| `test_init_creates_default_session_if_not_provided` | When no `session=` is passed, `requests.Session()` is called and stored. |

---

### 3. `test_connection()`

**Source:** [`ServiceCatalogue.test_connection()`](../../src/hmpps/clients/service_catalogue.py)

#### `TestTestConnection`
| Test | What it checks |
|---|---|
| `test_connection_success` | Returns `True` on 200 response; `head()` is called. |
| `test_connection_timeout` | Returns `False` when `Timeout` is raised. |
| `test_connection_refused` | Returns `False` when `ConnectionError` is raised. |
| `test_connection_uses_correct_timeout` | The configured `timeout` value is passed to `session.head()`. |

---

### 4. `_request_json_with_retry()` (internal)

**Source:** [`ServiceCatalogue._request_json_with_retry()`](../../src/hmpps/clients/service_catalogue.py)

#### `TestRequestJsonWithRetry`
| Test | What it checks |
|---|---|
| `test_success_first_attempt` | Returns JSON on first try; only 1 `get()` call made. |
| `test_success_after_retry` | First request fails (HTTPError), second succeeds; result is from the successful attempt. |
| `test_exhausted_retries_raises_runtime_error` | After `max_retries` failures, raises `RuntimeError` with "Exceeded retries" message. |
| `test_non_2xx_status_triggers_retry` (parameterised, 7 status codes) | Each of 400/401/403/404/500/502/503 triggers retry via `raise_for_status()`. |
| `test_invalid_json_triggers_retry` | A 200 response with unparseable JSON body triggers retry. |
| `test_exponential_backoff` | `time.sleep()` is called with 0.5s, 1.0s, 2.0s between retries. |

---

### 5. `get_with_retry()`

**Source:** [`ServiceCatalogue.get_with_retry()`](../../src/hmpps/clients/service_catalogue.py)

#### `TestGetWithRetry`
| Test | What it checks |
|---|---|
| `test_single_page_result` | Returns both records from a single-page response. |
| `test_multi_page_aggregation` | Aggregates data across 3 pages (5 total records). |
| `test_empty_data_array` | Returns `[]` when the API returns an empty `data` array. |
| `test_preserves_existing_query_params` | Filters in the URI (e.g. `?filters[name]=test`) are preserved in the outgoing request URL. |
| `test_failure_on_first_page_returns_empty` | If the first page request raises `RuntimeError`, returns `[]`. |
| `test_failure_on_subsequent_page_continues` | If page 2 fails, data from page 1 is still returned. |

---

### 6. `get_single_record_with_retry()`

**Source:** [`ServiceCatalogue.get_single_record_with_retry()`](../../src/hmpps/clients/service_catalogue.py)

#### `TestGetSingleRecordWithRetry`
| Test | What it checks |
|---|---|
| `test_returns_dict_data` | Returns the `data` dict when it's a proper dict. |
| `test_data_not_dict_returns_empty` | Returns `{}` when `data` is unexpectedly a list. |
| `test_request_failure_returns_empty` | Returns `{}` when the request raises `RuntimeError`. |

---

### 7. `get_all_records()`

**Source:** [`ServiceCatalogue.get_all_records()`](../../src/hmpps/clients/service_catalogue.py)

#### `TestGetAllRecords`
| Test | What it checks |
|---|---|
| `test_delegates_to_get_with_retry` | Calls `get_with_retry(table)` and returns its result. |

---

### 8. `get_record()`

**Source:** [`ServiceCatalogue.get_record()`](../../src/hmpps/clients/service_catalogue.py)

#### `TestGetRecord`
| Test | What it checks |
|---|---|
| `test_constructs_filter_correctly` (parameterised, 2 cases) | Uses `?filters` when the table has no query params, `&filters` when it already has `?`. |
| `test_record_found` | Returns the first matching record. |
| `test_record_not_found_returns_none` | Returns `None` when `get_with_retry` returns `[]`. |
| `test_ampersand_encoding` | `&` in the parameter value is encoded as `&amp;`. |

---

### 9. `get_filtered_records()`

**Source:** [`ServiceCatalogue.get_filtered_records()`](../../src/hmpps/clients/service_catalogue.py)

#### `TestGetFilteredRecords`
| Test | What it checks |
|---|---|
| `test_records_found` | Returns the `data` list on 200 with results. |
| `test_no_records_found` | Returns `None` when `data` is empty. |
| `test_non_200_response` (parameterised, 3 status codes) | Returns `None` for 400/404/500. |
| `test_request_exception` | Returns `None` when `ConnectionError` is raised. |
| `test_uses_configured_timeout` | `timeout=self.timeout` is passed to `session.get()`. |

---

### 10. `get_record_by_id()`

**Source:** [`ServiceCatalogue.get_record_by_id()`](../../src/hmpps/clients/service_catalogue.py)

#### `TestGetRecordById`
| Test | What it checks |
|---|---|
| `test_record_found` | Returns the record dict from `get_single_record_with_retry`. |
| `test_record_not_found` | Returns `None` when the underlying call returns `{}`. |

---

### 11. `update()`

**Source:** [`ServiceCatalogue.update()`](../../src/hmpps/clients/service_catalogue.py)

#### `TestUpdate`
| Test | What it checks |
|---|---|
| `test_successful_update` | Returns `True` on 200; payload is wrapped in `{'data': ...}`. |
| `test_non_200_response` (parameterised, 3 status codes) | Returns `False` for 400/404/500. |
| `test_request_exception` | Returns `False` when `ConnectionError` is raised. |
| `test_uses_configured_timeout` | `timeout=self.timeout` is passed to `session.put()`. |

---

### 12. `add()`

**Source:** [`ServiceCatalogue.add()`](../../src/hmpps/clients/service_catalogue.py)

#### `TestAdd`
| Test | What it checks |
|---|---|
| `test_successful_add` | Returns the parsed JSON body on 201. |
| `test_successful_add_with_team_name` | Handles the `team_name` field path in the success log message without error. |
| `test_non_201_response` (parameterised, 3 status codes) | Returns `False` for 400/409/500. |
| `test_request_exception` | Returns `False` when `ConnectionError` is raised. |
| `test_uses_configured_timeout` | `timeout=self.timeout` is passed to `session.post()`. |

---

### 13. `delete()`

**Source:** [`ServiceCatalogue.delete()`](../../src/hmpps/clients/service_catalogue.py)

#### `TestDelete`
| Test | What it checks |
|---|---|
| `test_successful_delete` (parameterised, 200 and 204) | Returns `True` for both success status codes. |
| `test_non_2xx_response` (parameterised, 3 status codes) | Returns `False` for 400/404/500. |
| `test_request_exception` | Returns `False` when `ConnectionError` is raised. |
| `test_uses_configured_timeout` | `timeout=self.timeout` is passed to `session.delete()`. |

---

### 14. `unpublish()`

**Source:** [`ServiceCatalogue.unpublish()`](../../src/hmpps/clients/service_catalogue.py)

#### `TestUnpublish`
| Test | What it checks |
|---|---|
| `test_successful_unpublish` | Returns `True`; payload is `{'data': {'publishedAt': None}}`. |
| `test_non_200_response` | Returns `False` for 400. |
| `test_request_exception` | Returns `False` when `ConnectionError` is raised. |
| `test_uses_configured_timeout` | `timeout=self.timeout` is passed to `session.put()`. |

---

### 15. `get_id()`

**Source:** [`ServiceCatalogue.get_id()`](../../src/hmpps/clients/service_catalogue.py)

#### `TestGetId`
| Test | What it checks |
|---|---|
| `test_id_found` | Returns the `documentId` string from the first matching record. |
| `test_no_records_found` | Returns `None` when no records match. |
| `test_record_missing_document_id` | Returns `None` when the record exists but has no `documentId` key. |
| `test_ampersand_encoding` | `&` in the match string is encoded as `&amp;`. |

---

### 16. `get_component_env_id()`

**Source:** [`ServiceCatalogue.get_component_env_id()`](../../src/hmpps/clients/service_catalogue.py)

#### `TestGetComponentEnvId`
| Test | What it checks |
|---|---|
| `test_env_found` | Returns the correct `documentId` for the named environment. |
| `test_env_not_found` | Returns `None` when the environment name doesn't match any entry. |
| `test_empty_envs_list` | Returns `None` when `envs` is `[]`. |
| `test_missing_envs_key` | Returns `None` when the component dict has no `envs` key at all. |

---

### 17. `find_all_teams_ref_in_sc()`

**Source:** [`ServiceCatalogue.find_all_teams_ref_in_sc()`](../../src/hmpps/clients/service_catalogue.py)

#### `TestFindAllTeamsRefInSc`
| Test | What it checks |
|---|---|
| `test_aggregates_all_team_types` | Collects teams from `_write`, `_admin`, and `_maintain` fields across components; deduplicates. |
| `test_handles_none_team_lists` | Treats `None` team lists as empty (doesn't crash). |
| `test_empty_components_list` | Returns empty `set()` when there are no components. |

---

### 18. `update_scheduled_job()`

**Source:** [`ServiceCatalogue.update_scheduled_job()`](../../src/hmpps/clients/service_catalogue.py)

#### `TestUpdateScheduledJob`
| Test | What it checks |
|---|---|
| `test_successful_update_succeeded_status` | Sets `last_successful_run` and `result='Succeeded'` in the update payload. |
| `test_successful_update_failed_status` | Does **not** set `last_successful_run`; includes `error_details` from the job context. |
| `test_job_not_found` | Returns `False` when `get_record` returns `None`. |
| `test_update_fails` | Returns `False` when `update()` raises an exception. |
| `test_uses_global_job_when_no_context_provided` | Falls back to the module-level `job` singleton when no `job_context` is passed. |

---

## Potential Gaps & Missing Tests

The following are areas where the current tests could be extended to catch more breakages:

### Constructor / Environment Variables
| Gap | Risk |
|---|---|
| No test for `os.getenv` fallback | If someone removes the `or os.getenv(...)` fallback for `url`, `key`, or `filter`, existing consumers that rely on environment variables would break silently. A test that patches `os.getenv` and constructs `ServiceCatalogue()` with no arguments would catch this. |

### `_request_json_with_retry()`
| Gap | Risk |
|---|---|
| No test for `timeout` propagation | Unlike the CRUD methods, there's no explicit assertion that `self.timeout` is passed to `session.get()` within this method. Currently covered implicitly, but an explicit test would guard against regression. |

### `get_with_retry()`
| Gap | Risk |
|---|---|
| No test for URL construction | No assertion that the base URL is constructed as `{self.url}/v1/{uri}`. A change to this pattern would silently break all API calls. |

### `get_record()`
| Gap | Risk |
|---|---|
| No test for multiple matching records | Only tests the case where exactly 1 record is returned. If the filtering returns multiple records, the method always returns `json_data[0]` — a test asserting this behaviour would document the intent. |

### `get_filtered_records()`
| Gap | Risk |
|---|---|
| No test for ampersand encoding | Unlike `get_record` and `get_id`, there's no test asserting `&` → `&amp;` encoding in `get_filtered_records`. |
| No test for URL construction | No assertion that the URL is constructed correctly with the filter parameters. |

### `update()`
| Gap | Risk |
|---|---|
| No test for correct URL construction | No assertion that the PUT goes to `{url}/v1/{table}/{element_id}`. |

### `add()`
| Gap | Risk |
|---|---|
| No test that data missing both `name` and `team_name` raises `KeyError` | The success log branch does `data["team_name"] if "team_name" in data else data["name"]`. If neither key exists, this will raise `KeyError` after a successful 201. Currently untested. |
| No test for correct URL construction | No assertion that the POST goes to `{url}/v1/{table}`. |

### `delete()`
| Gap | Risk |
|---|---|
| No test for correct URL construction | No assertion that the DELETE goes to `{url}/v1/{table}/{element_id}`. |

### `unpublish()`
| Gap | Risk |
|---|---|
| Only tests one error status code (400) | Unlike `update` and `delete` which test multiple status codes via parameterisation, `unpublish` only checks 400. Adding 404/500 would be more robust. |

### `update_scheduled_job()`
| Gap | Risk |
|---|---|
| No test for missing `documentId` on the job record | The method checks `if not job_id` and returns `False`, but there's no test covering this branch. |
| No test for `job_name` fallback to `'unknown'` | If `job_ctx.name` is empty/falsy, it falls back to `'unknown'`. This path is untested. |

---

## Running the Tests

```bash
# Run just the ServiceCatalogue tests
uv run pytest tests/clients/test_service_catalogue.py -v
```

### Coverage (optional)

Coverage analysis shows which lines of source code are exercised by the tests and which are not. This requires the `pytest-cov` package (already in `dev` dependencies):

```bash
# Run tests with a coverage report — uncovered line numbers are listed in the "Missing" column
# Note: use the dotted module path without the "src." prefix, because pyproject.toml
# sets pythonpath = "src", so Python sees the module as hmpps.clients.service_catalogue
uv run pytest tests/clients/test_service_catalogue.py --cov=hmpps.clients.service_catalogue --cov-report=term-missing
```
