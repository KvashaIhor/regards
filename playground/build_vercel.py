"""Assembles build/vercel: the playground, regards.py and the examples, ready for `vercel deploy`.

Vercel installs dependencies from pyproject.toml whenever there is one, and the regards package's
pyproject.toml rightly has none. So the playground deploys from its own folder, with app.py at the
top and Flask in requirements.txt.

    python3 playground/build_vercel.py
    cd build/vercel && vercel deploy --prod
"""

import shutil
from pathlib import Path

PLAYGROUND = Path(__file__).resolve().parent
ROOT = PLAYGROUND.parent
OUT = ROOT / "build" / "vercel"


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    shutil.copytree(PLAYGROUND, OUT, ignore=shutil.ignore_patterns(
        "tests", "__pycache__", "*.pyc", "build_vercel.py", ".vercel"))
    shutil.copy2(ROOT / "regards.py", OUT / "regards.py")
    shutil.copytree(ROOT / "examples", OUT / "examples")
    if (ROOT / ".vercel").is_dir():
        shutil.copytree(ROOT / ".vercel", OUT / ".vercel")  # deploy to the already-linked project
    print(OUT)


if __name__ == "__main__":
    main()
