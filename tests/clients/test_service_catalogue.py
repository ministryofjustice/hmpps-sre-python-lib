"""
Comprehensive tests for the ServiceCatalogue client.

This module tests all public methods of the ServiceCatalogue class with
mocking to avoid real API calls. Tests are organized by function and use
parameterization where appropriate for thorough coverage.
"""

import pytest
import requests
from unittest.mock import Mock, patch, call
from requests.exceptions import ConnectionError, Timeout, HTTPError

from src.hmpps.clients.service_catalogue import (
  ServiceCatalogue,
  _set_page,
  _basename,
)
from src.hmpps.services.job_log_handling import Jobs


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_session():
  """Create a mock requests session."""
  return Mock(spec=requests.Session)


@pytest.fixture
def sc_params():
  """Standard ServiceCatalogue params for testing."""
  return {
    'url': 'https://test-sc.example.com',
    'key': 'test-api-key-12345',
    'filter': '',
  }


@pytest.fixture
def sc_params_with_filter():
  """ServiceCatalogue params with a filter."""
  return {
    'url': 'https://test-sc.example.com',
    'key': 'test-api-key-12345',
    'filter': '&filters[name][$contains]=test',
  }


@pytest.fixture
def sc_params_with_timeout():
  """ServiceCatalogue params with custom timeout."""
  return {
    'url': 'https://test-sc.example.com',
    'key': 'test-api-key-12345',
    'timeout': 30,
  }


@pytest.fixture
def service_catalogue(sc_params, mock_session):
  """Create a ServiceCatalogue instance with mocked session."""
  # Mock the head call for test_connection in __init__
  mock_response = Mock()
  mock_response.status_code = 200
  mock_session.head.return_value = mock_response
  return ServiceCatalogue(sc_params, session=mock_session)


@pytest.fixture
def mock_job():
  """Create a mock job context for testing update_scheduled_job."""
  mock = Mock(spec=Jobs)
  mock.name = 'test-scheduled-job'
  mock.error_messages = []
  return mock


# =============================================================================
# Sample Response Data Fixtures
# =============================================================================


@pytest.fixture
def single_page_response():
  """Sample single page API response."""
  return {
    'data': [
      {'id': 1, 'documentId': 'doc-1', 'name': 'component-1'},
      {'id': 2, 'documentId': 'doc-2', 'name': 'component-2'},
    ],
    'meta': {
      'pagination': {
        'page': 1,
        'pageSize': 10,
        'pageCount': 1,
        'total': 2,
      }
    },
  }


@pytest.fixture
def multi_page_response_page1():
  """First page of multi-page response."""
  return {
    'data': [
      {'id': 1, 'documentId': 'doc-1', 'name': 'component-1'},
      {'id': 2, 'documentId': 'doc-2', 'name': 'component-2'},
    ],
    'meta': {
      'pagination': {
        'page': 1,
        'pageSize': 2,
        'pageCount': 3,
        'total': 5,
      }
    },
  }


@pytest.fixture
def multi_page_response_page2():
  """Second page of multi-page response."""
  return {
    'data': [
      {'id': 3, 'documentId': 'doc-3', 'name': 'component-3'},
      {'id': 4, 'documentId': 'doc-4', 'name': 'component-4'},
    ],
    'meta': {
      'pagination': {
        'page': 2,
        'pageSize': 2,
        'pageCount': 3,
        'total': 5,
      }
    },
  }


@pytest.fixture
def multi_page_response_page3():
  """Third page of multi-page response."""
  return {
    'data': [
      {'id': 5, 'documentId': 'doc-5', 'name': 'component-5'},
    ],
    'meta': {
      'pagination': {
        'page': 3,
        'pageSize': 2,
        'pageCount': 3,
        'total': 5,
      }
    },
  }


@pytest.fixture
def single_record_response():
  """Sample single record API response."""
  return {
    'data': {
      'id': 1,
      'documentId': 'doc-abc123',
      'name': 'test-component',
      'description': 'A test component',
    },
    'meta': {},
  }


# =============================================================================
# Tests for Helper Functions
# =============================================================================


class TestSetPage:
  """Tests for _set_page helper function."""

  @pytest.mark.parametrize(
    'url,page,expected',
    [
      # URL without existing params
      (
        'https://api.example.com/v1/components',
        2,
        'https://api.example.com/v1/components?pagination%5Bpage%5D=2',
      ),
      # URL with existing params
      (
        'https://api.example.com/v1/components?filters[name]=test',
        3,
        'https://api.example.com/v1/components?filters%5Bname%5D=test&pagination%5Bpage%5D=3',
      ),
      # URL with existing pagination param (should overwrite)
      (
        'https://api.example.com/v1/components?pagination[page]=1',
        5,
        'https://api.example.com/v1/components?pagination%5Bpage%5D=5',
      ),
      # URL with multiple params
      (
        'https://api.example.com/v1/components?sort=asc&limit=10',
        2,
        'https://api.example.com/v1/components?sort=asc&limit=10&pagination%5Bpage%5D=2',
      ),
    ],
  )
  def test_set_page_various_urls(self, url, page, expected):
    """Test _set_page with various URL formats."""
    result = _set_page(url, page)
    assert result == expected

  def test_set_page_preserves_other_params(self):
    """Test that _set_page preserves all other query parameters."""
    url = 'https://api.example.com/v1/components?filter=active&sort=name'
    result = _set_page(url, 10)
    assert 'pagination%5Bpage%5D=10' in result
    assert 'filter=active' in result
    assert 'sort=name' in result


class TestBasename:
  """Tests for _basename helper function."""

  @pytest.mark.parametrize(
    'url,expected',
    [
      # URL with query string
      (
        'https://api.example.com/v1/components?filters=test',
        'https://api.example.com/v1/components',
      ),
      # URL without query string
      (
        'https://api.example.com/v1/components',
        'https://api.example.com/v1/components',
      ),
      # Empty string
      ('', ''),
      # URL with complex query
      (
        'https://api.example.com/v1/components?a=1&b=2&c=3',
        'https://api.example.com/v1/components',
      ),
    ],
  )
  def test_basename_various_urls(self, url, expected):
    """Test _basename strips query string correctly."""
    assert _basename(url) == expected


# =============================================================================
# Tests for ServiceCatalogue Initialization
# =============================================================================


class TestServiceCatalogueInit:
  """Tests for ServiceCatalogue.__init__."""

  def test_init_with_valid_params(self, sc_params, mock_session):
    """Test successful initialization with valid parameters."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_session.head.return_value = mock_response

    sc = ServiceCatalogue(sc_params, session=mock_session)

    assert sc.url == sc_params['url']
    assert sc.key == sc_params['key']
    assert sc.filter == ''
    assert sc.timeout == 10  # default
    assert sc.connection_ok is True
    assert 'Bearer test-api-key-12345' in sc.api_headers['Authorization']

  def test_init_with_filter(self, sc_params_with_filter, mock_session):
    """Test initialization with filter parameter."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_session.head.return_value = mock_response

    sc = ServiceCatalogue(sc_params_with_filter, session=mock_session)

    assert sc.filter == '&filters[name][$contains]=test'
    assert sc.filter in sc.components_get

  def test_init_with_custom_timeout(self, sc_params_with_timeout, mock_session):
    """Test initialization with custom timeout."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_session.head.return_value = mock_response

    sc = ServiceCatalogue(sc_params_with_timeout, session=mock_session)

    assert sc.timeout == 30

  def test_init_connection_failure(self, sc_params, mock_session):
    """Test initialization when connection fails."""
    mock_session.head.side_effect = ConnectionError('Connection refused')

    sc = ServiceCatalogue(sc_params, session=mock_session)

    assert sc.connection_ok is False

  def test_init_creates_default_session_if_not_provided(self, sc_params):
    """Test that a default session is created if none provided."""
    with patch('requests.Session') as mock_session_class:
      mock_instance = Mock()
      mock_response = Mock()
      mock_response.status_code = 200
      mock_instance.head.return_value = mock_response
      mock_session_class.return_value = mock_instance

      sc = ServiceCatalogue(sc_params)

      mock_session_class.assert_called_once()
      assert sc.session == mock_instance


# =============================================================================
# Tests for test_connection
# =============================================================================


class TestTestConnection:
  """Tests for ServiceCatalogue.test_connection."""

  def test_connection_success(self, service_catalogue, mock_session):
    """Test successful connection."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_session.head.return_value = mock_response

    result = service_catalogue.test_connection()

    assert result is True
    mock_session.head.assert_called()

  def test_connection_timeout(self, service_catalogue, mock_session):
    """Test connection timeout."""
    mock_session.head.side_effect = Timeout('Connection timed out')

    result = service_catalogue.test_connection()

    assert result is False

  def test_connection_refused(self, service_catalogue, mock_session):
    """Test connection refused."""
    mock_session.head.side_effect = ConnectionError('Connection refused')

    result = service_catalogue.test_connection()

    assert result is False

  def test_connection_uses_correct_timeout(self, sc_params_with_timeout, mock_session):
    """Test that connection uses configured timeout."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_session.head.return_value = mock_response

    sc = ServiceCatalogue(sc_params_with_timeout, session=mock_session)
    sc.test_connection()

    # Verify timeout was passed to head call
    call_kwargs = mock_session.head.call_args[1]
    assert call_kwargs['timeout'] == 30


# =============================================================================
# Tests for _request_json_with_retry
# =============================================================================


class TestRequestJsonWithRetry:
  """Tests for ServiceCatalogue._request_json_with_retry."""

  def test_success_first_attempt(self, service_catalogue, mock_session):
    """Test successful response on first attempt."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'data': 'test'}
    mock_response.raise_for_status = Mock()
    mock_session.get.return_value = mock_response

    result = service_catalogue._request_json_with_retry(
      'https://api.example.com/test', max_retries=3, timeout=10
    )

    assert result == {'data': 'test'}
    assert mock_session.get.call_count == 1

  def test_success_after_retry(self, service_catalogue, mock_session):
    """Test successful response after retry."""
    mock_fail_response = Mock()
    mock_fail_response.raise_for_status.side_effect = HTTPError('500 Server Error')

    mock_success_response = Mock()
    mock_success_response.status_code = 200
    mock_success_response.json.return_value = {'data': 'success'}
    mock_success_response.raise_for_status = Mock()

    mock_session.get.side_effect = [
      mock_fail_response,
      mock_success_response,
    ]

    with patch('time.sleep'):  # Skip actual sleep
      result = service_catalogue._request_json_with_retry(
        'https://api.example.com/test', max_retries=3, timeout=10
      )

    assert result == {'data': 'success'}
    assert mock_session.get.call_count == 2

  def test_exhausted_retries_raises_runtime_error(
    self, service_catalogue, mock_session
  ):
    """Test that RuntimeError is raised after exhausting retries."""
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = HTTPError('500 Server Error')
    mock_session.get.return_value = mock_response

    with patch('time.sleep'):
      with pytest.raises(RuntimeError) as exc_info:
        service_catalogue._request_json_with_retry(
          'https://api.example.com/test', max_retries=3, timeout=10
        )

    assert 'Exceeded retries' in str(exc_info.value)
    assert mock_session.get.call_count == 3

  @pytest.mark.parametrize('status_code', [400, 401, 403, 404, 500, 502, 503])
  def test_non_2xx_status_triggers_retry(
    self, service_catalogue, mock_session, status_code
  ):
    """Test that non-2xx status codes trigger retry."""
    mock_response = Mock()
    mock_response.status_code = status_code
    mock_response.raise_for_status.side_effect = HTTPError(f'{status_code} Error')
    mock_session.get.return_value = mock_response

    with patch('time.sleep'):
      with pytest.raises(RuntimeError):
        service_catalogue._request_json_with_retry(
          'https://api.example.com/test', max_retries=2, timeout=10
        )

    assert mock_session.get.call_count == 2

  def test_invalid_json_triggers_retry(self, service_catalogue, mock_session):
    """Test that invalid JSON response triggers retry."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = Mock()
    mock_response.json.side_effect = ValueError('Invalid JSON')
    mock_session.get.return_value = mock_response

    with patch('time.sleep'):
      with pytest.raises(RuntimeError):
        service_catalogue._request_json_with_retry(
          'https://api.example.com/test', max_retries=2, timeout=10
        )

    assert mock_session.get.call_count == 2

  def test_exponential_backoff(self, service_catalogue, mock_session):
    """Test that exponential backoff is applied between retries."""
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = HTTPError('Error')
    mock_session.get.return_value = mock_response

    with patch('time.sleep') as mock_sleep:
      with pytest.raises(RuntimeError):
        service_catalogue._request_json_with_retry(
          'https://api.example.com/test', max_retries=4, timeout=10
        )

    # Check backoff pattern: 0.5s, 1.0s, 2.0s
    expected_calls = [call(0.5), call(1.0), call(2.0)]
    assert mock_sleep.call_args_list == expected_calls


# =============================================================================
# Tests for get_with_retry
# =============================================================================


class TestGetWithRetry:
  """Tests for ServiceCatalogue.get_with_retry."""

  def test_single_page_result(self, service_catalogue, single_page_response):
    """Test fetching single page of results."""
    with patch.object(
      service_catalogue, '_request_json_with_retry', return_value=single_page_response
    ):
      result = service_catalogue.get_with_retry('components')

    assert len(result) == 2
    assert result[0]['name'] == 'component-1'
    assert result[1]['name'] == 'component-2'

  def test_multi_page_aggregation(
    self,
    service_catalogue,
    multi_page_response_page1,
    multi_page_response_page2,
    multi_page_response_page3,
  ):
    """Test aggregation of multi-page results."""
    with patch.object(
      service_catalogue,
      '_request_json_with_retry',
      side_effect=[
        multi_page_response_page1,
        multi_page_response_page2,
        multi_page_response_page3,
      ],
    ):
      result = service_catalogue.get_with_retry('components')

    assert len(result) == 5
    assert result[0]['name'] == 'component-1'
    assert result[4]['name'] == 'component-5'

  def test_empty_data_array(self, service_catalogue):
    """Test handling of empty data array."""
    empty_response = {
      'data': [],
      'meta': {'pagination': {'page': 1, 'pageCount': 1, 'total': 0}},
    }
    with patch.object(
      service_catalogue, '_request_json_with_retry', return_value=empty_response
    ):
      result = service_catalogue.get_with_retry('components')

    assert result == []

  def test_preserves_existing_query_params(
    self, service_catalogue, single_page_response
  ):
    """Test that existing query params are preserved in URL."""
    with patch.object(
      service_catalogue, '_request_json_with_retry', return_value=single_page_response
    ) as mock_request:
      service_catalogue.get_with_retry('components?filters[name]=test')

    called_url = mock_request.call_args[0][0]
    assert 'filters[name]=test' in called_url

  def test_failure_on_first_page_returns_empty(self, service_catalogue):
    """Test that failure on first page returns empty list."""
    with patch.object(
      service_catalogue,
      '_request_json_with_retry',
      side_effect=RuntimeError('API Error'),
    ):
      result = service_catalogue.get_with_retry('components')

    assert result == []

  def test_failure_on_subsequent_page_continues(
    self, service_catalogue, multi_page_response_page1
  ):
    """Test that failure on subsequent page doesn't fail aggregation."""
    with patch.object(
      service_catalogue,
      '_request_json_with_retry',
      side_effect=[multi_page_response_page1, RuntimeError('Page 2 failed')],
    ):
      result = service_catalogue.get_with_retry('components')

    # Should have data from page 1 only
    assert len(result) == 2


# =============================================================================
# Tests for get_single_record_with_retry
# =============================================================================


class TestGetSingleRecordWithRetry:
  """Tests for ServiceCatalogue.get_single_record_with_retry."""

  def test_returns_dict_data(self, service_catalogue, single_record_response):
    """Test successful single record retrieval."""
    with patch.object(
      service_catalogue, '_request_json_with_retry', return_value=single_record_response
    ):
      result = service_catalogue.get_single_record_with_retry('components/doc-abc123')

    assert result['name'] == 'test-component'
    assert result['documentId'] == 'doc-abc123'

  def test_data_not_dict_returns_empty(self, service_catalogue):
    """Test handling when data is not a dict."""
    response_with_list = {'data': [{'id': 1}], 'meta': {}}
    with patch.object(
      service_catalogue, '_request_json_with_retry', return_value=response_with_list
    ):
      result = service_catalogue.get_single_record_with_retry('components/123')

    assert result == {}

  def test_request_failure_returns_empty(self, service_catalogue):
    """Test that request failure returns empty dict."""
    with patch.object(
      service_catalogue,
      '_request_json_with_retry',
      side_effect=RuntimeError('API Error'),
    ):
      result = service_catalogue.get_single_record_with_retry('components/123')

    assert result == {}


# =============================================================================
# Tests for get_all_records
# =============================================================================


class TestGetAllRecords:
  """Tests for ServiceCatalogue.get_all_records."""

  def test_delegates_to_get_with_retry(self, service_catalogue, single_page_response):
    """Test that get_all_records correctly delegates to get_with_retry."""
    mock_data = [{'id': 1, 'name': 'test'}]
    with patch.object(
      service_catalogue, 'get_with_retry', return_value=mock_data
    ) as mock_get:
      result = service_catalogue.get_all_records('test-table')

    mock_get.assert_called_once_with('test-table')
    assert result == mock_data


# =============================================================================
# Tests for get_record
# =============================================================================


class TestGetRecord:
  """Tests for ServiceCatalogue.get_record."""

  @pytest.mark.parametrize(
    'table,label,parameter,expected_filter_start',
    [
      # Table without query params
      ('components', 'name', 'test-comp', '?filters'),
      # Table with existing query params
      ('components?populate=true', 'name', 'test-comp', '&filters'),
    ],
  )
  def test_constructs_filter_correctly(
    self, service_catalogue, table, label, parameter, expected_filter_start
  ):
    """Test that filter is constructed correctly based on table URL."""
    mock_data = [{'id': 1, label: parameter}]
    with patch.object(
      service_catalogue, 'get_with_retry', return_value=mock_data
    ) as mock_get:
      service_catalogue.get_record(table, label, parameter)

    called_uri = mock_get.call_args[0][0]
    assert expected_filter_start in called_uri
    assert f'filters[{label}][$eq]={parameter}' in called_uri

  def test_record_found(self, service_catalogue):
    """Test successful record retrieval."""
    mock_data = [{'id': 1, 'name': 'found-record', 'documentId': 'doc-123'}]
    with patch.object(service_catalogue, 'get_with_retry', return_value=mock_data):
      result = service_catalogue.get_record('components', 'name', 'found-record')

    assert result['name'] == 'found-record'

  def test_record_not_found_returns_none(self, service_catalogue):
    """Test that None is returned when record not found."""
    with patch.object(service_catalogue, 'get_with_retry', return_value=[]):
      result = service_catalogue.get_record('components', 'name', 'nonexistent')

    assert result is None

  def test_ampersand_encoding(self, service_catalogue):
    """Test that ampersand in parameter is encoded."""
    mock_data = [{'id': 1, 'name': 'test&name'}]
    with patch.object(
      service_catalogue, 'get_with_retry', return_value=mock_data
    ) as mock_get:
      service_catalogue.get_record('components', 'name', 'test&name')

    called_uri = mock_get.call_args[0][0]
    assert '&amp;' in called_uri


# =============================================================================
# Tests for get_filtered_records
# =============================================================================


class TestGetFilteredRecords:
  """Tests for ServiceCatalogue.get_filtered_records."""

  def test_records_found(self, service_catalogue, mock_session):
    """Test successful filtered records retrieval."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
      'data': [{'id': 1, 'name': 'test'}, {'id': 2, 'name': 'test2'}]
    }
    mock_session.get.return_value = mock_response

    result = service_catalogue.get_filtered_records('components', 'name', 'test')

    assert len(result) == 2
    assert result[0]['id'] == 1

  def test_no_records_found(self, service_catalogue, mock_session):
    """Test when no records match filter."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'data': []}
    mock_session.get.return_value = mock_response

    result = service_catalogue.get_filtered_records('components', 'name', 'nonexistent')

    assert result is None

  @pytest.mark.parametrize('status_code', [400, 404, 500])
  def test_non_200_response(self, service_catalogue, mock_session, status_code):
    """Test handling of non-200 responses."""
    mock_response = Mock()
    mock_response.status_code = status_code
    mock_session.get.return_value = mock_response

    result = service_catalogue.get_filtered_records('components', 'name', 'test')

    assert result is None

  def test_request_exception(self, service_catalogue, mock_session):
    """Test handling of request exceptions."""
    mock_session.get.side_effect = ConnectionError('Connection failed')

    result = service_catalogue.get_filtered_records('components', 'name', 'test')

    assert result is None


# =============================================================================
# Tests for get_record_by_id
# =============================================================================


class TestGetRecordById:
  """Tests for ServiceCatalogue.get_record_by_id."""

  def test_record_found(self, service_catalogue):
    """Test successful record retrieval by ID."""
    mock_data = {'id': 1, 'documentId': 'doc-123', 'name': 'test'}
    with patch.object(
      service_catalogue, 'get_single_record_with_retry', return_value=mock_data
    ):
      result = service_catalogue.get_record_by_id('components', 'doc-123')

    assert result['name'] == 'test'

  def test_record_not_found(self, service_catalogue):
    """Test when record not found by ID."""
    with patch.object(
      service_catalogue, 'get_single_record_with_retry', return_value={}
    ):
      result = service_catalogue.get_record_by_id('components', 'nonexistent')

    assert result is None


# =============================================================================
# Tests for update
# =============================================================================


class TestUpdate:
  """Tests for ServiceCatalogue.update."""

  def test_successful_update(self, service_catalogue, mock_session):
    """Test successful record update."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_session.put.return_value = mock_response

    result = service_catalogue.update('components', 'doc-123', {'name': 'updated'})

    assert result is True
    mock_session.put.assert_called_once()
    call_kwargs = mock_session.put.call_args[1]
    assert call_kwargs['json'] == {'data': {'name': 'updated'}}

  @pytest.mark.parametrize('status_code', [400, 404, 500])
  def test_non_200_response(self, service_catalogue, mock_session, status_code):
    """Test handling of non-200 responses."""
    mock_response = Mock()
    mock_response.status_code = status_code
    mock_response.content = b'Error message'
    mock_session.put.return_value = mock_response

    result = service_catalogue.update('components', 'doc-123', {'name': 'test'})

    assert result is False

  def test_request_exception(self, service_catalogue, mock_session):
    """Test handling of request exceptions."""
    mock_session.put.side_effect = ConnectionError('Connection failed')

    result = service_catalogue.update('components', 'doc-123', {'name': 'test'})

    assert result is False

  def test_uses_configured_timeout(self, service_catalogue, mock_session):
    """Test that update uses configured timeout."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_session.put.return_value = mock_response

    service_catalogue.update('components', 'doc-123', {'name': 'test'})

    call_kwargs = mock_session.put.call_args[1]
    assert call_kwargs['timeout'] == service_catalogue.timeout


# =============================================================================
# Tests for add
# =============================================================================


class TestAdd:
  """Tests for ServiceCatalogue.add."""

  def test_successful_add(self, service_catalogue, mock_session):
    """Test successful record addition."""
    mock_response = Mock()
    mock_response.status_code = 201
    mock_response.json.return_value = {'data': {'id': 1, 'name': 'new-record'}}
    mock_session.post.return_value = mock_response

    result = service_catalogue.add('components', {'name': 'new-record'})

    assert result == {'data': {'id': 1, 'name': 'new-record'}}
    mock_session.post.assert_called_once()

  def test_successful_add_with_team_name(self, service_catalogue, mock_session):
    """Test successful add with team_name field."""
    mock_response = Mock()
    mock_response.status_code = 201
    mock_response.json.return_value = {'data': {'id': 1, 'team_name': 'test-team'}}
    mock_session.post.return_value = mock_response

    result = service_catalogue.add('teams', {'team_name': 'test-team'})

    assert result is not False

  @pytest.mark.parametrize('status_code', [400, 409, 500])
  def test_non_201_response(self, service_catalogue, mock_session, status_code):
    """Test handling of non-201 responses."""
    mock_response = Mock()
    mock_response.status_code = status_code
    mock_response.content = b'Error message'
    mock_session.post.return_value = mock_response

    result = service_catalogue.add('components', {'name': 'test'})

    assert result is False

  def test_request_exception(self, service_catalogue, mock_session):
    """Test handling of request exceptions."""
    mock_session.post.side_effect = ConnectionError('Connection failed')

    result = service_catalogue.add('components', {'name': 'test'})

    assert result is False


# =============================================================================
# Tests for delete
# =============================================================================


class TestDelete:
  """Tests for ServiceCatalogue.delete."""

  @pytest.mark.parametrize('status_code', [200, 204])
  def test_successful_delete(self, service_catalogue, mock_session, status_code):
    """Test successful record deletion."""
    mock_response = Mock()
    mock_response.status_code = status_code
    mock_session.delete.return_value = mock_response

    result = service_catalogue.delete('components', 'doc-123')

    assert result is True
    mock_session.delete.assert_called_once()

  @pytest.mark.parametrize('status_code', [400, 404, 500])
  def test_non_2xx_response(self, service_catalogue, mock_session, status_code):
    """Test handling of non-2xx responses."""
    mock_response = Mock()
    mock_response.status_code = status_code
    mock_response.content = b'Error message'
    mock_session.delete.return_value = mock_response

    result = service_catalogue.delete('components', 'doc-123')

    assert result is False

  def test_request_exception(self, service_catalogue, mock_session):
    """Test handling of request exceptions."""
    mock_session.delete.side_effect = ConnectionError('Connection failed')

    result = service_catalogue.delete('components', 'doc-123')

    assert result is False


# =============================================================================
# Tests for unpublish
# =============================================================================


class TestUnpublish:
  """Tests for ServiceCatalogue.unpublish."""

  def test_successful_unpublish(self, service_catalogue, mock_session):
    """Test successful record unpublish."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_session.put.return_value = mock_response

    result = service_catalogue.unpublish('components', 'doc-123')

    assert result is True
    call_kwargs = mock_session.put.call_args[1]
    assert call_kwargs['json'] == {'data': {'publishedAt': None}}

  def test_non_200_response(self, service_catalogue, mock_session):
    """Test handling of non-200 response."""
    mock_response = Mock()
    mock_response.status_code = 400
    mock_response.content = b'Error'
    mock_session.put.return_value = mock_response

    result = service_catalogue.unpublish('components', 'doc-123')

    assert result is False

  def test_request_exception(self, service_catalogue, mock_session):
    """Test handling of request exceptions."""
    mock_session.put.side_effect = ConnectionError('Connection failed')

    result = service_catalogue.unpublish('components', 'doc-123')

    assert result is False


# =============================================================================
# Tests for get_id
# =============================================================================


class TestGetId:
  """Tests for ServiceCatalogue.get_id."""

  def test_id_found(self, service_catalogue):
    """Test successful ID retrieval."""
    mock_data = [{'documentId': 'doc-abc123', 'name': 'test'}]
    with patch.object(service_catalogue, 'get_with_retry', return_value=mock_data):
      result = service_catalogue.get_id('components', 'name', 'test')

    assert result == 'doc-abc123'

  def test_no_records_found(self, service_catalogue):
    """Test when no records match."""
    with patch.object(service_catalogue, 'get_with_retry', return_value=[]):
      result = service_catalogue.get_id('components', 'name', 'nonexistent')

    assert result is None

  def test_record_missing_document_id(self, service_catalogue):
    """Test when record exists but lacks documentId."""
    mock_data = [{'id': 1, 'name': 'test'}]  # No documentId
    with patch.object(service_catalogue, 'get_with_retry', return_value=mock_data):
      result = service_catalogue.get_id('components', 'name', 'test')

    assert result is None

  def test_ampersand_encoding(self, service_catalogue):
    """Test that ampersand in match_string is encoded."""
    mock_data = [{'documentId': 'doc-123'}]
    with patch.object(
      service_catalogue, 'get_with_retry', return_value=mock_data
    ) as mock_get:
      service_catalogue.get_id('components', 'name', 'test&value')

    called_uri = mock_get.call_args[0][0]
    assert '&amp;' in called_uri


# =============================================================================
# Tests for get_component_env_id
# =============================================================================


class TestGetComponentEnvId:
  """Tests for ServiceCatalogue.get_component_env_id."""

  def test_env_found(self, service_catalogue):
    """Test successful environment ID retrieval."""
    component = {
      'name': 'test-component',
      'envs': [
        {'name': 'dev', 'documentId': 'env-dev-123'},
        {'name': 'prod', 'documentId': 'env-prod-456'},
      ],
    }
    result = service_catalogue.get_component_env_id(component, 'prod')

    assert result == 'env-prod-456'

  def test_env_not_found(self, service_catalogue):
    """Test when environment not found."""
    component = {
      'name': 'test-component',
      'envs': [
        {'name': 'dev', 'documentId': 'env-dev-123'},
      ],
    }
    result = service_catalogue.get_component_env_id(component, 'staging')

    assert result is None

  def test_empty_envs_list(self, service_catalogue):
    """Test handling of empty envs list."""
    component = {'name': 'test-component', 'envs': []}

    result = service_catalogue.get_component_env_id(component, 'prod')

    assert result is None

  def test_missing_envs_key(self, service_catalogue):
    """Test handling when envs key is missing."""
    component = {'name': 'test-component'}

    result = service_catalogue.get_component_env_id(component, 'prod')

    assert result is None


# =============================================================================
# Tests for find_all_teams_ref_in_sc
# =============================================================================


class TestFindAllTeamsRefInSc:
  """Tests for ServiceCatalogue.find_all_teams_ref_in_sc."""

  def test_aggregates_all_team_types(self, service_catalogue):
    """Test that all team types are aggregated."""
    mock_components = [
      {
        'name': 'comp-1',
        'github_project_teams_write': ['team-write-1', 'team-write-2'],
        'github_project_teams_admin': ['team-admin-1'],
        'github_project_teams_maintain': ['team-maintain-1'],
      },
      {
        'name': 'comp-2',
        'github_project_teams_write': ['team-write-3'],
        'github_project_teams_admin': ['team-admin-1'],  # Duplicate
        'github_project_teams_maintain': [],
      },
    ]
    with patch.object(
      service_catalogue, 'get_all_records', return_value=mock_components
    ):
      result = service_catalogue.find_all_teams_ref_in_sc()

    expected = {
      'team-write-1',
      'team-write-2',
      'team-write-3',
      'team-admin-1',
      'team-maintain-1',
    }
    assert result == expected

  def test_handles_none_team_lists(self, service_catalogue):
    """Test handling of None team lists."""
    mock_components = [
      {
        'name': 'comp-1',
        'github_project_teams_write': None,
        'github_project_teams_admin': ['team-admin-1'],
        'github_project_teams_maintain': None,
      },
    ]
    with patch.object(
      service_catalogue, 'get_all_records', return_value=mock_components
    ):
      result = service_catalogue.find_all_teams_ref_in_sc()

    assert result == {'team-admin-1'}

  def test_empty_components_list(self, service_catalogue):
    """Test handling of empty components list."""
    with patch.object(service_catalogue, 'get_all_records', return_value=[]):
      result = service_catalogue.find_all_teams_ref_in_sc()

    assert result == set()


# =============================================================================
# Tests for update_scheduled_job
# =============================================================================


class TestUpdateScheduledJob:
  """Tests for ServiceCatalogue.update_scheduled_job."""

  def test_successful_update_succeeded_status(self, service_catalogue, mock_job):
    """Test successful job update with Succeeded status."""
    mock_job_data = {'documentId': 'job-doc-123', 'name': 'test-scheduled-job'}

    with (
      patch.object(service_catalogue, 'get_record', return_value=mock_job_data),
      patch.object(service_catalogue, 'update', return_value=True) as mock_update,
    ):
      result = service_catalogue.update_scheduled_job('Succeeded', job_context=mock_job)

    assert result is True
    mock_update.assert_called_once()
    update_data = mock_update.call_args[0][2]
    assert 'last_successful_run' in update_data
    assert update_data['result'] == 'Succeeded'

  def test_successful_update_failed_status(self, service_catalogue, mock_job):
    """Test successful job update with Failed status."""
    mock_job.error_messages = ['Error 1', 'Error 2']
    mock_job_data = {'documentId': 'job-doc-123', 'name': 'test-scheduled-job'}

    with (
      patch.object(service_catalogue, 'get_record', return_value=mock_job_data),
      patch.object(service_catalogue, 'update', return_value=True) as mock_update,
    ):
      result = service_catalogue.update_scheduled_job('Failed', job_context=mock_job)

    assert result is True
    update_data = mock_update.call_args[0][2]
    assert 'last_successful_run' not in update_data
    assert update_data['result'] == 'Failed'
    assert update_data['error_details'] == ['Error 1', 'Error 2']

  def test_job_not_found(self, service_catalogue, mock_job):
    """Test handling when job not found in Service Catalogue."""
    with patch.object(service_catalogue, 'get_record', return_value=None):
      result = service_catalogue.update_scheduled_job('Succeeded', job_context=mock_job)

    assert result is False

  def test_update_fails(self, service_catalogue, mock_job):
    """Test handling when update operation fails."""
    mock_job_data = {'documentId': 'job-doc-123', 'name': 'test-scheduled-job'}

    with (
      patch.object(service_catalogue, 'get_record', return_value=mock_job_data),
      patch.object(service_catalogue, 'update', side_effect=Exception('Update failed')),
    ):
      result = service_catalogue.update_scheduled_job('Succeeded', job_context=mock_job)

    assert result is False

  def test_uses_global_job_when_no_context_provided(self, service_catalogue):
    """Test that global job is used when no context provided."""
    mock_job_data = {'documentId': 'job-doc-123', 'name': 'global-job'}

    with (
      patch.object(
        service_catalogue, 'get_record', return_value=mock_job_data
      ) as mock_get,
      patch.object(service_catalogue, 'update', return_value=True),
      patch('src.hmpps.clients.service_catalogue.job') as mock_global_job,
    ):
      mock_global_job.name = 'global-job'
      mock_global_job.error_messages = []

      result = service_catalogue.update_scheduled_job('Succeeded')

    assert result is True
    # Verify get_record was called with the global job name
    mock_get.assert_called_once()
