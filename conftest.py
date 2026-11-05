"""保证裸 `pytest` 与 `python -m pytest` 都能找到 agent 包。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
