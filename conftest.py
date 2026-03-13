"""Root conftest — ensures src/ is on the Python path."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
