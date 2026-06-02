# API Keys and Service Tokens

API keys authenticate external integrations with the Tasklet API.

## Creating an API key

Go to Settings > Security > API Tokens > Generate New Token. Give it a name (e.g., "CI pipeline") and select the scopes it needs (read, write, admin).

## Rotating keys without downtime

To rotate a key safely:
1. Generate a new token with the same scopes.
2. Update your integration to use the new token.
3. Verify the integration works.
4. Revoke the old token.

Do not revoke first and then create — in-flight requests using the old token will fail during the gap.

## Revoking a token

Go to Settings > Security > API Tokens, find the token, and click "Revoke." If the token is not visible in the UI, it may have been created via the API. Use `DELETE /api/v1/tokens/{token_id}` to revoke it programmatically.

## OAuth apps

If a customer wants to embed your Tasklet integration, register an OAuth app under Settings > Security > OAuth Apps. This gives you a client ID and secret for the standard OAuth 2.0 authorization code flow.

## Token expiry

SCIM tokens expire after 90 days. API tokens do not expire unless revoked. We recommend rotating API tokens every 6 months as a security best practice.
