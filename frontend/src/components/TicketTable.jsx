// Ticket table with filter chips above. Filters are sent as query
// parameters to GET /api/users/{id}/tickets — no client-side filtering
// (so the backend's authorization model is the only thing that decides
// what the user sees, even from this UI).

const PRIORITY_BADGE = {
  urgent: 'bg-red-100 text-red-700 ring-red-200',
  high: 'bg-orange-100 text-orange-700 ring-orange-200',
  medium: 'bg-amber-100 text-amber-700 ring-amber-200',
  low: 'bg-slate-100 text-slate-600 ring-slate-200',
}

const STATUS_BADGE = {
  open: 'bg-blue-100 text-blue-700 ring-blue-200',
  in_progress: 'bg-indigo-100 text-indigo-700 ring-indigo-200',
  waiting_on_customer: 'bg-amber-100 text-amber-700 ring-amber-200',
  resolved: 'bg-green-100 text-green-700 ring-green-200',
  closed: 'bg-slate-100 text-slate-600 ring-slate-200',
}

const STATUSES = ['open', 'in_progress', 'waiting_on_customer', 'resolved', 'closed']
const PRIORITIES = ['urgent', 'high', 'medium', 'low']
const CATEGORIES = [
  'bug_report',
  'feature_request',
  'billing',
  'integration_issue',
  'how_to_question',
]

const labelize = (s) => s.replace(/_/g, ' ')

function FilterSelect({ label, value, options, onChange }) {
  return (
    <select
      value={value || ''}
      onChange={(e) => onChange(e.target.value || null)}
      className="border border-slate-300 rounded-md px-2 py-1 text-xs bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
    >
      <option value="">{label}</option>
      {options.map((o) => (
        <option key={o} value={o}>
          {labelize(o)}
        </option>
      ))}
    </select>
  )
}

function Badge({ value, palette }) {
  return (
    <span
      className={`px-2 py-0.5 rounded text-[11px] font-medium ring-1 ${palette[value] || 'bg-slate-100 text-slate-600 ring-slate-200'}`}
    >
      {labelize(value)}
    </span>
  )
}

export default function TicketTable({ tickets, filters, onFiltersChange }) {
  const set = (key) => (val) => onFiltersChange({ ...filters, [key]: val })
  const hasFilters = !!(filters.status || filters.priority || filters.category)

  return (
    <div className="bg-white rounded-lg shadow-sm border border-slate-200 flex flex-col h-[640px]">
      <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between flex-wrap gap-2">
        <div>
          <div className="font-semibold">Tickets</div>
          <div className="text-xs text-slate-500">
            {tickets.length} {tickets.length === 1 ? 'ticket' : 'tickets'} matching
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <FilterSelect
            label="all status"
            value={filters.status}
            options={STATUSES}
            onChange={set('status')}
          />
          <FilterSelect
            label="all priority"
            value={filters.priority}
            options={PRIORITIES}
            onChange={set('priority')}
          />
          <FilterSelect
            label="all category"
            value={filters.category}
            options={CATEGORIES}
            onChange={set('category')}
          />
          {hasFilters && (
            <button
              onClick={() => onFiltersChange({})}
              className="text-xs text-slate-500 hover:text-slate-700"
            >
              clear
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-[11px] uppercase tracking-wider text-slate-500 sticky top-0">
            <tr>
              <th className="text-left px-4 py-2 font-medium">id</th>
              <th className="text-left px-4 py-2 font-medium">priority</th>
              <th className="text-left px-4 py-2 font-medium">title</th>
              <th className="text-left px-4 py-2 font-medium">status</th>
              <th className="text-left px-4 py-2 font-medium">created</th>
            </tr>
          </thead>
          <tbody>
            {tickets.map((t) => (
              <tr
                key={t.id}
                className="border-t border-slate-100 hover:bg-slate-50"
              >
                <td className="px-4 py-2 text-slate-400 font-mono text-xs">
                  #{t.id}
                </td>
                <td className="px-4 py-2">
                  <Badge value={t.priority} palette={PRIORITY_BADGE} />
                </td>
                <td className="px-4 py-2 text-slate-700">{t.title}</td>
                <td className="px-4 py-2">
                  <Badge value={t.status} palette={STATUS_BADGE} />
                </td>
                <td className="px-4 py-2 text-slate-500 text-xs whitespace-nowrap">
                  {new Date(t.created_at).toLocaleDateString(undefined, {
                    month: 'short',
                    day: 'numeric',
                  })}
                </td>
              </tr>
            ))}
            {tickets.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  className="text-center text-slate-400 py-12 text-sm"
                >
                  No tickets match these filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
