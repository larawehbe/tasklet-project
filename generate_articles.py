"""Generate synthetic Tasklet help articles for the knowledge base.

Run once:
    python generate_articles.py

Creates data/knowledge/ with ~18 markdown files covering topics
that match the seed ticket data. No API calls, no dependencies.
"""

from pathlib import Path

ARTICLES = {
    "jira-integration.md": """\
# Setting Up the Jira Integration

Tasklet can sync tickets bidirectionally with Jira so your team does not have to update two systems.

## How to connect

1. Go to Settings > Integrations > Jira.
2. Click "Connect Jira" and sign in with your Atlassian account.
3. Select the Jira project you want to link to your Tasklet project.
4. Choose the sync direction: Tasklet to Jira, Jira to Tasklet, or both.
5. Map your Tasklet categories and priorities to Jira issue types and priorities.
6. Click "Start Sync."

## Import limits

The initial import processes up to 500 tickets. For larger projects the import runs in batches of 100-150 tickets. If the sync halts mid-import, check Settings > Integrations > Jira > Sync Log for error details. Common causes include expired Jira API tokens and rate limits on the Jira side.

## Troubleshooting

If sync stops unexpectedly, re-authenticate your Jira connection and retry. If PR comments from Jira are not appearing on linked Tasklet tickets, verify that the "Pull Request Comments" toggle is enabled under the integration settings.
""",
    "slack-integration.md": """\
# Connecting Slack to Tasklet

The Slack integration lets your team receive ticket notifications in Slack channels and create tickets directly from Slack.

## Setup

1. Go to Settings > Integrations > Slack.
2. Click "Add to Slack" and authorize Tasklet in your Slack workspace.
3. Choose a default channel for notifications.
4. Optionally map individual Tasklet projects to specific Slack channels under Settings > Integrations > Slack > Channel Mapping.

## Features

- Ticket creation, status changes, and comments post to your chosen channel.
- Use the `/tasklet create` slash command to file a ticket without leaving Slack.
- Use `/tasklet invite @user` to send a Tasklet workspace invite from Slack.

## Per-project channel mapping

By default all notifications go to one channel. To send each project to its own channel, go to Settings > Integrations > Slack > Channel Mapping and assign a channel per project.

## Known limitations

- Ticket titles longer than 100 characters may show a blank preview when pinned in Slack.
- Webhook delivery retries three times within 60 seconds. If your Slack endpoint is slow, some events may be dropped. A future update will add exponential backoff.
""",
    "sprint-board-basics.md": """\
# Sprint Board Basics

The sprint board is where your team plans, tracks, and completes work for each sprint.

## Columns

By default you get four columns: To Do, In Progress, Review, and Done. You can rename, add, or remove columns under Board Settings. To reorder columns, drag them by their header.

## WIP limits

Work-in-progress limits are not yet supported natively. This is a frequently requested feature. As a workaround, add the max count to the column name (e.g., "In Progress (max 5)") as a visual reminder.

## Dragging tickets

Drag tickets between columns to change their status. If a ticket snaps back to its original column, check that you have edit permissions on the project and that the board is not in read-only mode.

## Filtering

Use the filter bar above the board to narrow by assignee, priority, or label. Note: if you apply a filter, switch tabs, and come back, the filter bar may collapse. This is a known issue being tracked.
""",
    "billing-and-plans.md": """\
# Billing and Seat Management

Tasklet offers three plans: Free (up to 5 users), Team (up to 50 users), and Enterprise (unlimited).

## Viewing your invoice

Go to Settings > Billing > Invoices. Each invoice shows the billing period, seat count, and total charge.

## Adding or removing seats

Under Settings > Billing > Seats, click "Add seat" or "Remove seat." Changes take effect on the next billing cycle. If you remove a seat mid-cycle, the charge for that seat continues until the current period ends, then stops.

## Annual renewal

Annual plans renew automatically. You receive a renewal email 30 days before the renewal date. If the seat count on the renewal email looks wrong, check Settings > Billing > Seats to see the current count. Removed seats should disappear after the current period ends. If they do not, contact support.

## Refunds

Tasklet does not offer partial refunds for unused seats mid-cycle. If you were charged for a seat you already removed, verify the removal date under Settings > Billing > Seats > History.
""",
    "inviting-teammates.md": """\
# Inviting Teammates

You can invite new users to your Tasklet workspace in several ways.

## From the web app

1. Go to Settings > Members > Invite.
2. Enter one or more email addresses.
3. Choose a role: Member, Admin, or Guest (read-only).
4. Click "Send Invites."

Invitees receive an email with a join link. If the email does not arrive, ask them to check their spam folder. Invite emails are sent from noreply@tasklet.example and may be flagged by corporate email filters.

## From Slack

If you have the Slack integration connected, use `/tasklet invite @user` to send an invite directly from Slack.

## Domain capture

Want everyone with your company email domain to auto-join? Go to Settings > Security > Domain Capture, enter your domain (e.g., @hooli.example), and enable it. New signups with that domain will be added to your workspace automatically.

## Guest access

To share a board with an external user as view-only, invite them with the Guest role. Guests can view boards and tickets but cannot create, edit, or comment.
""",
    "api-rate-limits.md": """\
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
""",
    "scim-and-sso.md": """\
# SCIM Provisioning and SSO Setup

Tasklet supports SAML-based single sign-on and SCIM for automated user provisioning.

## SAML SSO

1. Go to Settings > Security > SSO.
2. Enter your Identity Provider (IdP) metadata URL or upload the XML file.
3. Copy the Tasklet ACS URL and Entity ID into your IdP configuration.
4. Test the connection, then enable SSO.

If your IdP rotates the metadata URL, update it under Settings > Security > SSO > Edit Connection.

## SCIM with Okta

1. In Okta, add the Tasklet SCIM app from the directory.
2. Under Provisioning, enter the Tasklet SCIM endpoint: `https://api.tasklet.example/scim/v2`.
3. Enter your SCIM bearer token (generate one under Settings > Security > API Tokens).
4. Enable Create Users, Update Users, and Deactivate Users.

If you see "invalid metadata" on the Okta side, regenerate the SCIM token in Tasklet and re-enter it in Okta. Tokens expire after 90 days.

## Troubleshooting

If SAML login fails after IdP changes, verify the metadata URL and ACS URL match. If SCIM sync stops, check that the bearer token has not expired.
""",
    "exporting-data.md": """\
# Exporting Data from Tasklet

Tasklet supports several export formats for tickets, reports, and workspace data.

## CSV export

From any filtered ticket list, click the "Export" button in the top-right corner. The CSV respects your current filters — if you are viewing only open bugs, the CSV contains only open bugs.

## Sprint reports as PDF

Go to Sprints > select a completed sprint > Reports > Export as PDF. The PDF includes the burndown chart, completed tickets, and carry-over items. Share it with leadership or attach it to a retro document.

## Full workspace export (JSON)

Under Settings > Data > Export Workspace, click "Start Export." This generates a JSON archive of all tickets, comments, and metadata. Note: uploaded file attachments are not included in the JSON export. To export attachments, use the API endpoint `GET /api/v1/attachments/export`.

## Scheduled reports

You can set up a weekly email report that summarizes the previous week per team. Go to Settings > Reports > Scheduled and configure the recipients, day, and time. Reports are sent in HTML email format.
""",
    "webhooks.md": """\
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
""",
    "automation-rules.md": """\
# Automation Rules

Automation rules let you trigger actions automatically when certain conditions are met.

## Creating a rule

1. Go to Project Settings > Automation > New Rule.
2. Choose a trigger: ticket created, status changed, priority changed, comment added, or sprint started.
3. Add conditions to narrow when the rule fires (e.g., only when priority is urgent).
4. Choose an action: change status, assign to user, add label, send notification, or post to Slack.
5. Save and enable.

## Examples

- Auto-assign urgent bugs to the on-call engineer.
- Post to Slack when a ticket moves to "resolved."
- Add a "needs-review" label when a ticket enters the "Review" column.

## Known issues

The action dropdown in the rule editor may be clipped if the browser window is short. Scroll down or resize the window to see all options. This is a known UI bug being tracked.

## Limits

Free plans can have up to 5 rules per project. Team plans allow 50. Enterprise plans have no limit.
""",
    "time-tracking.md": """\
# Time Tracking

Tasklet includes built-in time tracking so your team can log hours directly on tickets.

## Starting a timer

Open any ticket and click the stopwatch icon. The timer runs until you click it again to stop. Logged time appears in the ticket activity feed.

## Midnight rollover

If a timer is running across midnight (e.g., you start at 11:30 PM and stop at 12:30 AM), the timer should continue counting. There is a known bug where the timer resets to zero at midnight. If this happens, manually add the missing time under the ticket's Time Log tab.

## Reports

View time reports under Reports > Time Tracking. Filter by project, user, or date range. Export as CSV for payroll or client billing.
""",
    "notifications.md": """\
# Notifications

Tasklet sends notifications for ticket updates, mentions, and sprint events.

## Email notifications

By default you receive email notifications when:
- Someone mentions you in a comment.
- A ticket assigned to you changes status.
- A sprint you are part of starts or ends.

Manage your preferences under Settings > Notifications > Email.

## Disabling notifications globally

Admins can temporarily silence all email notifications for the workspace under Settings > Notifications > Global Override. This is useful during onboarding when new team members have not configured their preferences yet.

## Duplicate notifications

If you receive two emails for the same event (e.g., a mention triggers two emails ~30 seconds apart), this is a known bug. The engineering team is working on a fix. As a workaround, disable the "real-time" notification option and keep only "batched" (every 15 minutes).

## In-app notifications

The bell icon in the top-right shows unread notifications. Click it to see recent activity. Mark all as read with the checkmark button.
""",
    "custom-fields.md": """\
# Custom Fields

Custom fields let you add structured metadata to tickets beyond the default title, description, category, and priority.

## Adding a custom field

1. Go to Project Settings > Custom Fields > Add Field.
2. Choose a type: text, number, dropdown, date, or checkbox.
3. Name the field (e.g., "Customer Impact", "Story Points", "Due Date").
4. Optionally set a default value.
5. Save.

The field now appears on every ticket in that project. Fill it in when creating or editing a ticket.

## Filtering by custom fields

Custom fields are available as filters in the ticket list and sprint board. Click "Add Filter" and select your custom field from the dropdown.

## Limitations

- Custom fields are per-project, not global. If you want the same field across projects, you must create it in each one.
- The API does not yet support custom fields. This is on the roadmap.
- Free plans are limited to 3 custom fields per project.
""",
    "api-keys.md": """\
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
""",
    "search-tips.md": """\
# Searching Tickets

The search bar at the top of the ticket list searches across ticket titles and descriptions.

## Basic search

Type any keyword and press Enter. Results include tickets where the keyword appears in the title or description. Search is case-insensitive.

## Filters vs search

Filters (status, priority, category, assignee) narrow the ticket list structurally. Search matches text content. You can combine both: filter to "open bugs" and then search for "Safari" to find open bugs mentioning Safari.

## Performance

Search on workspaces with fewer than 10,000 tickets is typically instant. For larger workspaces (50,000+ tickets), search may take 5-15 seconds. The team is working on improving search performance for large workspaces.
""",
    "github-integration.md": """\
# GitHub Integration

Link your GitHub repositories to Tasklet so commits, pull requests, and issues stay connected to tickets.

## Setup

1. Go to Settings > Integrations > GitHub.
2. Click "Connect GitHub" and authorize the Tasklet GitHub App.
3. Select which repositories to link.
4. Tasklet will auto-link commits and PRs that mention a ticket ID (e.g., "Fixes TASK-42").

## PR comments

When a PR linked to a Tasklet ticket receives comments, those comments appear in the ticket activity feed. If PR comments stop syncing, check that the GitHub App still has the "Pull requests" permission enabled in your GitHub organization settings.

## GitHub Actions

Build status from GitHub Actions appears on linked tickets. There may be a 5-10 minute delay between the build completing and the status updating in Tasklet. This is due to GitHub webhook delivery timing, not a Tasklet issue.

## Deploy hooks

Webhooks fire on push events by default. If deploy hooks are not firing on tagged releases, verify that the `release.tagged` event is selected in your webhook subscription under Settings > Integrations > Webhooks.
""",
    "audit-log.md": """\
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
""",
    "keyboard-shortcuts.md": """\
# Keyboard Shortcuts

Tasklet supports keyboard shortcuts for common actions.

## Global shortcuts

- `Ctrl+K` (or `Cmd+K` on Mac) — Open the command palette.
- `Ctrl+N` — Create a new ticket.
- `Ctrl+/` — Focus the search bar.
- `G then B` — Go to the sprint board.
- `G then L` — Go to the ticket list.
- `G then S` — Go to settings.

## Board shortcuts

- `Arrow keys` — Move between tickets on the board.
- `Enter` — Open the selected ticket.
- `M` — Assign the selected ticket to yourself.
- `P` — Cycle priority (low > medium > high > urgent).

## Ticket detail shortcuts

- `E` — Edit the ticket title.
- `C` — Add a comment.
- `Esc` — Close the ticket detail panel.

View all shortcuts by pressing `?` from any page.
""",
}


def main():
    out_dir = Path("data/knowledge")
    out_dir.mkdir(parents=True, exist_ok=True)

    for filename, content in ARTICLES.items():
        path = out_dir / filename
        path.write_text(content)
        print(f"  created {path}")

    print(f"\nDone — {len(ARTICLES)} articles in {out_dir}/")


if __name__ == "__main__":
    main()