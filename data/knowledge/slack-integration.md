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
