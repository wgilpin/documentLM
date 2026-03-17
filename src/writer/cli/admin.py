"""Admin CLI — generate invite codes and reset user passwords.

Usage:
    uv run python -m writer.cli.admin generate-invite [--count N]
    uv run python -m writer.cli.admin reset-password <email> <new_password>
"""

import argparse
import asyncio
import sys

from writer.core.logging import get_logger

logger = get_logger(__name__)


async def _generate_invite(count: int) -> None:
    from writer.core.database import _get_session_factory  # noqa: PLC2701
    from writer.services.auth_service import create_invite_codes

    session_factory = _get_session_factory()
    async with session_factory() as db:
        codes = await create_invite_codes(db, count=count)
        await db.commit()

    for code in codes:
        print(code)


async def _reset_password(email: str, new_password: str) -> None:
    from writer.core.database import _get_session_factory  # noqa: PLC2701
    from writer.services.auth_service import UserNotFoundError, reset_password

    session_factory = _get_session_factory()
    async with session_factory() as db:
        try:
            await reset_password(db, email, new_password)
            await db.commit()
        except UserNotFoundError:
            print(f"Error: no user found with email {email!r}", file=sys.stderr)
            sys.exit(1)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

    print(f"Password reset for {email}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Writer admin CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    invite_parser = sub.add_parser("generate-invite", help="Generate invite codes")
    invite_parser.add_argument(
        "--count", type=int, default=1, help="Number of codes to generate (default: 1)"
    )

    reset_parser = sub.add_parser("reset-password", help="Reset a user's password")
    reset_parser.add_argument("email", help="User email address")
    reset_parser.add_argument("new_password", help="New password (min 8 chars)")

    args = parser.parse_args()

    if args.command == "generate-invite":
        asyncio.run(_generate_invite(args.count))
    elif args.command == "reset-password":
        asyncio.run(_reset_password(args.email, args.new_password))


if __name__ == "__main__":
    main()
