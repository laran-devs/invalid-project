import sys
from .parser import build_parser
from .commands import handle_convert, handle_validate, handle_stats


def cli() -> None:
    parser = build_parser()
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    if args.command == "convert":
        sys.exit(handle_convert(args))
    elif args.command == "validate":
        sys.exit(handle_validate(args))
    elif args.command == "stats":
        sys.exit(handle_stats(args))
    else:
        parser.print_help()
        sys.exit(0)


main = cli

__all__ = [
    "build_parser",
    "handle_convert",
    "handle_validate",
    "handle_stats",
    "cli",
    "main",
]
