"""Allow ``python -m lsl_viewer`` execution."""
from lsl_viewer.cli import app

if __name__ == "__main__":
    raise SystemExit(app())
