from __future__ import annotations

import os

from .api import create_app

app = create_app()


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(
        "nodetrade.server:app",
        host=os.getenv("NODETRADE_HOST", "127.0.0.1"),
        port=int(os.getenv("NODETRADE_PORT", "8000")),
        reload=False,
    )
