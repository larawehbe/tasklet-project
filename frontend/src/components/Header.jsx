// Top bar: brand + user switcher.
// The user switcher is the demo's stand-in for authentication.
export default function Header({ users, userId, onChange }) {
  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
      <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
        <div className="flex items-baseline gap-3">
          <div className="text-xl font-bold text-indigo-700">Tasklet</div>
          <div className="text-xs text-slate-500 uppercase tracking-wider">
            Support Dashboard
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Logged in as</span>
          <select
            value={userId}
            onChange={(e) => onChange(parseInt(e.target.value, 10))}
            className="border border-slate-300 rounded-md px-3 py-1.5 text-sm bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}
              </option>
            ))}
          </select>
        </div>
      </div>
    </header>
  )
}
