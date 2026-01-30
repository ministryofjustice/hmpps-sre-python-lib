import requests
import json
import time
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from hmpps.services.job_log_handling import (
  log_debug,
  log_error,
  log_info,
  log_critical,
  log_warning,
  job,
  Jobs,
)
from datetime import datetime


def _set_page(url: str, page: int) -> str:
  """Return `url` with pagination[page] set to `page`, preserving existing params."""
  parsed = urlparse(url)
  query = dict(parse_qsl(parsed.query, keep_blank_values=True))
  query['pagination[page]'] = str(page)
  new_query = urlencode(query, doseq=True)
  return urlunparse(parsed._replace(query=new_query))


def _basename(url: str) -> str:
  """Return URL without query string (for compact logging)."""
  return url.split('?', 1)[0]


class ServiceCatalogue:
  def __init__(
    self,
    params: Dict[str, Any],
    session: Optional[requests.Session] = None,
  ):
    # default variables
    page_size = 10
    pagination_page_size = f'&pagination[pageSize]={page_size}'
    # Example Sort filter
    # sort_filter='&sort=updatedAt:asc'
    sort_filter = ''

    self.url = params['url']
    self.key = params['key']
    self.timeout = params.get('timeout', 10)
    # Allow injection of a requests session for testability
    self.session = session or requests.Session()

    # limit results for testing/dev
    # See strapi filter syntax
    #   https://docs.strapi.io/dev-docs/api/rest/filters-locale-publication
    # Example filter string = '&filters[name][$contains]=example'
    self.filter = params.get('filter', '')

    self.product_filter = (
      '&fields[0]=slack_channel_id&fields[1]='
      'slack_channel_name&fields[2]=p_id&fields[3]=name'
    )
    self.api_headers = {
      'Authorization': f'Bearer {self.key}',
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    }
    self.components = 'components'
    self.components_get = (
      f'{self.components}?populate[latest_commit]=true&populate'
      f'[product]=true&populate[envs]=true{self.filter}{pagination_page_size}{sort_filter}'
    )
    self.products = 'products'

    self.products_get = (
      f'{self.products}?populate[parent]=true&populate[children]='
      'true&populate[product_set]=true&populate[service_area]=true&populate[team]=true'
      f'{self.product_filter}{pagination_page_size}{sort_filter}'
    )
    self.sharepoint_discovery_products_get = (
      f'{self.products}?populate[parent]=true&'
      'populate[children]=true&populate[product_set]=true&populate[service_area]=true'
      f'&populate[team]=true{pagination_page_size}{sort_filter}'
    )
    self.github_teams = 'github-teams'
    self.environments = 'environments'
    self.environments_get = (
      f'{self.environments}?populate[component]=true{pagination_page_size}{sort_filter}'
    )
    self.scheduled_jobs = 'scheduled-jobs'
    self.connection_ok = self.test_connection()

  """
  Test connection to the Service Catalogue
  """

  def test_connection(self) -> bool:
    # Test connection to Service Catalogue
    try:
      log_info(f'Testing connection to the Service Catalogue - {self.url}')
      r = self.session.head(
        f'{self.url}', headers=self.api_headers, timeout=self.timeout
      )
      log_info(
        f'Successfully connected to the Service Catalogue - {self.url}. {r.status_code}'
      )
      return True
    except Exception as e:
      log_critical(f'Unable to connect to the Service Catalogue - {e}')
      return False

  """
  Generic get request with retry functionality
  """

  def _request_json_with_retry(
    self,
    url: str,
    max_retries: int,
    timeout: int,
  ) -> Dict[str, Any]:
    """GET JSON with retry/backoff; raises after exhausting retries."""
    attempt = 0
    last_err: Exception | None = None

    while attempt < max_retries:
      try:
        resp = self.session.get(url, headers=self.api_headers, timeout=timeout)
        resp.raise_for_status()  # Raises for non-2xx
        return resp.json()
      except (requests.RequestException, ValueError) as e:
        # Request errors or invalid JSON
        last_err = e
        attempt += 1
        log_warning(
          f'Service Catalogue API error for {_basename(url)} '
          f'(attempt {attempt}/{max_retries}): {e}'
        )
        if attempt < max_retries:
          # Exponential backoff: 0.5s, 1.0s, 2.0s...
          time.sleep(0.5 * (2 ** (attempt - 1)))

    # Out of retries
    raise RuntimeError(
      f'Exceeded retries for {_basename(url)} (last error: {last_err})'
    ) from last_err

  def get_with_retry(
    self,
    uri: str,
    max_retries: int = 3,
    timeout: int = 10,
  ) -> List[Any]:
    """
    Fetch all pages for the given `uri`, aggregating the `field` array.
    - Retries each page up to `max_retries` times with exponential backoff.
    - Preserves any existing query params on `uri`.
    """
    base_url = f'{self.url.rstrip("/")}/v1/{uri.lstrip("/")}'
    json_data: List[Any] = []

    # First page
    try:
      first = self._request_json_with_retry(base_url, max_retries, timeout)
      pagination = first['meta']['pagination']
      log_debug(f'Got result page: {pagination["page"]} from Service Catalogue')
      page_count = int(pagination.get('pageCount', 1))
      json_data.extend(first.get('data', []))
    except Exception as e:
      log_error(f'Failed to get page data from Service Catalogue: {e}')
      # If meta/pagination missing, assume single page
      page_count = 1

    # Remaining pages (if any)
    for p in range(2, page_count + 1):
      page_url = _set_page(base_url, p)
      try:
        page_json = self._request_json_with_retry(page_url, max_retries, timeout)
        p_meta = page_json['meta']['pagination']
        log_debug(f'Got result page: {p_meta["page"]} from Service Catalogue')
        json_data.extend(page_json.get('data', []))
      except Exception:
        pass  # If pagination info missing, don't fail aggregation

    return json_data

  # Get a single record (no pagination)
  def get_single_record_with_retry(
    self,
    uri: str,
    max_retries: int = 3,
    timeout: int = 10,
  ) -> Dict[str, Any]:
    """
    Fetch all pages for the given `uri`, aggregating the `field` array.
    - Retries each page up to `max_retries` times with exponential backoff.
    - Preserves any existing query params on `uri`.
    """
    base_url = f'{self.url.rstrip("/")}/v1/{uri.lstrip("/")}'
    json_data: Dict[str, Any] = {}
    try:
      response_data = self._request_json_with_retry(base_url, max_retries, timeout)
      data_obj = response_data.get('data')
      if isinstance(data_obj, dict):
        json_data = data_obj
      else:
        log_warning(f'Unexpected data format for single record: {type(data_obj)}')
    except Exception as e:
      log_error(f'Failed to get data from Service Catalogue: {e}')
    return json_data

  def get_all_records(self, table: str) -> List[Any]:
    """Get all multipage results from Service Catalogue."""
    log_info(
      f'Getting all records from table {table} in Service Catalogue using URL: '
      f'{self.url}/v1/{table}'
    )
    return self.get_with_retry(table)

  def get_record(
    self, table: str, label: str, parameter: str
  ) -> Optional[Dict[str, Any]]:
    """Get a single record by filter parameter from the Service Catalogue."""
    if '?' in table:  # add an extra parameter if there are already parameters
      filter = f'&filters[{label}][$eq]={parameter.replace("&", "&amp;")}'
    else:
      filter = f'?filters[{label}][$eq]={parameter.replace("&", "&amp;")}'
    if json_data := self.get_with_retry(f'{table}{filter}'):
      return json_data[0]
    else:
      return None

  def get_filtered_records(
    self, match_table: str, match_field: str, match_string: str
  ) -> Optional[List[Dict[str, Any]]]:
    """Get filtered records from the Service Catalogue."""
    try:
      r = self.session.get(
        f'{self.url}/v1/{match_table}?filters[{match_field}][$eq]='
        f'{match_string.replace("&", "&amp;")}',
        headers=self.api_headers,
        timeout=self.timeout,
      )
      if r.status_code == 200 and r.json()['data']:
        sc_id = r.json()['data'][0]['id']
        log_debug(
          f'Successfully found Service Catalogue ID for {match_field}='
          f'{match_string} in {match_table}: {sc_id}'
        )
        return r.json()['data']
      log_warning(
        f'Could not find Service Catalogue ID for {match_field}={match_string} '
        f'in {match_table}'
      )
      return None
    except Exception as e:
      log_error(
        f'Error getting Service Catalogue ID for {match_field}={match_string} '
        f'in {match_table}: {e}'
      )
      return None

  def get_record_by_id(self, table: str, id: str) -> Optional[Dict[str, Any]]:
    """Get a single record by id from the Service Catalogue."""
    if json_data := self.get_single_record_with_retry(f'{table}/{id}'):
      return json_data
    else:
      return None

  def update(self, table: str, element_id: str, data: Dict[str, Any]) -> bool:
    """Update a record in the Service Catalogue with passed-in JSON data."""
    try:
      log_debug(f'data to be uploaded: {json.dumps(data, indent=2)}')
      x = self.session.put(
        f'{self.url}/v1/{table}/{element_id}',
        headers=self.api_headers,
        json={'data': data},
        timeout=self.timeout,
      )
      if x.status_code == 200:
        log_info(
          f'Successfully updated record {element_id} in'
          f' {table.split("/")[-1]}: {x.status_code}'
        )
      else:
        log_error(
          f'Received non-200 response from service catalogue for record id'
          f' {element_id} in {table.split("/")[-1]}: {x.status_code}'
          f' {x.content}'
        )
        return False
    except Exception as e:
      log_error(
        f'Error updating service catalogue for record id {element_id} '
        f'in {table.split("/")[-1]}: {e}'
      )
      return False
    return True

  def add(self, table: str, data: Dict[str, Any]) -> Dict[str, Any] | bool:
    """Add a new record to the Service Catalogue."""
    try:
      log_debug(f'Data to be added: {json.dumps(data, indent=2)}')
      x = self.session.post(
        f'{self.url}/v1/{table}',
        headers=self.api_headers,
        json={'data': data},
        timeout=self.timeout,
      )
      if x.status_code == 201:
        log_info(
          f'Successfully added '
          f'{(data["team_name"] if "team_name" in data else data["name"])} '
          f'to {table.split("/")[-1]}: {x.status_code}'
        )
      else:
        log_error(
          f'Received non-201 response from service catalogue to add a record to '
          f'{table.split("/")[-1]}: {x.status_code} {x.content}'
        )
        return False
    except Exception as e:
      log_error(
        f'Error adding a record to {table.split("/")[-1]} in service catalogue: {e}'
      )
      return False
    return x.json()

  def delete(self, table: str, element_id: str) -> bool:
    """Delete a record from the Service Catalogue."""
    try:
      log_debug(f'Deleting record {element_id} from {table.split("/")[-1]}')
      x = self.session.delete(
        f'{self.url}/v1/{table}/{element_id}',
        headers=self.api_headers,
        timeout=self.timeout,
      )
      if 200 <= x.status_code < 300:
        log_info(
          f'Successfully deleted record {element_id} from {table.split("/")[-1]}: '
          f'{x.status_code}'
        )
      else:
        log_error(
          f'Received non-2xx response from service catalogue deleting record id '
          f'{element_id} in {table.split("/")[-1]}: {x.status_code} {x.content}'
        )
        return False
    except Exception as e:
      log_error(
        f'Error deleting record {element_id} from {table.split("/")[-1]} '
        f'in service catalogue: {e}'
      )
      return False
    return True

  def unpublish(self, table: str, element_id: str) -> bool:
    """Unpublish a record in the Service Catalogue."""
    try:
      # log_debug(f'data to be unpublished: {json.dumps(data, indent=2)}')
      data = {'publishedAt': None}
      x = self.session.put(
        f'{self.url}/v1/{table}/{element_id}',
        headers=self.api_headers,
        json={'data': data},
        timeout=self.timeout,
      )
      if x.status_code == 200:
        log_info(
          f'Successfully unpublished record {element_id} in {table.split("/")[-1]}: '
          f'{x.status_code}'
        )
      else:
        log_info(
          f'Received non-200 response from service catalogue for record id {element_id}'
          f' in {table.split("/")[-1]}: {x.status_code} {x.content}'
        )
        return False
    except Exception as e:
      log_error(
        f'Error updating service catalogue for record id {element_id} in '
        f'{table.split("/")[-1]}: {e}'
      )
      return False
    return True

  def get_id(
    self, match_table: str, match_field: str, match_string: str
  ) -> Optional[str]:
    """Get a documentId by filter parameter.

    Example: get_id('github-teams', 'team_name', 'example')
    """
    uri = (
      f'{match_table}?filters[{match_field}][$eq]={match_string.replace("&", "&amp;")}'
    )
    if json_data := self.get_with_retry(uri):
      if sc_id := json_data[0].get('documentId'):
        log_debug(
          f'Successfully found Service Catalogue documentID for '
          f'{match_field}={match_string} in {match_table}: {sc_id}'
        )
        return sc_id
      else:
        log_warning(
          f'Could not find Service Catalogue documentID for '
          f'{match_field}={match_string} in {match_table}'
        )
        return None
    return None

  def get_component_env_id(self, component: Dict[str, Any], env: str) -> Optional[str]:
    """Get environment documentId from a component's envs array."""
    env_id = None
    for env_obj in component.get('envs', []):
      if env_obj.get('name') == env:
        env_id = env_obj.get('documentId')
        log_debug(
          f'Found existing environment ID for {env} in component '
          f'{component.get("name")}: {env_id}'
        )
        break
    if not env_id:
      log_debug(
        f'No existing environment ID found for {env} in component '
        f'{component.get("name")}'
      )
    return env_id

  def find_all_teams_ref_in_sc(self) -> set[str]:
    """Find all GitHub team references across all components in Service Catalogue."""
    components = self.get_all_records(self.components_get)
    combined_teams: set[str] = set()
    for component in components:
      combined_teams.update(component.get('github_project_teams_write', []) or [])
      combined_teams.update(component.get('github_project_teams_admin', []) or [])
      combined_teams.update(component.get('github_project_teams_maintain', []) or [])
    return combined_teams

  def update_scheduled_job(
    self, status: str, job_context: Optional[Jobs] = None
  ) -> bool:
    """Update a scheduled job record in the Service Catalogue."""
    job_ctx = job_context or job  # Fallback to global for backward compat
    job_name = job_ctx.name if job_ctx.name else 'unknown'
    sc_scheduled_jobs_data = self.get_record('scheduled-jobs', 'name', job_name)
    job_data: Dict[str, Any] = {
      'last_scheduled_run': datetime.now().isoformat(),
      'result': status,
      'error_details': job_ctx.error_messages,
    }
    if status == 'Succeeded':
      job_data['last_successful_run'] = datetime.now().isoformat()
    try:
      if not sc_scheduled_jobs_data:
        log_error(f'Job {job_name} not found in Service Catalogue')
        return False
      job_id = sc_scheduled_jobs_data.get('documentId')
      if not job_id:
        log_error(f'Job {job_name} has no documentId')
        return False
      self.update(self.scheduled_jobs, job_id, job_data)
    except Exception as e:
      log_error(f'Job {job_name} not found in Service Catalogue - {e}')
      return False
    return True
