import os
from pathlib import Path

from .api import create_app

app = create_app()

# Serve the existing public dashboard without exposing internal API controls.
_dashboard_dir = Path(__file__).resolve().parents[2] / "dashboard" / "public"
if _dashboard_dir.is_dir():
    from fastapi.staticfiles import StaticFiles
    app.mount("/dashboard", StaticFiles(directory=str(_dashboard_dir), html=True), name="dashboard")


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(
        "nodetrade.server:app",
        host=os.getenv("NODETRADE_HOST", "127.0.0.1"),
        port=int(os.getenv("NODETRADE_PORT", "8000")),
        reload=False,
    )
