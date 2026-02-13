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
      log_info('Successfully conected to Slack.')
      return True
    except Exception as e:
      log_critical(f'Unable to connect to Slack. {e}')
      return None

  def get_slack_channel_name_by_id(self, slack_channel_id):
    log_debug(f'Getting Slack Channel Name for id {slack_channel_id}')
    slack_channel_name = None
    try:
      slack_channel_name = self.slack_client.conversations_info(
        channel=slack_channel_id
      )['channel']['name']
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
