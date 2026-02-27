from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Dict, List, Optional, Union


class ManifestGenerator:
    """Generates a build manifest for the generated artifacts."""

    def __init__(self, dist_path: Path):
        self.dist_path = dist_path
        self.artifacts: List[Dict] = []
        self._lock = threading.Lock()

    def add_artifact(
        self,
        name: str,
        artifact_type: str,
        path: Union[Path, str],
        metadata: Optional[Dict] = None,
    ) -> None:
        if isinstance(path, Path) and path.is_absolute():
            try:
                display_path = str(path.relative_to(self.dist_path.absolute()))
            except ValueError:
                display_path = str(path)
        else:
            display_path = str(path)

        with self._lock:
            self.artifacts.append(
                {
                    "name": name,
                    "type": artifact_type,
                    "path": display_path,
                    "metadata": metadata or {},
                }
            )

    def save(self) -> None:
        manifest_path = self.dist_path / "build_manifest.json"
        with open(manifest_path, "w") as f:
            json.dump({"artifacts": self.artifacts}, f, indent=2)
        print(f"Manifest saved to: {manifest_path}")
