"""Pytest config: add project root to path so tests can import extract, tables_to_excel."""
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))
