## Classes

### hmpps.Slack
Client for sending Slack messages and looking up Slack users and channels.
Rate-limited Slack API requests are retried using Slack's `Retry-After` delay.

### Functions

*get_slack_channel_counterpart(channel, *, cache_ttl_seconds=None, use_cache=True)*
Purpose: Return a channel ID when given a channel name, or a channel name when given an ID.
Inputs: channel (name or channel ID); optional cache TTL in seconds and cache toggle.
Outputs: the corresponding ID or name, or None if it cannot be resolved.
Notes: Name lookups cache the paginated channel list visible to the token for 30 minutes by default. Public channels require `channels:read`; private channels require `groups:read` and must be visible to the token. ID lookups use a valid cached list when available and otherwise call Slack's `conversations.info` endpoint. Set `use_cache=False` to bypass caching.