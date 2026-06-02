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
