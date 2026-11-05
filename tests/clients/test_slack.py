from unittest.mock import MagicMock

from slack_sdk.errors import SlackApiError
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler

from hmpps.clients.slack import Slack


def test_channel_id_lookup_caches_paginated_results():
  slack = Slack(token='test-token')
  slack.slack_client = MagicMock()
  slack.slack_client.conversations_list.side_effect = [
    {
      'channels': [{'name': 'general', 'id': 'C123'}],
      'response_metadata': {'next_cursor': 'next-page'},
    },
    {
      'channels': [{'name': 'alerts', 'id': 'C456'}],
      'response_metadata': {'next_cursor': ''},
    },
  ]

  assert slack.get_slack_channel_id_by_name('general') == 'C123'
  assert slack.get_slack_channel_id_by_name('#alerts') == 'C456'
  assert slack.slack_client.conversations_list.call_count == 2
  assert all(
    call.kwargs['limit'] == 500
    for call in slack.slack_client.conversations_list.call_args_list
  )


def test_channel_id_lookup_can_override_cache_ttl(monkeypatch):
  slack = Slack(token='test-token')
  slack.slack_client = MagicMock()
  slack.slack_client.conversations_list.side_effect = [
    {'channels': [{'name': 'general', 'id': 'C123'}]},
    {'channels': [{'name': 'general', 'id': 'C456'}]},
  ]
  now = [100]
  monkeypatch.setattr('hmpps.clients.slack.time.monotonic', lambda: now[0])

  assert slack.get_slack_channel_id_by_name('general', cache_ttl_seconds=1) == 'C123'
  now[0] = 102
  assert slack.get_slack_channel_id_by_name('general', cache_ttl_seconds=1) == 'C456'
  assert slack.slack_client.conversations_list.call_count == 2


def test_channel_id_lookup_can_bypass_cache():
  slack = Slack(token='test-token')
  slack.slack_client = MagicMock()
  slack.slack_client.conversations_list.side_effect = [
    {'channels': [{'name': 'general', 'id': 'C123'}]},
    {'channels': [{'name': 'general', 'id': 'C456'}]},
  ]

  assert slack.get_slack_channel_id_by_name('general', use_cache=False) == 'C123'
  assert slack.get_slack_channel_id_by_name('general', use_cache=False) == 'C456'
  assert slack.slack_client.conversations_list.call_count == 2
  assert slack._channel_ids_by_name is None


def test_channel_id_lookup_returns_match_if_later_page_fails():
  slack = Slack(token='test-token')
  slack.slack_client = MagicMock()
  slack.slack_client.conversations_list.side_effect = [
    {
      'channels': [{'name': 'general', 'id': 'C123'}],
      'response_metadata': {'next_cursor': 'next-page'},
    },
    SlackApiError('request failed', MagicMock()),
  ]

  assert slack.get_slack_channel_id_by_name('general') == 'C123'
  assert slack._channel_ids_by_name is None


def test_channel_id_lookup_rechecks_cache_after_acquiring_lock(monkeypatch):
  slack = Slack(token='test-token')
  slack.slack_client = MagicMock()
  monkeypatch.setattr('hmpps.clients.slack.time.monotonic', lambda: 100)

  class PopulateCacheLock:
    def __enter__(self):
      slack._channel_ids_by_name = {'general': 'C123'}
      slack._channel_ids_cache_created_at = 100

    def __exit__(self, *args):
      pass

  slack._channel_ids_cache_lock = PopulateCacheLock()

  assert slack.get_slack_channel_id_by_name('general') == 'C123'
  slack.slack_client.conversations_list.assert_not_called()


def test_slack_client_has_rate_limit_retry_handler():
  slack = Slack(token='test-token')

  assert any(
    isinstance(handler, RateLimitErrorRetryHandler)
    for handler in slack.slack_client.retry_handlers
  )


def test_channel_counterpart_uses_cached_channel_map():
  slack = Slack(token='test-token')
  slack.slack_client = MagicMock()
  slack.slack_client.conversations_list.return_value = {
    'channels': [{'name': 'general', 'id': 'C123'}],
  }

  assert slack.get_slack_channel_counterpart('general') == 'C123'
  assert slack.get_slack_channel_counterpart('C123') == 'general'
  assert slack.slack_client.conversations_list.call_count == 1
  slack.slack_client.conversations_info.assert_not_called()


def test_channel_counterpart_uses_info_endpoint_for_uncached_id():
  slack = Slack(token='test-token')
  slack.slack_client = MagicMock()
  slack.slack_client.conversations_info.return_value = {
    'channel': {'name': 'general'},
  }

  assert slack.get_slack_channel_counterpart('C123') == 'general'
  slack.slack_client.conversations_info.assert_called_once_with(channel='C123')