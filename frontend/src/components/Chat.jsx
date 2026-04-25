import { useEffect, useRef, useState } from 'react'

// One MessageItem per AgentMessage from the backend. We render three roles:
//   user      — bubble on the right
//   assistant — bubble on the left, plus inline collapsible tool calls
//   tool      — collapsible tool result, indented under the assistant turn
//
// The collapsibles are the "thinking panel" your students will use to peek
// inside the agent's loop.

function ToolCall({ toolCall }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="my-1 ml-2 text-xs">
      <button
        onClick={() => setOpen(!open)}
        className="text-slate-500 hover:text-slate-800 font-mono"
      >
        {open ? '▼' : '▶'} called <span className="text-indigo-600">{toolCall.name}</span>
      </button>
      {open && (
        <pre className="mt-1 p-2 bg-slate-50 rounded text-[11px] overflow-x-auto border border-slate-200">
          {JSON.stringify(toolCall.input, null, 2)}
        </pre>
      )}
    </div>
  )
}

function ToolResult({ toolResult }) {
  const [open, setOpen] = useState(false)
  let pretty = toolResult.content
  try {
    pretty = JSON.stringify(JSON.parse(toolResult.content), null, 2)
  } catch {
    /* keep as-is */
  }
  const tone = toolResult.is_error ? 'text-red-600' : 'text-slate-500'
  return (
    <div className="my-1 ml-6 text-xs">
      <button
        onClick={() => setOpen(!open)}
        className={`${tone} hover:opacity-80 font-mono`}
      >
        {open ? '▼' : '▶'} result {toolResult.is_error && '(error)'}
      </button>
      {open && (
        <pre className="mt-1 p-2 bg-slate-50 rounded text-[11px] overflow-x-auto border border-slate-200 max-h-64">
          {pretty}
        </pre>
      )}
    </div>
  )
}

function MessageItem({ msg }) {
  if (msg.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="bg-indigo-600 text-white px-4 py-2 rounded-2xl rounded-tr-sm max-w-[85%] whitespace-pre-wrap">
          {msg.content}
        </div>
      </div>
    )
  }
  if (msg.role === 'assistant') {
    return (
      <div className="flex flex-col gap-1">
        {msg.content && (
          <div className="flex justify-start">
            <div className="bg-white border border-slate-200 px-4 py-2 rounded-2xl rounded-tl-sm max-w-[85%] whitespace-pre-wrap">
              {msg.content}
            </div>
          </div>
        )}
        {msg.tool_calls?.map((tc, i) => (
          <ToolCall key={i} toolCall={tc} />
        ))}
      </div>
    )
  }
  if (msg.role === 'tool' && msg.tool_result) {
    return <ToolResult toolResult={msg.tool_result} />
  }
  return null
}

export default function Chat({ user, messages, onSend, onReset }) {
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [confirmReset, setConfirmReset] = useState(false)
  const scrollRef = useRef(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, busy])

  const submit = async (e) => {
    e.preventDefault()
    const text = input.trim()
    if (!text || busy) return
    setInput('')
    setBusy(true)
    try {
      await onSend(text)
    } catch (err) {
      // App will surface the error; just unblock the input here.
      console.error(err)
    } finally {
      setBusy(false)
    }
  }

  const handleReset = async () => {
    if (!confirmReset) {
      setConfirmReset(true)
      setTimeout(() => setConfirmReset(false), 3000)
      return
    }
    await onReset()
    setConfirmReset(false)
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-slate-200 flex flex-col h-[640px]">
      <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
        <div>
          <div className="font-semibold">Support agent</div>
          <div className="text-xs text-slate-500">
            chatting with {user?.name}
          </div>
        </div>
        <button
          onClick={handleReset}
          className={`text-xs px-2 py-1 rounded ${
            confirmReset
              ? 'bg-red-50 text-red-700 border border-red-200'
              : 'text-slate-500 hover:text-red-600'
          }`}
        >
          {confirmReset ? 'click again to confirm' : 'Reset'}
        </button>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <div className="text-center text-slate-400 text-sm pt-12 space-y-2">
            <div>Try one of these:</div>
            <div className="italic">"what tickets do I have?"</div>
            <div className="italic">"any urgent bugs from this week?"</div>
            <div className="italic">"open a high priority bug about the login page"</div>
          </div>
        )}
        {messages.map((m, i) => (
          <MessageItem key={i} msg={m} />
        ))}
        {busy && (
          <div className="flex justify-start">
            <div className="bg-white border border-slate-200 px-4 py-2 rounded-2xl rounded-tl-sm">
              <span className="inline-block animate-pulse">●</span>
              <span className="inline-block animate-pulse" style={{ animationDelay: '150ms' }}>●</span>
              <span className="inline-block animate-pulse" style={{ animationDelay: '300ms' }}>●</span>
            </div>
          </div>
        )}
      </div>

      <form onSubmit={submit} className="p-3 border-t border-slate-200 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={busy}
          placeholder="Ask the support agent..."
          className="flex-1 border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-slate-50"
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 disabled:cursor-not-allowed text-white px-4 py-2 rounded-md text-sm font-medium"
        >
          Send
        </button>
      </form>
    </div>
  )
}
