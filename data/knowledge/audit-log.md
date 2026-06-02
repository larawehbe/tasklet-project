# Audit Log

The audit log records actions taken in your workspace for security and compliance purposes.

## What is logged

- User logins and logouts (including SSO sessions).
- Ticket creation, updates, and deletion.
- Member invitations, role changes, and removals.
- Integration connections and disconnections.
- API token creation and revocation.
- Settings changes.

## Viewing the log

Go to Settings > Security > Audit Log. Filter by user, action type, or date range.

## What is not logged

Tool and integration API calls (e.g., calls made by a Jira sync or GitHub webhook) do not currently appear in the audit log. This is a known gap. Only actions initiated by a human user through the web app or API with a user token are logged.

## Retention

Audit logs are retained for 1 year on Team plans and 3 years on Enterprise plans. Free plans do not have audit log access.
