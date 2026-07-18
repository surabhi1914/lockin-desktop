"""LockIn desktop entry point with preserved Phase 0 bootstrap flags."""

import sys
from pathlib import Path

from app.application import run
from app.bootstrap import main as bootstrap_main
from app.health import run_health_check
from app.version import __version__


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments == ["--version"]:
        print(f"LockIn {__version__}")
        return 0
    if "--health-check-output" in arguments:
        index = arguments.index("--health-check-output")
        if index + 1 >= len(arguments):
            print("--health-check-output requires a JSON path", file=sys.stderr)
            return 2
        return run_health_check(Path(arguments[index + 1]))
    if "--phase0-bootstrap" in arguments or "--check-only" in arguments:
        return bootstrap_main(arguments)
    return run(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
