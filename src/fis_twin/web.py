"""Serve the current local graph and the built frontend."""

import json
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles


def create_app(graph_path: Path, frontend: Path) -> FastAPI:
    app = FastAPI(title="FIS Production Network", docs_url=None, redoc_url=None)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/topology")
    def topology(request: Request) -> Response:
        try:
            with graph_path.open(encoding="utf-8") as source:
                graph = json.load(source)
            if (
                not isinstance(graph, dict)
                or graph.get("schemaVersion") != "1.0"
                or not isinstance(graph.get("topologyId"), str)
                or not isinstance(graph.get("nodes"), list)
                or not isinstance(graph.get("edges"), list)
            ):
                raise ValueError
            version = graph["topologyId"]
            if len(version) != 64 or any(char not in "0123456789abcdef" for char in version):
                raise ValueError
        except (OSError, ValueError):
            return JSONResponse({"detail": "No readable graph. Run discovery first."}, status_code=503)
        headers = {"ETag": f'"{version}"', "Cache-Control": "private, no-cache"}
        if request.headers.get("if-none-match") == headers["ETag"]:
            return Response(status_code=304, headers=headers)
        return JSONResponse(graph, headers=headers)

    app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app
