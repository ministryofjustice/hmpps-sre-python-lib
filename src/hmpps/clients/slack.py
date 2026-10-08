import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from hmpps.services.job_log_handling import (
  log_debug,
  log_error,
  log_info,
  log_critical,
  log_warning,
)


class Slack:
  def __init__(
    self, notify_channel: str = '', alert_channel: str = '', token: str = ''
  ):
    self.notify_channel = notify_channel or os.getenv('SLACK_NOTIFY_CHANNEL', '')
    self.alert_channel = alert_channel or os.getenv('SLACK_ALERT_CHANNEL', '')
    self.token = token or os.getenv('SLACK_BOT_TOKEN', '')

    # Test auth and connection to Slack
    log_debug(f'Connecting to Slack with token ending {self.token[-4:]}')
    try:
      self.slack_client = WebClient(token=self.token)
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

  def get_slack_channel_id_by_name(self, slack_channel_name=''):
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

    try:
      cursor = None
      while True:
        response = self.slack_client.conversations_list(
          types='public_channel,private_channel',
          exclude_archived=True,
          limit=1000,
          cursor=cursor,
        )

        channels = response.get('channels', [])
        for channel in channels:
          if channel.get('name') == normalized_channel_name:
            slack_channel_id = channel.get('id')
            log_debug(
              f'Slack channel ID for {normalized_channel_name} is {slack_channel_id}'
            )
            return slack_channel_id

        cursor = response.get('response_metadata', {}).get('next_cursor')
        if not cursor:
          break

      log_info(
        f'Unable to get Slack channel ID - channel {normalized_channel_name} not found'
      )
    except SlackApiError as e:
      log_error(f'Slack error: {e}')

    log_debug(f'Slack channel ID for {normalized_channel_name} is {slack_channel_id}')
    return slack_channel_id

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
