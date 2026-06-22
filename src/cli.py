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
from src.models import ToolResult, ToolUse, User

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
        rows = conn.execute(
            "SELECT id, name, email, is_admin FROM users ORDER BY id"
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        typer.echo("No users found. Run `support-agent init-db` first.")
        raise typer.Exit(1)

    typer.echo(f"{'ID':<5} {'Admin':<7} {'Name':<20} Email")
    typer.echo("-" * 58)
    for row in rows:
        admin_label = "yes" if row["is_admin"] else "no"
        typer.echo(f"{row['id']:<5} {admin_label:<7} {row['name']:<20} {row['email']}")


def _load_user(conn, user_id: int) -> User:
    row = conn.execute(
        "SELECT id, email, name, is_admin FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if row is None:
        typer.echo(f"User {user_id} not found. Run `support-agent list-users` to see valid ids.")
        raise typer.Exit(1)
    return User(**dict(row))


@app.command()
def chat(
    user_id: int = typer.Option(..., "--user-id", help="ID of the user to chat as."),
    new: bool = typer.Option(False, "--new", help="Start a fresh conversation."),
    verbose: bool = typer.Option(False, "--verbose", help="Print every tool call."),
) -> None:
    """Interactive multi-turn support chat for --user-id."""
    client = Anthropic()
    conn = get_connection()

    user = _load_user(conn, user_id)

    conversation = (
        Conversation.new(conn, user_id)
        if new
        else Conversation.load_or_create(conn, user_id)
    )

    if conversation.messages:
        typer.echo(f"Resuming conversation {conversation.id} ({len(conversation.messages)} messages).")
    else:
        typer.echo(f"New conversation {conversation.id}.")

    if user.is_admin:
        typer.echo("[Admin session — ticket queries span all users]")

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
                user,
                user_input,
                on_tool_call=on_tool_call if verbose else None,
            )
            typer.echo(f"\nAgent: {result.final_text}\n")
    except (KeyboardInterrupt, EOFError):
        typer.echo("\nGoodbye.")
    finally:
        conn.close()
