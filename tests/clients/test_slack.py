from unittest.mock import MagicMock

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
    call.kwargs['limit'] == 200
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