import os
import time
from threading import Lock
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.http_retry import default_retry_handlers
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler
from hmpps.services.job_log_handling import (
  log_debug,
  log_error,
  log_info,
  log_critical,
  log_warning,
)


class Slack:
  _CHANNEL_IDS_CACHE_TTL_SECONDS = 1800

  def __init__(
    self, notify_channel: str = '', alert_channel: str = '', token: str = ''
  ):
    self.notify_channel = notify_channel or os.getenv('SLACK_NOTIFY_CHANNEL', '')
    self.alert_channel = alert_channel or os.getenv('SLACK_ALERT_CHANNEL', '')
    self.token = token or os.getenv('SLACK_BOT_TOKEN', '')
    self._channel_ids_by_name = None
    self._channel_ids_cache_created_at = 0
    self._channel_ids_cache_lock = Lock()

    # Test auth and connection to Slack
    log_debug(f'Connecting to Slack with token ending {self.token[-4:]}')
    try:
      retry_handlers = default_retry_handlers()
      retry_handlers.append(RateLimitErrorRetryHandler())
      self.slack_client = WebClient(
        token=self.token,
        retry_handlers=retry_handlers,
      )
    except Exception as e:
      log_critical(f'Unable to connect to Slack. {e}')
      return False

  def test_connection(self):
    try:
      self.slack_client.api_test()
      log_info('Successfully connected to Slack.')
      return True
    except Exception as e:
      log_critical(f'Unable to connect to Slack. {e}')
      return None

  def get_slack_channel_name_by_id(self, slack_channel_id=''):
    log_debug(f'Getting Slack Channel Name for id {slack_channel_id}')
    slack_channel_name = None
    try:
      slack_channel_name = (
        self.slack_client.conversations_info(channel=slack_channel_id)
        .get('channel', {})
        .get('name', '')
      )
    except SlackApiError as e:
      if 'channel_not_found' in str(e):
        log_info(
          f'Unable to update Slack channel name - '
          f'{slack_channel_id} not found or private'
        )
      else:
        log_error(f'Slack error: {e}')
    log_debug(f'Slack channel name for {slack_channel_id} is {slack_channel_name}')
    return slack_channel_name

  def _channel_ids_cache_is_valid(self, cache_ttl_seconds):
    return (
      self._channel_ids_by_name is not None
      and time.monotonic() - self._channel_ids_cache_created_at < cache_ttl_seconds
    )

  def _fetch_channel_ids_by_name(self):
    channel_ids_by_name = {}
    cursor = None
    try:
      while True:
        response = self.slack_client.conversations_list(
          types='public_channel,private_channel',
          exclude_archived=True,
          limit=500,
          cursor=cursor,
        )

        for channel in response.get('channels', []):
          name = channel.get('name')
          channel_id = channel.get('id')
          if name and channel_id:
            channel_ids_by_name[name] = channel_id

        cursor = response.get('response_metadata', {}).get('next_cursor')
        if not cursor:
          return channel_ids_by_name, True
    except SlackApiError as e:
      log_error(f'Slack error: {e}')
      return channel_ids_by_name, False

  def get_slack_channel_id_by_name(
    self,
    slack_channel_name='',
    *,
    cache_ttl_seconds=None,
    use_cache=True,
  ):
    log_debug(f'Getting Slack Channel ID for name {slack_channel_name}')
    slack_channel_id = None

    if not slack_channel_name:
      log_info('Unable to get Slack channel ID - no channel name provided')
      return slack_channel_id

    # If caller passes a Slack channel ID already, return it unchanged.
    if isinstance(slack_channel_name, str) and slack_channel_name.startswith(
      ('C', 'G')
    ):
      log_debug(
        f'Input {slack_channel_name} looks like a Slack channel ID, returning as-is'
      )
      return slack_channel_name

    normalized_channel_name = str(slack_channel_name).lstrip('#')
    cache_ttl_seconds = (
      self._CHANNEL_IDS_CACHE_TTL_SECONDS
      if cache_ttl_seconds is None
      else cache_ttl_seconds
    )

    if not use_cache:
      log_debug('Bypassing Slack channel ID cache')
      channel_ids, complete = self._fetch_channel_ids_by_name()
      if not complete:
        return channel_ids.get(normalized_channel_name)
    else:
      if self._channel_ids_cache_is_valid(cache_ttl_seconds):
        log_debug(f'Using cached Slack channel IDs for {normalized_channel_name}')
      else:
        log_debug(f'Refreshing Slack channel ID cache for {normalized_channel_name}')
        with self._channel_ids_cache_lock:
          if not self._channel_ids_cache_is_valid(cache_ttl_seconds):
            channel_ids, complete = self._fetch_channel_ids_by_name()
            if not complete:
              return channel_ids.get(normalized_channel_name)
            self._channel_ids_by_name = channel_ids
            self._channel_ids_cache_created_at = time.monotonic()

      channel_ids = self._channel_ids_by_name

    slack_channel_id = channel_ids.get(normalized_channel_name)
    if not slack_channel_id:
      log_info(
        f'Unable to get Slack channel ID - channel {normalized_channel_name} not found'
      )

    log_debug(f'Slack channel ID for {normalized_channel_name} is {slack_channel_id}')
    return slack_channel_id

  def get_slack_channel_counterpart(
    self,
    channel='',
    *,
    cache_ttl_seconds=None,
    use_cache=True,
  ):
    """Return a channel ID for a name or a name for a channel ID.

    Name lookups use the cached channel list. ID lookups use a valid cached
    list when available, then fall back to Slack's conversations.info endpoint.
    """
    if not channel:
      log_info('Unable to get Slack channel counterpart - no channel provided')
      return None

    # Channel IDs use C/G prefixes; names are looked up in the opposite direction.
    if isinstance(channel, str) and channel.startswith(('C', 'G')):
      cache_ttl_seconds = (
        self._CHANNEL_IDS_CACHE_TTL_SECONDS
        if cache_ttl_seconds is None
        else cache_ttl_seconds
      )
      # Only a fully loaded, unexpired list can answer reverse lookups from cache.
      cache_is_valid = (
        use_cache
        and self._channel_ids_by_name is not None
        and time.monotonic() - self._channel_ids_cache_created_at
        < cache_ttl_seconds
      )
      if cache_is_valid:
        for channel_name, channel_id in self._channel_ids_by_name.items():
          if channel_id == channel:
            log_debug(f'Using cached Slack channel name for {channel}')
            return channel_name

      # The direct endpoint can resolve IDs missing from the cached channel list.
      return self.get_slack_channel_name_by_id(channel)

    return self.get_slack_channel_id_by_name(
      channel,
      cache_ttl_seconds=cache_ttl_seconds,
      use_cache=use_cache,
    )

  def notify(self, message):
    if not self.notify_channel:
      log_warning('No notification channel set in config')
      return
    log_debug(f'Sending notification to {self.notify_channel}')
    try:
      self.slack_client.chat_postMessage(
        channel=self.notify_channel, text=f':information-source: {message}'
      )
    except SlackApiError as e:
      log_error(f'Slack error: {e}')

  def alert(self, message):
    if not self.alert_channel:
      log_error('No alert channel set in config')
      return
    log_debug(f'Sending alert to {self.alert_channel}')
    try:
      self.slack_client.chat_postMessage(
        channel=self.alert_channel, text=f':warning_triangle: {message}'
      )
    except SlackApiError as e:
      log_error(f'Slack error: {e}')

  def get_user_id_by_email(self, email):
    log_debug(f'Looking up Slack user for email {email}')
    try:
      if result := self.slack_client.users_lookupByEmail(email=email):
        user_id = result.get('user', {}).get('id')
        return f'<@{user_id}>'
    except SlackApiError as e:
      if e.response['error'] == 'users_not_found':
        log_warning(f'User with email {email} not found.')
        return email
      log_error(f'Error looking up user by email: {e}')
      return email
