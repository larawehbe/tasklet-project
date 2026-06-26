"""Command-line interface for the Tasklet support agent.

Entry point: support-agent (defined in pyproject.toml [project.scripts]).

Commands:
  init-db              Wipe and recreate the database with demo data.
  chat --user-id N     Start an interactive support chat as user N.
                       --verbose prints each tool call as it happens.
                       --new     starts a fresh conversation (ignores history).
"""

import argparse
import sys

from anthropic import Anthropic

from src import agent
from src.conversation import Conversation
from src.db import get_connection, init_db


def cmd_init_db(_args) -> None:
    print("Initializing database — this will wipe data/tasklet.db...")
    init_db(seed=True)
    print("Done. Demo data loaded.")


def cmd_chat(args) -> None:
    client = Anthropic()
    conn = get_connection()

    if args.new:
        conversation = Conversation.new(conn, args.user_id)
    else:
        conversation = Conversation.load_or_create(conn, args.user_id)

    print(f"Tasklet support — user {args.user_id}. Type 'quit' to exit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "bye"):
            break

        def on_tool(tu, tr):
            status = "error" if tr.is_error else "ok"
            print(f"  [tool] {tu.name}({tu.input}) → {status}")

        result = agent.run_turn(
            client=client,
            conn=conn,
            conversation=conversation,
            user_input=user_input,
            on_tool_call=on_tool if args.verbose else None,
        )
        print(f"Agent: {result.final_text}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="support-agent",
        description="Tasklet support agent CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init-db",
        help="Initialize (or reset) the database with demo data",
    )
    init_parser.set_defaults(func=cmd_init_db)

    chat_parser = subparsers.add_parser(
        "chat",
        help="Start an interactive support chat session",
    )
    chat_parser.add_argument("--user-id", type=int, required=True, metavar="N")
    chat_parser.add_argument(
        "--verbose", action="store_true", help="Print tool calls"
    )
    chat_parser.add_argument(
        "--new", action="store_true", help="Start a fresh conversation"
    )
    chat_parser.set_defaults(func=cmd_chat)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
