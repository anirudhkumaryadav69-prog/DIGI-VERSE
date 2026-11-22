import os
import sys
from pathlib import Path

import uvicorn

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    os.chdir(BACKEND_ROOT)
    root_str = str(BACKEND_ROOT)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    existing_pypath = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = f"{root_str}{os.pathsep}{existing_pypath}" if existing_pypath else root_str
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, reload_dirs=[root_str])


if __name__ == "__main__":
    main()
