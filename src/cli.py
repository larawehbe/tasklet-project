"""Typer CLI for the Tasklet support agent.

Three commands:

  support-agent init-db
  support-agent list-users
  support-agent chat --user-id <id> [--new] [--verbose]

`chat` resumes the user's most recent conversation by default. Pass --new
to start fresh. Pass --verbose to print every tool call inline.
"""

import os

import typer
from anthropic import Anthropic
from dotenv import load_dotenv

from src.agent import run_turn
from src.conversation import Conversation
from src.db import get_connection, init_db
from src.models import ToolResult, ToolUse

app = typer.Typer(add_completion=False, help="Tasklet Support Agent CLI.")


@app.command("init-db")
def init_db_cmd() -> None:
    """Wipe and re-create the database from schema.sql + seed.sql."""
    init_db()
    typer.echo("Database initialized.")


@app.command("list-users")
def list_users_cmd() -> None:
    """List seed users so you know what user-ids you can chat as."""
    conn = get_connection()
    rows = conn.execute("SELECT id, email, name FROM users ORDER BY id").fetchall()
    if not rows:
        typer.echo("No users found. Run `support-agent init-db` first.")
        raise typer.Exit(1)
    for r in rows:
        typer.echo(f"  {r['id']:>3}  {r['name']:<20}  {r['email']}")
    conn.close()


@app.command()
def chat(
    user_id: int = typer.Option(..., "--user-id", help="User to chat as."),
    new: bool = typer.Option(
        False, "--new", help="Start a fresh conversation instead of resuming."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="Print every tool call and its result."
    ),
) -> None:
    """Open an interactive chat session as the given user."""
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        typer.echo(
            "ANTHROPIC_API_KEY is not set. Add it to .env or export it.",
            err=True,
        )
        raise typer.Exit(2)

    conn = get_connection()
    user_row = conn.execute(
        "SELECT id, name FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if user_row is None:
        typer.echo(
            f"No user with id {user_id}. Run `support-agent list-users` to see options.",
            err=True,
        )
        raise typer.Exit(2)

    conversation = (
        Conversation.new(conn, user_id)
        if new
        else Conversation.load_or_create(conn, user_id)
    )

    client = Anthropic(api_key=api_key)

    typer.echo(f"Chatting as {user_row['name']} (user id {user_id}).")
    if conversation.messages and not new:
        typer.echo(
            f"Resumed conversation with {len(conversation.messages)} prior messages. "
            "Use --new to start fresh."
        )
    typer.echo("Type 'exit' or press Ctrl-D to leave.\n")

    def on_tool_call(tu: ToolUse, tr: ToolResult) -> None:
        prefix = "[tool error]" if tr.is_error else "[tool]"
        snippet = tr.content if len(tr.content) <= 200 else tr.content[:200] + "..."
        typer.echo(f"  {prefix} {tu.name}({tu.input}) -> {snippet}")

    while True:
        try:
            user_input = input("you: ")
        except EOFError:
            typer.echo("\nGoodbye.")
            break

        if user_input.strip().lower() in ("exit", "quit"):
            typer.echo("Goodbye.")
            break
        if not user_input.strip():
            continue

        try:
            result = run_turn(
                client=client,
                conn=conn,
                conversation=conversation,
                user_input=user_input,
                on_tool_call=on_tool_call if verbose else None,
            )
            typer.echo(f"agent: {result.final_text}\n")
        except Exception as e:  # noqa: BLE001  (top-level CLI error guard)
            typer.echo(f"[error] {type(e).__name__}: {e}", err=True)

    conn.close()


if __name__ == "__main__":
    app()
