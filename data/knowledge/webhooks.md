# Webhooks

Webhooks let external systems react to events in Tasklet in real time.

## Setting up a webhook

1. Go to Settings > Integrations > Webhooks.
2. Click "Add Webhook."
3. Enter the target URL where Tasklet should send POST requests.
4. Select which events to subscribe to: ticket.created, ticket.updated, ticket.commented, sprint.started, sprint.completed.
5. Save.

## Payload

Each webhook POST includes a JSON body with the event type, timestamp, and the full object that changed. The `X-Signature` header contains an HMAC-SHA256 of the payload using your webhook secret.

## Signature verification

If the `X-Signature` header is empty, regenerate your webhook secret under Settings > Integrations > Webhooks > Edit. Copy the new secret into your receiver and verify it matches.

## Retries

Tasklet retries failed deliveries three times with a fixed 20-second interval. If your endpoint is intermittently slow, some events may be missed. Exponential backoff is planned for a future release.

## Deploy hooks

Webhooks fire on all push events by default. For tagged releases, ensure your webhook subscription includes the `release.tagged` event under the event selector.
