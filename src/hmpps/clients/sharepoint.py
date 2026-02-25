import os
import logging
import json
from office365.graph_client import GraphClient

log = logging.getLogger(__name__)


class SharePoint:
  def _redact(self, value):
    return f'{value[:3]}...{value[-3:]}' if value and len(value) > 6 else value

  def __init__(
    self, site_url='', client_id='', client_secret='', tenant_id='', site_name=''
  ):
    """Initialize SharePoint client with Azure AD credentials using Microsoft Graph."""
    self.site_url = site_url or os.getenv(
      'SITE_URL' or 'https://justiceuk.sharepoint.com'
    )
    self.client_id = client_id or os.getenv('SP_CLIENT_ID', '')
    self.client_secret = client_secret or os.getenv('SP_CLIENT_SECRET', '')
    self.tenant_id = tenant_id or os.getenv('AZ_TENANT_ID', '')
    self.site_name = site_name or os.getenv('SITE_NAME', '')

    log.debug(f'client_id: {self._redact(self.client_id)}')
    log.debug(f'client_secret: {self._redact(self.client_secret)}')
    log.debug(f'tenant_id: {self._redact(self.tenant_id)}')

    try:
      # Authenticate using client credentials (app-only)
      self.client = GraphClient(tenant=tenant_id).with_client_secret(
        client_id, client_secret
      )
      log.info(
        f'Successfully authenticated to Microsoft Graph with tenant: {tenant_id}'
      )
    except Exception as e:
      log.error(f'Failed to authenticate to Microsoft Graph: {e}')
      raise

    try:
      # Get the site data
      self.site = self._get_site()
    except Exception as e:
      log.error(f'✗ Failed to get site information: {e}')

  def validate_credentials(self):
    """Validate that credentials can access Microsoft Graph."""
    try:
      if self.site_name:
        site = self.client.sites.get_by_url(self.site_url).get().execute_query()
        log.info(f'✓ Successfully accessed site: {site.name}')

      return True

    except Exception as e:
      log.error(f'✗ Credential validation failed: {e}')
      return False

  def _get_site(self):
    """Get the SharePoint site object."""
    try:
      site = self.client.sites.get_by_url(self.site_url).get().execute_query()
      return site
    except Exception as e:
      log.error(f'✗ Failed to get site: {e}')
      raise

  # Document management section

  def get_document_library(self, library_name):
    """Get a document library (Drive) by name."""
    try:
      drives = self.site.drives.get().execute_query()
      for drive in drives:
        # In Graph API, drive.name is usually "Documents" or the library name
        # drive.web_url can also be checked if needed
        if drive.name == library_name:
          log.info(f'✓ Found document library: {library_name}')
          return drive

      log.error(f"✗ Document library '{library_name}' not found")
      # List available drives to help debugging
      available_drives = [d.name for d in drives if d.name is not None]
      log.info(f'Available libraries: {", ".join(available_drives)}')
      return None
    except Exception as e:
      log.error(f'✗ Failed to get document library: {e}')
      return None

  def get_folder(self, drive, folder_path):
    """Get a folder within a drive by path."""
    try:
      # folder_path should be relative to root, e.g., "Test" or "Folder/Subfolder"
      if not folder_path:
        return drive.root

      # construct the path to the item
      item = drive.root.get_by_path(folder_path).get().execute_query()

      # Verify if it is a folder (Graph DriveItem has a 'folder' facet if it's a folder)
      if item.folder is not None:
        log.info(f'✓ Found folder: {folder_path}')
        return item

      log.error(f"✗ Item at '{folder_path}' is not a folder")
      return None
    except Exception as e:
      log.error(f"✗ Failed to get folder '{folder_path}': {e}")
      return None

  def upload_file(self, drive_name, folder_path, local_file_path):
    """Upload a file to a specific folder in a document library."""
    try:
      drive = self.get_document_library(drive_name)
      if not drive:
        log.warning('Drive not found')
        return False

      target_folder = drive.root
      if folder_path:
        target_folder = target_folder.get_by_path(folder_path)
        log.info('folder_path set')
      else:
        log.warning('folder_path not set')

      file_name = os.path.basename(local_file_path)
      log.debug('Reading in the file content')
      with open(local_file_path, 'rb') as f:
        file_content = f.read()

      # Upload the file
      log.debug('Uploading the file')
      # Use upload(name, content) instead of upload_file(name, content)
      target_folder.upload(file_name, file_content).execute_query()
      log.info(f"✓ Successfully uploaded '{file_name}' to '{drive_name}/{folder_path}'")
      return True

    except Exception as e:
      log.error(f'✗ Failed to upload file: {e}')
      return False

  # List management section

  def _get_list(self, list_title):
    try:
      target_list_name = list_title
      site = self._get_site()
      # Filter by display name to avoid enumerating all lists
      lists = (
        site.lists.filter(f"displayName eq '{target_list_name}'").get().execute_query()
      )

      if len(lists) > 0:
        list = lists[0]
        log.info(f'✓ Found list: {list.display_name}')
        return list

      return None
    except Exception as e:
      log.error(f'✗ Failed to get list: {e}')
      return None

  def get_list_fields(self, list_title):
    """Get all fields (columns) from a list."""
    try:
      target_list = self._get_list(list_title)
      if not target_list:
        log.error(f"List '{list_title}' not found")
        return []

      columns = target_list.columns.get().execute_query()

      log.info(f"Found {len(columns)} fields in '{list_title}':")
      for col in columns:
        log.info(f' - {col.name} (Display: {col.display_name})')

      return columns

    except Exception as e:
      log.error(f'✗ Failed to get list fields: {e}')
      raise

  def ensure_list_exists(self, list_title):
    """Return an error if the list doesn't exist"""
    try:
      existing_list = self._get_list(list_title)

      if existing_list:
        # if delete_if_exists:
        #   log.info(f"List '{list_title}' exists. Deleting to recreate...")
        #   existing_list.delete_object().execute_query()
        #   log.info(f"✓ Deleted existing list '{list_title}'")
        #   return self._create_list(list_title)
        # else:
        log.info(f"List '{list_title}' already exists")
        return existing_list
      else:
        # need to create the list manually
        log.error(
          f'Unable to update Sharepoint list {list_title} - '
          'please make sure it exists and is accessible'
        )
        return None

    except Exception as e:
      log.error(f'✗ Failed to ensure list exists: {e}')
      raise

  def add_list_items_batch(self, list_title, items):
    """Add multiple items to a list in batch mode."""
    try:
      target_list = self._get_list(list_title)
      if not target_list:
        log.error(f"List '{list_title}' not found")
        return []

      log.info(f"Adding {len(items)} items to '{list_title}'...")

      added_items = []
      for item_data in items:
        # Convert item_data to Graph API format (fields property)
        new_item = target_list.items.add(fields=item_data).execute_query()
        added_items.append(new_item)

      log.info(f"✓ Successfully added {len(items)} items to '{list_title}'")
      return added_items

    except Exception as e:
      log.error(f'✗ Failed to add items: {e}')
      raise

  def update_list_items_batch(self, list_title, items):
    """Update multiple items in a list."""
    try:
      target_list = self._get_list(list_title)
      if not target_list:
        return False

      log.info(f"Updating {len(items)} items in '{list_title}'...")

      for item_data in items:
        item_id = item_data.pop('id', None)
        if item_id:
          log.info(f'item_data is: {json.dumps(item_data, indent=2)}')
          item_fields = target_list.items[item_id].fields
          for k, v in item_data.items():
            item_fields.set_property(k, v)
          item_fields.update().execute_query()

      log.info(f"✓ Successfully updated {len(items)} items in '{list_title}'")
      return True

    except Exception as e:
      log.error(f'✗ Failed to update items: {e}')
      raise

  def delete_list_items_batch(self, list_title, item_ids):
    """delete multiple items in a list."""
    try:
      target_list = self._get_list(list_title)
      if not target_list:
        return

      for item_id in item_ids:
        list_item = target_list.items[item_id]
        list_item.delete_object().execute_query()

    except Exception as e:
      log.error(f'✗ Failed to add items: {e}')
      raise

  def get_list_items_with_id(self, list_title, field_list=[], title_field='Title'):
    """Get all items from a list and return a mapping of Title -> ID."""
    try:
      target_list = self._get_list(list_title)
      if not target_list:
        log.error(f"List '{list_title}' not found")
        return {}

      # Use paged() to automatically handle pagination
      items = target_list.items.expand(['fields']).paged(200).get().execute_query()

      id_map = {}
      for item in items:
        title = item.fields.properties.get(title_field, '')
        item_id = item.id

        if title and item_id:
          id_map[title] = {'id': item_id}
          for field_name in field_list:
            id_map[title][field_name] = item.fields.properties.get(field_name)
      log.info(f"Retrieved {len(id_map)} items from '{list_title}'")
      return id_map

    except Exception as e:
      log.error(f'✗ Failed to get list items: {e}')
      raise
