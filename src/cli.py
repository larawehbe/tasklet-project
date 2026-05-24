"""Command-line interface for the Tasklet support agent.

Commands
--------
  init-db               Wipe and re-seed data/tasklet.db (destructive).
  list-users            Print every user in the database.
  chat --user-id N      Start an interactive chat session as user N.
                        --new       ignore previous history, start fresh
                        --verbose   print each tool call as it happens
"""

import argparse
import sys

from anthropic import Anthropic
from dotenv import load_dotenv

from src.agent import run_turn
from src.conversation import Conversation
from src.db import get_connection, init_db
from src.models import ToolResult, ToolUse


def cmd_init_db(_args: argparse.Namespace) -> None:
    init_db(seed=True)
    print("Database initialised: data/tasklet.db")


def cmd_list_users(_args: argparse.Namespace) -> None:
    conn = get_connection()
    rows = conn.execute("SELECT id, name, email FROM users ORDER BY id").fetchall()
    conn.close()
    if not rows:
        print("No users found. Run: uv run support-agent init-db")
        return
    for row in rows:
        print(f"  {row['id']:>3}  {row['name']:<25}  {row['email']}")


def _print_tool_call(tu: ToolUse, result: ToolResult) -> None:
    status = "error" if result.is_error else "ok"
    print(f"  [tool] {tu.name}({tu.input}) → [{status}] {result.content[:120]}")


def cmd_chat(args: argparse.Namespace) -> None:
    conn = get_connection()

    row = conn.execute(
        "SELECT name FROM users WHERE id = ?", (args.user_id,)
    ).fetchone()
    if row is None:
        print(f"No user with id={args.user_id}. Run list-users to see valid ids.")
        sys.exit(1)

    print(f"Chatting as {row['name']} (user_id={args.user_id}). Type 'quit' to exit.\n")

    conversation = (
        Conversation.new(conn, args.user_id)
        if args.new
        else Conversation.load_or_create(conn, args.user_id)
    )

    client = Anthropic()
    on_tool_call = _print_tool_call if args.verbose else None

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input or user_input.lower() in {"quit", "exit"}:
            break

        result = run_turn(client, conn, conversation, user_input, on_tool_call)
        print(f"Agent: {result.final_text}\n")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="support-agent",
        description="Tasklet support agent CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Wipe and re-seed the database (destructive)")

    sub.add_parser("list-users", help="Print all users in the database")

    chat_p = sub.add_parser("chat", help="Start an interactive chat session")
    chat_p.add_argument("--user-id", type=int, required=True, help="User to chat as")
    chat_p.add_argument("--new", action="store_true", help="Start a fresh conversation")
    chat_p.add_argument(
        "--verbose", action="store_true", help="Print tool calls as they happen"
    )

    args = parser.parse_args()
    {"init-db": cmd_init_db, "list-users": cmd_list_users, "chat": cmd_chat}[
        args.command
    ](args)


if __name__ == "__main__":
    main()
