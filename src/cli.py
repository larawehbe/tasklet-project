"""CLI entry point for the Tasklet support agent.

Three commands:
  init-db     — wipe and re-seed the database.
  list-users  — show all users so you know which --user-id to pass.
  chat        — start an interactive support session for a given user.
"""

import typer
from anthropic import Anthropic
from dotenv import load_dotenv

from src.agent import run_turn
from src.conversation import Conversation
from src.db import get_connection, init_db
from src.models import ToolResult, ToolUse

load_dotenv()

app = typer.Typer(help="Tasklet support agent CLI.")


@app.command("init-db")
def init_db_cmd() -> None:
    """Wipe and re-seed the database from schema.sql + seed.sql."""
    init_db(seed=True)
    typer.echo("Database initialised.")


@app.command("list-users")
def list_users() -> None:
    """Print every user so you know which --user-id to pass to chat."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT id, name, email FROM users ORDER BY id").fetchall()
    finally:
        conn.close()

    if not rows:
        typer.echo("No users found. Run `support-agent init-db` first.")
        raise typer.Exit(1)

    typer.echo(f"{'ID':<5} {'Name':<20} Email")
    typer.echo("-" * 50)
    for row in rows:
        typer.echo(f"{row['id']:<5} {row['name']:<20} {row['email']}")


@app.command()
def chat(
    user_id: int = typer.Option(..., "--user-id", help="ID of the user to chat as."),
    new: bool = typer.Option(False, "--new", help="Start a fresh conversation."),
    verbose: bool = typer.Option(False, "--verbose", help="Print every tool call."),
) -> None:
    """Interactive multi-turn support chat for --user-id."""
    client = Anthropic()
    conn = get_connection()

    conversation = (
        Conversation.new(conn, user_id)
        if new
        else Conversation.load_or_create(conn, user_id)
    )

    if conversation.messages:
        typer.echo(f"Resuming conversation {conversation.id} ({len(conversation.messages)} messages).")
    else:
        typer.echo(f"New conversation {conversation.id}.")

    typer.echo("Type your message, or 'quit' / Ctrl-C to exit.\n")

    def on_tool_call(tu: ToolUse, result: ToolResult) -> None:
        typer.echo(f"  [tool] {tu.name}({tu.input}) → {result.content}")

    try:
        while True:
            user_input = typer.prompt("You")
            if user_input.strip().lower() in {"quit", "exit", "q"}:
                break

            result = run_turn(
                client,
                conn,
                conversation,
                user_input,
                on_tool_call=on_tool_call if verbose else None,
            )
            typer.echo(f"\nAgent: {result.final_text}\n")
    except (KeyboardInterrupt, EOFError):
        typer.echo("\nGoodbye.")
    finally:
        conn.close()
