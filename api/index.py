import os
import sys
from pathlib import Path

# Vercel executes this file from the repository root. Make the src-layout
# package importable without requiring a local editable install.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Vercel's deployed filesystem is not a persistent writable working directory.
# Keep the current SQLite implementation alive for the function using /tmp.
os.environ.setdefault("NODETRADE_DB", "/tmp/nodetrade.db")

from nodetrade.server import app
