# Contribution Challenges — Tasklet Support Agent

This codebase is a teaching reference for production AI agents. Help us grow it. Pick a challenge that matches your level, build it, open a pull request.

## Rules of engagement

- One challenge per PR — keep scope tight.
- Update `CLAUDE.md` if you introduce new conventions.
- The security model is non-negotiable. Every read and write must be scoped by `user_id` from the authenticated session, never from LLM input. If your change interacts with the security model, prove the property still holds — by structure, not just by comment.
- Include the prompt(s) you used in the PR description, or save them under `prompts/`. The prompt is the teaching artifact.
- Update the `README.md` if your change affects how the project runs.
- Verify your work the way the project already does — read the code structurally for security properties, watch the tool log for correctness, run the demo walkthrough for qualitative behavior. Match the existing pattern.

---

## Tier 1 — Quick wins (a few hours)

### 1. Update ticket status
Currently the agent refuses any status changes. Add a fourth tool `update_ticket_status` with the same security model — scoped by `user_id`, validated input. Update the system prompt to remove the refusal language for status updates. Add demo prompts to the README walkthrough.

### 2. Ticket search by keyword
Add a `query` filter on `list_tickets` that does a `LIKE %query%` match on title and description. Update the tool description so Claude knows when to use it. Add demo prompts.

### 3. CSV export of tickets
A new CLI command and a matching API endpoint that exports the current user's tickets as CSV. Pure backend. No LLM.

### 4. Dark mode toggle on the React dashboard
Tailwind has `dark:` variants. Add a toggle in the header, persist the preference. Frontend-only. Good warm-up if you're new to React.

---

## Tier 2 — Real design work (a weekend)

### 5. Streaming responses
Convert `/chat` from a synchronous POST to a streaming Server-Sent Events endpoint. The agent loop should stream text and tool calls as they happen. Update `Chat.jsx` in the React app to consume the stream. Covers backpressure, error handling, and the EventSource API.

### 6. Admin user
Add an `is_admin` flag to the users table. Admins can see all tickets across all users. Regular users still can't. Prove the property structurally — show how `dispatch()` and the service layer evolve without breaking the existing security guarantees for non-admins.

### 7. Conversation summary
When a conversation passes a configurable number of messages, summarize older turns into a single system note before sending to Claude. Keep recent turns verbatim. Demonstrates context window management.

### 8. Prompt caching
The README explicitly lists this as "intentionally not implemented." Implement it. Mark the system prompt and tool schemas with `cache_control={"type": "ephemeral"}`. Measure the cost difference across a multi-turn session. Submit a write-up of when caching helps and when it doesn't.

---

## Tier 3 — Flagship (a week or more)

### 9. Multi-tool-per-turn parallel mode
The system prompt currently forces sequential tool use. Add a configuration option that allows Claude to issue multiple tools in one response, dispatch them concurrently, and feed all results back. Update the agent loop and the cap logic. Submit benchmarks comparing sequential vs parallel on multi-tool prompts.

### 10. A new agent persona
Same architecture, different domain. Build a personal finance agent over a transactions table — same security model, same tool-use pattern, same loop. Proves that the architecture is the asset, not the specific app.

### 11. Slack bot frontend
A fourth UI alongside CLI, Streamlit, and React. Slack slash commands or a bot user calling the FastAPI backend. Reinforces the lesson that the agent doesn't know who's calling it. Genuinely impressive portfolio piece.

### 12. Production deployment with real auth
Replace the user dropdown with real OAuth (Google or GitHub). Sessions, tokens, the works. The security model now has to interact with a real authentication layer — and it should still hold structurally. Document the trust boundary clearly.