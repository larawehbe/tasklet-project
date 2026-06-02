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
