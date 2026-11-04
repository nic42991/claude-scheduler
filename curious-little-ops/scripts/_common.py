from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from clops.config import load_secrets  # noqa: E402
from clops.state import State  # noqa: E402


def state_path() -> Path:
    return Path(os.environ.get("CLOPS_STATE_FILE", ROOT / "state.json"))


def load() -> tuple[State, object]:
    return State.load(state_path()), load_secrets()
