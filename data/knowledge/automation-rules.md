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
