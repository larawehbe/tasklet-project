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
