"""Run repository tests with fake or disposable loopback services."""

from pathlib import Path
import sys
import unittest


def main():
    """Discover from any current directory and return a useful exit status."""
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    suite = unittest.defaultTestLoader.discover(str(root / "test"), pattern="test_*.py")
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
