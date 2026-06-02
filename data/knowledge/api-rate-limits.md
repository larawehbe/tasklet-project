# API Rate Limits

Tasklet enforces rate limits to keep the platform stable for all users.

## Current limits

- Free plan: 60 requests per minute.
- Team plan: 300 requests per minute.
- Enterprise plan: 1000 requests per minute.

Limits are per API token, not per user.

## Rate limit headers

Every API response includes these headers:
- `X-RateLimit-Limit` — your plan limit.
- `X-RateLimit-Remaining` — requests remaining in the current window.
- `X-RateLimit-Reset` — Unix timestamp when the window resets.

Use these headers to self-throttle your integration. If you receive a 429 Too Many Requests response, wait until the reset time before retrying.

## Bulk operations

For large batch updates (e.g., updating 200 tickets), use the bulk endpoint `PATCH /api/v1/tickets/bulk` instead of individual PATCH calls. The bulk endpoint counts as one request regardless of how many tickets it updates.

## Recent changes

As of the April release, rate limits for Team plans were lowered from 500 to 300 requests per minute. If your nightly jobs started receiving 429s after the April update, this is likely the cause. Consider spreading requests over a longer window or upgrading to Enterprise.
