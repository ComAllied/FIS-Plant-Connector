"""Run the built frontend with a fresh synthetic graph for browser tests."""

from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn

from fis_twin.cli import write_json
from fis_twin.demo import write_demo
from fis_twin.discovery import discover
from fis_twin.mapping import load_mapping
from fis_twin.web import create_app


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    with TemporaryDirectory() as directory:
        workspace = Path(directory)
        write_demo(workspace)
        graph = workspace / "graph.json"
        write_json(graph, discover([workspace], load_mapping(root / "config/mapping.example.yaml")))
        uvicorn.run(create_app(graph, root / "frontend/dist"), host="127.0.0.1", port=4173)
