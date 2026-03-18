"""CLI entry point: uv run python -m writer [options]"""

import argparse
import os



def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m writer")
    parser.add_argument(
        "--seed-doc",
        metavar="EMAIL",
        default=None,
        help="Create/reset seed document assigned to this user email on startup",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", default=True)
    parser.add_argument("--no-reload", action="store_true")
    args = parser.parse_args()

    if args.seed_doc:
        os.environ["DEV_SEED_DOC_EMAIL"] = args.seed_doc
    os.environ["WRITER_PORT"] = str(args.port)

    import uvicorn

    uvicorn.run(
        "writer.main:app",
        host=args.host,
        port=args.port,
        reload=not args.no_reload,
    )


if __name__ == "__main__":
    main()
