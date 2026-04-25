import { useEffect, useState, useCallback } from 'react'
import { api } from './api.js'
import Header from './components/Header.jsx'
import Metrics from './components/Metrics.jsx'
import Chat from './components/Chat.jsx'
import TicketTable from './components/TicketTable.jsx'

export default function App() {
  const [users, setUsers] = useState([])
  const [userId, setUserId] = useState(null)
  const [tickets, setTickets] = useState([])
  const [filters, setFilters] = useState({})
  const [messages, setMessages] = useState([])
  const [error, setError] = useState(null)

  // First load — fetch users, default to the first.
  useEffect(() => {
    api.listUsers()
      .then((u) => {
        setUsers(u)
        if (u.length > 0) setUserId((prev) => prev ?? u[0].id)
      })
      .catch((e) => setError(e.message))
  }, [])

  const refreshTickets = useCallback(async () => {
    if (!userId) return
    try {
      const t = await api.listTickets(userId, filters)
      setTickets(t)
    } catch (e) {
      setError(e.message)
    }
  }, [userId, filters])

  const refreshConversation = useCallback(async () => {
    if (!userId) return
    try {
      const c = await api.getConversation(userId)
      setMessages(c.messages)
    } catch (e) {
      setError(e.message)
    }
  }, [userId])

  // Refresh on user / filter change.
  useEffect(() => { refreshTickets() }, [refreshTickets])
  useEffect(() => { refreshConversation() }, [refreshConversation])

  const handleSend = async (text) => {
    setError(null)
    const result = await api.sendMessage(userId, text)
    setMessages(result.messages)
    // The agent may have created a ticket — refresh so the panel updates live.
    refreshTickets()
  }

  const handleReset = async () => {
    setError(null)
    await api.resetConversation(userId)
    setMessages([])
  }

  if (!userId) {
    return (
      <div className="p-12 text-center text-slate-500">
        {error ? `Error: ${error}` : 'Loading...'}
      </div>
    )
  }

  const currentUser = users.find((u) => u.id === userId)

  return (
    <div className="min-h-screen">
      <Header users={users} userId={userId} onChange={setUserId} />

      {error && (
        <div className="max-w-7xl mx-auto px-6 mt-4">
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded-md text-sm flex justify-between items-center">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="ml-3 text-red-500 hover:text-red-700">×</button>
          </div>
        </div>
      )}

      <main className="max-w-7xl mx-auto p-6 space-y-6">
        <Metrics tickets={tickets} />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Chat
            user={currentUser}
            messages={messages}
            onSend={handleSend}
            onReset={handleReset}
          />
          <TicketTable
            tickets={tickets}
            filters={filters}
            onFiltersChange={setFilters}
          />
        </div>
      </main>
    </div>
  )
}
