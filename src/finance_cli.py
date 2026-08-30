"""Command-line interface for the personal finance agent.

Entry point: finance-agent (defined in pyproject.toml [project.scripts]).

Commands:
  chat --user-id N     Start an interactive finance chat as user N.
                       --verbose prints each tool call as it happens.
                       --new     starts a fresh conversation (ignores history).

The database is shared with the support agent (same tasklet.db). Run
`support-agent init-db` first to create the database and load demo data.

Demo prompts to try:
  "How much did I spend on food last month?"
  "Show my transactions from Amazon."
  "What were my biggest expenses this month?"
  "List my income transactions this year."
  "How much did I spend on transport vs entertainment?"
"""

import argparse

from anthropic import Anthropic

from src.conversation import Conversation
from src.db import get_connection
from src.finance_agent import run_finance_turn


def cmd_chat(args) -> None:
    client = Anthropic()
    conn = get_connection()

    if args.new:
        conversation = Conversation.new(conn, args.user_id)
    else:
        conversation = Conversation.load_or_create(conn, args.user_id)

    print(f"Finance agent — user {args.user_id}. Type 'quit' to exit.\n")

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

        result = run_finance_turn(
            client=client,
            conn=conn,
            conversation=conversation,
            user_input=user_input,
            on_tool_call=on_tool if args.verbose else None,
        )
        print(f"Agent: {result.final_text}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="finance-agent",
        description="Personal finance agent CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    chat_parser = subparsers.add_parser(
        "chat",
        help="Start an interactive finance chat session",
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
