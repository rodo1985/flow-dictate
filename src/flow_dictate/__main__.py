"""Module entrypoint for ``python -m flow_dictate``."""

from __future__ import annotations

from flow_dictate.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
