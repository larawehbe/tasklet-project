// Four KPI cards across the top. Recomputed from the current ticket list,
// so they reflect whatever filters are active in the table below.

const OPEN_STATUSES = ['open', 'in_progress', 'waiting_on_customer']
const CLOSED_STATUSES = ['resolved', 'closed']

export default function Metrics({ tickets }) {
  const total = tickets.length
  const open = tickets.filter((t) => OPEN_STATUSES.includes(t.status)).length
  const urgent = tickets.filter((t) => t.priority === 'urgent').length
  const resolved = tickets.filter((t) => CLOSED_STATUSES.includes(t.status)).length

  const cards = [
    { label: 'Total', value: total, accent: 'text-slate-700', dot: 'bg-slate-400' },
    { label: 'Open', value: open, accent: 'text-blue-700', dot: 'bg-blue-500' },
    { label: 'Urgent', value: urgent, accent: 'text-red-700', dot: 'bg-red-500' },
    { label: 'Resolved', value: resolved, accent: 'text-green-700', dot: 'bg-green-500' },
  ]

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((c) => (
        <div
          key={c.label}
          className="bg-white rounded-lg shadow-sm p-5 border border-slate-200"
        >
          <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-slate-500">
            <span className={`w-2 h-2 rounded-full ${c.dot}`}></span>
            {c.label}
          </div>
          <div className={`mt-2 text-3xl font-bold ${c.accent}`}>
            {c.value}
          </div>
        </div>
      ))}
    </div>
  )
}
