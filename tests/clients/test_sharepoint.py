"""
Comprehensive tests for the SharePoint client.

This module tests all public and private methods of the SharePoint class with
mocking to avoid real Microsoft Graph / SharePoint API calls. Tests are
organised by function and use parameterisation where appropriate for thorough
coverage and data-quality assurance.
"""

import os
import pytest
from unittest.mock import MagicMock, patch


# =============================================================================
# Helpers – build the fluent mock chains that office365 uses
# =============================================================================


def _fluent_chain(return_value=None):
  """Return a mock whose .get().execute_query() yields *return_value*."""
  mock = MagicMock()
  mock.get.return_value.execute_query.return_value = return_value
  return mock


def _make_mock_site(drives=None, lists=None):
  """Create a mock SharePoint site with optional drives and lists."""
  site = MagicMock()
  site.name = 'test-site'

  # drives
  if drives is not None:
    site.drives.get.return_value.execute_query.return_value = drives

  # lists (supports .filter().get().execute_query() chain)
  if lists is not None:
    filter_chain = site.lists.filter.return_value
    filter_chain.get.return_value.execute_query.return_value = lists

  return site


def _graph_site_chain(mock_graph_client):
  """Shortcut to the .sites.get_by_url().get().execute_query chain."""
  return mock_graph_client.sites.get_by_url.return_value.get.return_value.execute_query


def _items_query_chain(mock_list):
  """Shortcut to .items.expand().paged().get().execute_query chain."""
  return mock_list.items.expand.return_value.paged.return_value.get.return_value.execute_query


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_graph_client():
  """Patch GraphClient so no real auth happens."""
  with patch('hmpps.clients.sharepoint.GraphClient') as MockGraphClient:
    instance = MagicMock()
    MockGraphClient.return_value.with_client_secret.return_value = instance
    yield instance


@pytest.fixture
def mock_site():
  """A default mock site object."""
  return _make_mock_site()


@pytest.fixture
def sharepoint(mock_graph_client, mock_site):
  """Fully-initialised SharePoint with all externals mocked."""
  # Make .sites.get_by_url().get().execute_query() return mock_site
  _graph_site_chain(mock_graph_client).return_value = mock_site

  from hmpps.clients.sharepoint import SharePoint

  sp = SharePoint(
    site_url='https://test.sharepoint.com/sites',
    client_id='abc123client',
    client_secret='sec123secret',
    tenant_id='ten123tenant',
    site_name='test-site',
  )
  assert sp.connection_ok is True
  return sp


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_drives():
  """Two mock Drive objects."""
  d1 = MagicMock()
  d1.name = 'Documents'
  d2 = MagicMock()
  d2.name = 'Reports'
  return [d1, d2]


@pytest.fixture
def sample_columns():
  """Mock column objects for a list."""
  col1 = MagicMock()
  col1.name = 'Title'
  col1.display_name = 'Title'
  col2 = MagicMock()
  col2.name = 'Status'
  col2.display_name = 'Status'
  return [col1, col2]


@pytest.fixture
def sample_list_items():
  """Mock list item objects with fields."""
  items = []
  for i in range(3):
    item = MagicMock()
    item.id = str(i + 1)
    item.fields.properties = {
      'Title': f'Item {i + 1}',
      'Status': 'Active',
      'Category': f'Cat-{i}',
    }
    item.to_json.return_value = {
      'id': str(i + 1),
      'fields': {'Title': f'Item {i + 1}', 'Status': 'Active', 'Category': f'Cat-{i}'},
    }
    items.append(item)
  return items


# =============================================================================
# Tests for _redact
# =============================================================================


class TestRedact:
  """Tests for SharePoint._redact (credential masking)."""

  def test_redacts_long_string(self, sharepoint):
    """Strings longer than 6 chars are redacted to first3...last3."""
    assert sharepoint._redact('abcdefghij') == 'abc...hij'

  def test_redacts_exactly_seven_chars(self, sharepoint):
    """Boundary: 7-char string still gets redacted."""
    assert sharepoint._redact('1234567') == '123...567'

  def test_does_not_redact_six_chars(self, sharepoint):
    """Strings of length <= 6 are returned unchanged."""
    assert sharepoint._redact('123456') == '123456'

  def test_does_not_redact_short_string(self, sharepoint):
    assert sharepoint._redact('abc') == 'abc'

  def test_empty_string(self, sharepoint):
    assert sharepoint._redact('') == ''

  def test_none_value(self, sharepoint):
    assert sharepoint._redact(None) is None


# =============================================================================
# Tests for __init__
# =============================================================================


class TestSharePointInit:
  """Tests for SharePoint.__init__."""

  def test_init_with_explicit_params(self, sharepoint):
    """Explicit constructor args are stored correctly."""
    assert sharepoint.site_url == 'https://test.sharepoint.com/sites'
    assert sharepoint.client_id == 'abc123client'
    assert sharepoint.client_secret == 'sec123secret'
    assert sharepoint.tenant_id == 'ten123tenant'
    assert sharepoint.site_name == 'test-site'
    assert sharepoint.site_uri == 'https://test.sharepoint.com/sites/test-site'

  def test_connection_ok_true_on_success(self, sharepoint):
    assert sharepoint.connection_ok is True

  def test_data_and_dict_initialised_empty(self, sharepoint):
    assert sharepoint.data == {}
    assert sharepoint.dict == {}

  def test_site_failure_sets_connection_ok_false(self, mock_graph_client):
    """If _get_site raises, connection_ok stays False but __init__ doesn't raise."""
    _graph_site_chain(mock_graph_client).side_effect = Exception('Site not found')

    from hmpps.clients.sharepoint import SharePoint

    sp = SharePoint(
      site_url='https://x.sharepoint.com/sites',
      client_id='cid',
      client_secret='csec',
      tenant_id='tid',
      site_name='bad-site',
    )
    assert sp.connection_ok is False

  def test_auth_failure_raises(self):
    """If GraphClient authentication fails, __init__ re-raises."""
    with patch('hmpps.clients.sharepoint.GraphClient') as MockGC:
      MockGC.return_value.with_client_secret.side_effect = Exception('Auth failed')

      from hmpps.clients.sharepoint import SharePoint

      with pytest.raises(Exception, match='Auth failed'):
        SharePoint(
          site_url='https://x.sharepoint.com/sites',
          client_id='cid',
          client_secret='csec',
          tenant_id='tid',
          site_name='s',
        )

  def test_init_reads_env_vars_as_fallback(self, mock_graph_client, mock_site):
    """When constructor params are empty, env vars are used."""
    _graph_site_chain(mock_graph_client).return_value = mock_site
    env = {
      'SITE_URL': 'https://env.sharepoint.com/sites',
      'SP_CLIENT_ID': 'env-cid',
      'SP_CLIENT_SECRET': 'env-csec',
      'AZ_TENANT_ID': 'env-tid',
      'SITE_NAME': 'env-site',
    }
    with patch.dict(os.environ, env, clear=False):
      from hmpps.clients.sharepoint import SharePoint

      sp = SharePoint()
      assert sp.site_url == 'https://env.sharepoint.com/sites'
      assert sp.client_id == 'env-cid'
      assert sp.client_secret == 'env-csec'
      assert sp.tenant_id == 'env-tid'
      assert sp.site_name == 'env-site'


# =============================================================================
# Tests for validate_credentials
# =============================================================================


class TestValidateCredentials:
  """Tests for SharePoint.validate_credentials."""

  def test_success(self, sharepoint, mock_graph_client):
    _graph_site_chain(mock_graph_client).return_value = MagicMock(name='ok-site')
    assert sharepoint.validate_credentials() is True

  def test_failure_returns_false(self, sharepoint, mock_graph_client):
    _graph_site_chain(mock_graph_client).side_effect = Exception('Forbidden')
    assert sharepoint.validate_credentials() is False


# =============================================================================
# Tests for _get_site
# =============================================================================


class TestGetSite:
  """Tests for SharePoint._get_site."""

  def test_returns_site(self, sharepoint, mock_graph_client, mock_site):
    _graph_site_chain(mock_graph_client).return_value = mock_site
    result = sharepoint._get_site()
    assert result == mock_site

  def test_raises_on_failure(self, sharepoint, mock_graph_client):
    _graph_site_chain(mock_graph_client).side_effect = Exception('Boom')
    with pytest.raises(Exception, match='Boom'):
      sharepoint._get_site()


# =============================================================================
# Tests for get_document_library
# =============================================================================


class TestGetDocumentLibrary:
  """Tests for SharePoint.get_document_library."""

  def test_found_by_name(self, sharepoint, sample_drives):
    sharepoint.site.drives.get.return_value.execute_query.return_value = sample_drives
    result = sharepoint.get_document_library('Documents')
    assert result is not None
    assert result.name == 'Documents'

  def test_not_found_returns_none(self, sharepoint, sample_drives):
    sharepoint.site.drives.get.return_value.execute_query.return_value = sample_drives
    assert sharepoint.get_document_library('NonExistent') is None

  def test_exception_returns_none(self, sharepoint):
    sharepoint.site.drives.get.return_value.execute_query.side_effect = Exception(
      'Graph error'
    )
    assert sharepoint.get_document_library('Documents') is None

  def test_empty_drives_returns_none(self, sharepoint):
    sharepoint.site.drives.get.return_value.execute_query.return_value = []
    assert sharepoint.get_document_library('Documents') is None


# =============================================================================
# Tests for get_folder
# =============================================================================


class TestGetFolder:
  """Tests for SharePoint.get_folder."""

  def test_empty_path_returns_root(self, sharepoint):
    drive = MagicMock()
    result = sharepoint.get_folder(drive, '')
    assert result is drive.root

  def test_none_path_returns_root(self, sharepoint):
    drive = MagicMock()
    result = sharepoint.get_folder(drive, None)
    assert result is drive.root

  def test_valid_folder(self, sharepoint):
    drive = MagicMock()
    folder_item = MagicMock()
    folder_item.folder = MagicMock()  # Non-None = it's a folder
    drive.root.get_by_path.return_value.get.return_value.execute_query.return_value = (
      folder_item
    )

    result = sharepoint.get_folder(drive, 'Reports/2024')
    assert result == folder_item
    drive.root.get_by_path.assert_called_once_with('Reports/2024')

  def test_item_is_not_a_folder(self, sharepoint):
    drive = MagicMock()
    file_item = MagicMock()
    file_item.folder = None  # Not a folder
    drive.root.get_by_path.return_value.get.return_value.execute_query.return_value = (
      file_item
    )

    assert sharepoint.get_folder(drive, 'file.txt') is None

  def test_exception_returns_none(self, sharepoint):
    drive = MagicMock()
    drive.root.get_by_path.return_value.get.return_value.execute_query.side_effect = (
      Exception('Not found')
    )
    assert sharepoint.get_folder(drive, 'missing') is None


# =============================================================================
# Tests for upload_file
# =============================================================================


class TestUploadFile:
  """Tests for SharePoint.upload_file."""

  def test_successful_upload_with_folder(self, sharepoint, tmp_path):
    """Upload succeeds when drive found and folder path given."""
    # Create a real temp file
    test_file = tmp_path / 'report.csv'
    test_file.write_bytes(b'col1,col2\nval1,val2')

    mock_drive = MagicMock()
    with patch.object(sharepoint, 'get_document_library', return_value=mock_drive):
      result = sharepoint.upload_file('Documents', 'Reports', str(test_file))

    assert result is True
    mock_drive.root.get_by_path.assert_called_once_with('Reports')
    mock_drive.root.get_by_path.return_value.upload.assert_called_once()

  def test_successful_upload_without_folder(self, sharepoint, tmp_path):
    """Upload succeeds to root when folder_path is empty."""
    test_file = tmp_path / 'data.txt'
    test_file.write_bytes(b'hello')

    mock_drive = MagicMock()
    with patch.object(sharepoint, 'get_document_library', return_value=mock_drive):
      result = sharepoint.upload_file('Documents', '', str(test_file))

    assert result is True
    mock_drive.root.get_by_path.assert_not_called()
    mock_drive.root.upload.assert_called_once()

  def test_drive_not_found_returns_false(self, sharepoint, tmp_path):
    test_file = tmp_path / 'data.txt'
    test_file.write_bytes(b'x')

    with patch.object(sharepoint, 'get_document_library', return_value=None):
      assert sharepoint.upload_file('Missing', 'f', str(test_file)) is False

  def test_upload_exception_returns_false(self, sharepoint, tmp_path):
    test_file = tmp_path / 'data.txt'
    test_file.write_bytes(b'x')

    mock_drive = MagicMock()
    mock_drive.root.upload.side_effect = Exception('Upload failed')
    with patch.object(sharepoint, 'get_document_library', return_value=mock_drive):
      assert sharepoint.upload_file('Documents', '', str(test_file)) is False

  def test_uploaded_filename_matches_basename(self, sharepoint, tmp_path):
    """The uploaded name should be the basename of the local path."""
    test_file = tmp_path / 'subdir' / 'report.xlsx'
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_bytes(b'data')

    mock_drive = MagicMock()
    with patch.object(sharepoint, 'get_document_library', return_value=mock_drive):
      sharepoint.upload_file('Documents', '', str(test_file))

    uploaded_name = mock_drive.root.upload.call_args[0][0]
    assert uploaded_name == 'report.xlsx'


# =============================================================================
# Tests for _get_list
# =============================================================================


class TestGetList:
  """Tests for SharePoint._get_list."""

  def test_list_found(self, sharepoint, mock_graph_client, mock_site):
    mock_list = MagicMock()
    mock_list.display_name = 'MyList'

    # _get_list calls _get_site() then filters
    _graph_site_chain(mock_graph_client).return_value = mock_site
    filter_chain = mock_site.lists.filter.return_value
    filter_chain.get.return_value.execute_query.return_value = [mock_list]

    result = sharepoint._get_list('MyList')
    assert result == mock_list

  def test_list_not_found(self, sharepoint, mock_graph_client, mock_site):
    _graph_site_chain(mock_graph_client).return_value = mock_site
    filter_chain = mock_site.lists.filter.return_value
    filter_chain.get.return_value.execute_query.return_value = []

    assert sharepoint._get_list('Missing') is None

  def test_exception_returns_none(self, sharepoint, mock_graph_client):
    _graph_site_chain(mock_graph_client).side_effect = Exception('Error')
    assert sharepoint._get_list('Broken') is None

  def test_filter_uses_correct_display_name(
    self, sharepoint, mock_graph_client, mock_site
  ):
    """Verify the OData filter string uses the supplied list title."""
    _graph_site_chain(mock_graph_client).return_value = mock_site
    filter_chain = mock_site.lists.filter.return_value
    filter_chain.get.return_value.execute_query.return_value = []

    sharepoint._get_list('Inventory Items')

    filter_arg = mock_site.lists.filter.call_args[0][0]
    assert "displayName eq 'Inventory Items'" in filter_arg


# =============================================================================
# Tests for get_list_fields
# =============================================================================


class TestGetListFields:
  """Tests for SharePoint.get_list_fields."""

  def test_returns_columns(self, sharepoint, sample_columns):
    mock_list = MagicMock()
    mock_list.columns.get.return_value.execute_query.return_value = sample_columns

    with patch.object(sharepoint, '_get_list', return_value=mock_list):
      result = sharepoint.get_list_fields('MyList')

    assert len(result) == 2

  def test_list_not_found_returns_empty(self, sharepoint):
    with patch.object(sharepoint, '_get_list', return_value=None):
      assert sharepoint.get_list_fields('Missing') == []

  def test_exception_re_raises(self, sharepoint):
    mock_list = MagicMock()
    mock_list.columns.get.return_value.execute_query.side_effect = Exception('Boom')

    with patch.object(sharepoint, '_get_list', return_value=mock_list):
      with pytest.raises(Exception, match='Boom'):
        sharepoint.get_list_fields('BadList')


# =============================================================================
# Tests for ensure_list_exists
# =============================================================================


class TestEnsureListExists:
  """Tests for SharePoint.ensure_list_exists."""

  def test_list_exists_returns_it(self, sharepoint):
    mock_list = MagicMock()
    mock_list.display_name = 'MyList'
    with patch.object(sharepoint, '_get_list', return_value=mock_list):
      result = sharepoint.ensure_list_exists('MyList')
    assert result == mock_list

  def test_list_not_found_returns_none(self, sharepoint):
    with patch.object(sharepoint, '_get_list', return_value=None):
      assert sharepoint.ensure_list_exists('Missing') is None

  def test_exception_re_raises(self, sharepoint):
    with patch.object(sharepoint, '_get_list', side_effect=Exception('Error')):
      with pytest.raises(Exception, match='Error'):
        sharepoint.ensure_list_exists('BadList')


# =============================================================================
# Tests for add_list_items_batch
# =============================================================================


class TestAddListItemsBatch:
  """Tests for SharePoint.add_list_items_batch."""

  def test_adds_items_successfully(self, sharepoint):
    mock_list = MagicMock()
    new_item = MagicMock()
    mock_list.items.add.return_value.execute_query.return_value = new_item

    items_data = [{'Title': 'Item A'}, {'Title': 'Item B'}]

    with patch.object(sharepoint, '_get_list', return_value=mock_list):
      result = sharepoint.add_list_items_batch('MyList', items_data)

    assert len(result) == 2
    assert mock_list.items.add.call_count == 2

  def test_list_not_found_returns_empty(self, sharepoint):
    with patch.object(sharepoint, '_get_list', return_value=None):
      assert sharepoint.add_list_items_batch('Missing', [{'Title': 'x'}]) == []

  def test_exception_re_raises(self, sharepoint):
    mock_list = MagicMock()
    mock_list.items.add.return_value.execute_query.side_effect = Exception('API error')

    with patch.object(sharepoint, '_get_list', return_value=mock_list):
      with pytest.raises(Exception, match='API error'):
        sharepoint.add_list_items_batch('MyList', [{'Title': 'x'}])

  def test_empty_items_returns_empty(self, sharepoint):
    mock_list = MagicMock()
    with patch.object(sharepoint, '_get_list', return_value=mock_list):
      result = sharepoint.add_list_items_batch('MyList', [])
    assert result == []

  def test_fields_passed_correctly(self, sharepoint):
    """Verify the fields kwarg is forwarded to the API."""
    mock_list = MagicMock()
    mock_list.items.add.return_value.execute_query.return_value = MagicMock()

    data = {'Title': 'Test', 'Status': 'Active'}
    with patch.object(sharepoint, '_get_list', return_value=mock_list):
      sharepoint.add_list_items_batch('MyList', [data])

    mock_list.items.add.assert_called_once_with(fields=data)


# =============================================================================
# Tests for update_list_items_batch
# =============================================================================


class TestUpdateListItemsBatch:
  """Tests for SharePoint.update_list_items_batch."""

  def test_updates_items(self, sharepoint):
    mock_list = MagicMock()

    items = [
      {'id': '1', 'Title': 'Updated A'},
      {'id': '2', 'Title': 'Updated B'},
    ]

    with patch.object(sharepoint, '_get_list', return_value=mock_list):
      result = sharepoint.update_list_items_batch('MyList', items)

    assert result is True
    # Each item triggers set_property + update + execute_query
    assert mock_list.items.__getitem__.call_count == 2

  def test_list_not_found_returns_false(self, sharepoint):
    with patch.object(sharepoint, '_get_list', return_value=None):
      assert sharepoint.update_list_items_batch('Missing', [{'id': '1'}]) is False

  def test_item_without_id_is_skipped(self, sharepoint):
    """Items without an 'id' key should be skipped without error."""
    mock_list = MagicMock()

    items = [{'Title': 'No ID'}]  # no 'id' field

    with patch.object(sharepoint, '_get_list', return_value=mock_list):
      result = sharepoint.update_list_items_batch('MyList', items)

    assert result is True
    mock_list.items.__getitem__.assert_not_called()

  def test_exception_re_raises(self, sharepoint):
    mock_list = MagicMock()
    mock_list.items.__getitem__.return_value.fields.set_property.side_effect = (
      Exception('Update error')
    )

    with patch.object(sharepoint, '_get_list', return_value=mock_list):
      with pytest.raises(Exception, match='Update error'):
        sharepoint.update_list_items_batch('MyList', [{'id': '1', 'Title': 'x'}])


# =============================================================================
# Tests for delete_list_items_batch
# =============================================================================


class TestDeleteListItemsBatch:
  """Tests for SharePoint.delete_list_items_batch."""

  def test_deletes_items(self, sharepoint):
    mock_list = MagicMock()

    with patch.object(sharepoint, '_get_list', return_value=mock_list):
      sharepoint.delete_list_items_batch('MyList', ['1', '2', '3'])

    assert mock_list.items.__getitem__.call_count == 3

  def test_list_not_found_returns_none(self, sharepoint):
    with patch.object(sharepoint, '_get_list', return_value=None):
      result = sharepoint.delete_list_items_batch('Missing', ['1'])
    assert result is None

  def test_exception_re_raises(self, sharepoint):
    mock_list = MagicMock()
    delete_chain = mock_list.items.__getitem__.return_value.delete_object.return_value
    delete_chain.execute_query.side_effect = Exception('Delete error')

    with patch.object(sharepoint, '_get_list', return_value=mock_list):
      with pytest.raises(Exception, match='Delete error'):
        sharepoint.delete_list_items_batch('MyList', ['1'])

  def test_empty_ids_no_calls(self, sharepoint):
    mock_list = MagicMock()
    with patch.object(sharepoint, '_get_list', return_value=mock_list):
      sharepoint.delete_list_items_batch('MyList', [])
    mock_list.items.__getitem__.assert_not_called()


# =============================================================================
# Tests for get_list_items_with_id
# =============================================================================


class TestGetListItemsWithId:
  """Tests for SharePoint.get_list_items_with_id."""

  def test_returns_id_map(self, sharepoint, sample_list_items):
    mock_list = MagicMock()
    _items_query_chain(mock_list).return_value = sample_list_items

    with patch.object(sharepoint, '_get_list', return_value=mock_list):
      result = sharepoint.get_list_items_with_id('MyList')

    assert len(result) == 3
    assert 'Item 1' in result
    assert result['Item 1']['id'] == '1'

  def test_respects_field_list(self, sharepoint, sample_list_items):
    mock_list = MagicMock()
    _items_query_chain(mock_list).return_value = sample_list_items

    with patch.object(sharepoint, '_get_list', return_value=mock_list):
      result = sharepoint.get_list_items_with_id(
        'MyList', field_list=['Status', 'Category']
      )

    # Each entry should have id + Status + Category
    entry = result['Item 1']
    assert entry['id'] == '1'
    assert entry['Status'] == 'Active'
    assert entry['Category'] == 'Cat-0'

  def test_custom_title_field(self, sharepoint):
    """Use a non-default title field for the map key."""
    item = MagicMock()
    item.id = '42'
    item.fields.properties = {'Name': 'custom-key', 'Status': 'Done'}

    mock_list = MagicMock()
    _items_query_chain(mock_list).return_value = [item]

    with patch.object(sharepoint, '_get_list', return_value=mock_list):
      result = sharepoint.get_list_items_with_id('MyList', title_field='Name')

    assert 'custom-key' in result
    assert result['custom-key']['id'] == '42'

  def test_list_not_found_returns_empty_dict(self, sharepoint):
    with patch.object(sharepoint, '_get_list', return_value=None):
      assert sharepoint.get_list_items_with_id('Missing') == {}

  def test_items_missing_title_are_skipped(self, sharepoint):
    """Items without the title field are not included in the map."""
    item_ok = MagicMock()
    item_ok.id = '1'
    item_ok.fields.properties = {'Title': 'Good', 'Status': 'Active'}

    item_no_title = MagicMock()
    item_no_title.id = '2'
    item_no_title.fields.properties = {'Status': 'Active'}  # no Title

    mock_list = MagicMock()
    _items_query_chain(mock_list).return_value = [
      item_ok,
      item_no_title,
    ]

    with patch.object(sharepoint, '_get_list', return_value=mock_list):
      result = sharepoint.get_list_items_with_id('MyList')

    assert len(result) == 1
    assert 'Good' in result

  def test_exception_re_raises(self, sharepoint):
    mock_list = MagicMock()
    _items_query_chain(mock_list).side_effect = Exception('Paging error')

    with patch.object(sharepoint, '_get_list', return_value=mock_list):
      with pytest.raises(Exception, match='Paging error'):
        sharepoint.get_list_items_with_id('MyList')


# =============================================================================
# Tests for _load_list_contents
# =============================================================================


class TestLoadListContents:
  """Tests for SharePoint._load_list_contents."""

  def test_returns_json_shape(self, sharepoint, sample_list_items):
    mock_list = MagicMock()
    _items_query_chain(mock_list).return_value = sample_list_items

    with patch.object(sharepoint, '_get_list', return_value=mock_list):
      result = sharepoint._load_list_contents('MyList')

    assert 'value' in result
    assert len(result['value']) == 3
    # Each entry is the to_json() output
    assert result['value'][0]['id'] == '1'
    assert result['value'][0]['fields']['Title'] == 'Item 1'

  def test_list_not_found_returns_none(self, sharepoint):
    with patch.object(sharepoint, '_get_list', return_value=None):
      assert sharepoint._load_list_contents('Missing') is None


# =============================================================================
# Tests for _make_dict
# =============================================================================


class TestMakeDict:
  """Tests for SharePoint._make_dict."""

  def test_converts_to_dict_keyed_by_id(self, sharepoint):
    data = {
      'value': [
        {'id': '10', 'fields': {'Title': 'A'}},
        {'id': '20', 'fields': {'Title': 'B'}},
      ]
    }
    result = sharepoint._make_dict(data)

    assert len(result) == 2
    assert result['10']['fields']['Title'] == 'A'
    assert result['20']['fields']['Title'] == 'B'

  def test_empty_value_list(self, sharepoint):
    assert sharepoint._make_dict({'value': []}) == {}

  def test_missing_value_key(self, sharepoint):
    """If 'value' key is absent, dict should be empty (iterating None)."""
    # dict comprehension over None would fail, but .get returns None
    # which is not iterable — this documents current behaviour
    with pytest.raises(TypeError):
      sharepoint._make_dict({})

  def test_duplicate_ids_last_wins(self, sharepoint):
    """If two items share an id, the last one wins (dict semantics)."""
    data = {
      'value': [
        {'id': '1', 'fields': {'Title': 'First'}},
        {'id': '1', 'fields': {'Title': 'Second'}},
      ]
    }
    result = sharepoint._make_dict(data)
    assert len(result) == 1
    assert result['1']['fields']['Title'] == 'Second'


# =============================================================================
# Tests for load_sharepoint_lists
# =============================================================================


class TestLoadSharepointLists:
  """Tests for SharePoint.load_sharepoint_lists."""

  def test_loads_multiple_lists(self, sharepoint, sample_list_items):
    """Successful load populates self.data and self.dict."""
    list_contents = {'value': [item.to_json() for item in sample_list_items]}

    with patch.object(sharepoint, '_load_list_contents', return_value=list_contents):
      sharepoint.load_sharepoint_lists(['ListA', 'ListB'])

    assert 'ListA' in sharepoint.data
    assert 'ListB' in sharepoint.data
    assert len(sharepoint.data['ListA']['value']) == 3
    assert 'ListA' in sharepoint.dict
    assert 'ListB' in sharepoint.dict

  def test_none_result_stored_as_empty(self, sharepoint):
    """When _load_list_contents returns None, data is [] and dict is {}."""
    with patch.object(sharepoint, '_load_list_contents', return_value=None):
      sharepoint.load_sharepoint_lists(['EmptyList'])

    assert sharepoint.data['EmptyList'] == []
    assert sharepoint.dict['EmptyList'] == {}

  def test_exception_handled_gracefully(self, sharepoint):
    """Exception in one list doesn't prevent others from loading."""
    good_contents = {'value': [{'id': '1', 'fields': {'Title': 'OK'}}]}

    def side_effect(name):
      if name == 'BadList':
        raise Exception('Broken')
      return good_contents

    with patch.object(sharepoint, '_load_list_contents', side_effect=side_effect):
      sharepoint.load_sharepoint_lists(['GoodList', 'BadList'])

    # GoodList should be loaded
    assert 'GoodList' in sharepoint.data
    assert len(sharepoint.data['GoodList']['value']) == 1
    # BadList should NOT appear in data (exception path doesn't set data)
    assert 'BadList' not in sharepoint.data

  def test_returns_none(self, sharepoint):
    """load_sharepoint_lists always returns None."""
    with patch.object(sharepoint, '_load_list_contents', return_value={'value': []}):
      result = sharepoint.load_sharepoint_lists(['X'])
    assert result is None

  def test_dict_values_keyed_by_item_id(self, sharepoint):
    """Verify the dict cache uses item 'id' as keys."""
    contents = {
      'value': [
        {'id': 'abc', 'fields': {'Title': 'Alpha'}},
        {'id': 'def', 'fields': {'Title': 'Beta'}},
      ]
    }

    with patch.object(sharepoint, '_load_list_contents', return_value=contents):
      sharepoint.load_sharepoint_lists(['TestList'])

    assert 'abc' in sharepoint.dict['TestList']
    assert 'def' in sharepoint.dict['TestList']
    assert sharepoint.dict['TestList']['abc']['fields']['Title'] == 'Alpha'
