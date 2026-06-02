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
