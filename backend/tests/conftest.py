"""Shared test fixtures."""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Add finance-automation to path
_fa = Path(__file__).parent.parent.parent / "finance-automation"
if _fa.exists():
    sys.path.insert(0, str(_fa))
