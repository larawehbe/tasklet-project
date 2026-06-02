"""CLI entry point for the Tasklet support agent.

Registered as the `support-agent` console script via pyproject.toml.

Usage:
    uv run support-agent init-db
    uv run support-agent list-users
    uv run support-agent chat --user-id 1
    uv run support-agent chat --user-id 1 --new
    uv run support-agent chat --user-id 1 --verbose
"""

import argparse
import os
import sys

from anthropic import Anthropic
from dotenv import load_dotenv

from src.agent import run_turn
from src.conversation import Conversation
from src.db import get_connection, init_db
from src.models import ToolResult, ToolUse


def cmd_init_db(_args: argparse.Namespace) -> None:
    init_db()
    print("Database initialized.")


def cmd_list_users(_args: argparse.Namespace) -> None:
    conn = get_connection()
    rows = conn.execute("SELECT id, email, name FROM users ORDER BY id").fetchall()
    conn.close()
    if not rows:
        print("No users found. Run `uv run support-agent init-db` first.")
        sys.exit(1)
    for r in rows:
        print(f"  {r['id']:>3}  {r['name']:<20}  {r['email']}")


def cmd_chat(args: argparse.Namespace) -> None:
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY is not set. Add it to .env or export it.", file=sys.stderr)
        sys.exit(2)

    conn = get_connection()
    user_row = conn.execute(
        "SELECT id, name FROM users WHERE id = ?", (args.user_id,)
    ).fetchone()
    if user_row is None:
        print(
            f"No user with id {args.user_id}. Run `uv run support-agent list-users` to see options.",
            file=sys.stderr,
        )
        sys.exit(2)

    conversation = (
        Conversation.new(conn, args.user_id)
        if args.new
        else Conversation.load_or_create(conn, args.user_id)
    )

    client = Anthropic(api_key=api_key)

    print(f"Chatting as {user_row['name']} (user id {args.user_id}).")
    if conversation.messages and not args.new:
        print(
            f"Resumed conversation with {len(conversation.messages)} prior messages. "
            "Use --new to start fresh."
        )
    print("Type 'exit' or press Ctrl-D to leave.\n")

    def on_tool_call(tu: ToolUse, tr: ToolResult) -> None:
        prefix = "[tool error]" if tr.is_error else "[tool]"
        snippet = tr.content if len(tr.content) <= 200 else tr.content[:200] + "..."
        print(f"  {prefix} {tu.name}({tu.input}) -> {snippet}")

    while True:
        try:
            user_input = input("you: ")
        except EOFError:
            print("\nGoodbye.")
            break

        if user_input.strip().lower() in ("exit", "quit"):
            print("Goodbye.")
            break
        if not user_input.strip():
            continue

        try:
            result = run_turn(
                client=client,
                conn=conn,
                conversation=conversation,
                user_input=user_input,
                on_tool_call=on_tool_call if args.verbose else None,
            )
            print(f"agent: {result.final_text}\n")
        except Exception as e:  # noqa: BLE001
            print(f"[error] {type(e).__name__}: {e}", file=sys.stderr)

    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="support-agent",
        description="Tasklet Support Agent CLI",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.required = True

    sub.add_parser("init-db", help="Wipe and reseed the database.")
    sub.add_parser("list-users", help="Show available users.")

    chat_p = sub.add_parser("chat", help="Start an interactive chat session.")
    chat_p.add_argument("--user-id", type=int, required=True, help="User to chat as.")
    chat_p.add_argument("--new", action="store_true", help="Start a fresh conversation.")
    chat_p.add_argument("--verbose", action="store_true", help="Print every tool call and result.")

    args = parser.parse_args()

    if args.command == "init-db":
        cmd_init_db(args)
    elif args.command == "list-users":
        cmd_list_users(args)
    elif args.command == "chat":
        cmd_chat(args)


if __name__ == "__main__":
    main()
