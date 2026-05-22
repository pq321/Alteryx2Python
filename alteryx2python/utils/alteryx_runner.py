from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil


@dataclass(slots=True)
class AlteryxRunner:
    designer_executable: str = "AlteryxEngineCmd.exe"

    def available(self) -> bool:
        return shutil.which(self.designer_executable) is not None

    def run_workflow(self, workflow_path: Path) -> Path:
        if not self.available():
            raise RuntimeError("Alteryx command-line engine is not available in this environment")
        return workflow_path