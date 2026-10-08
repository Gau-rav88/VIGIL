from __future__ import annotations

import uvicorn
from simulator.server import app


def main() -> None:
    uvicorn.run("simulator.server:app", host="0.0.0.0", port=8090, loop="uvloop")


if __name__ == "__main__":
    main()
