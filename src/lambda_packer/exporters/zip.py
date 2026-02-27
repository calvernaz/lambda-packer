"""Deterministic ZIP creation utility."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path


class ZipExporter:
    """
    Creates deterministic ZIP files from a directory.
    
    A ZIP is deterministic if its contents and their metadata (timestamps, permissions)
    are identical for every run on the same source code.
    """

    def __init__(
        self, deterministic_timestamp: int = 315532800
    ):  # Default: 1980-01-01 00:00:00
        self.deterministic_timestamp = deterministic_timestamp

    def export(self, src_dir: Path, dest_zip: Path) -> None:
        """
        Compresses a directory into a reproducible ZIP file.
        
        This method:
        1. Sorts files alphabetically.
        2. Sets a fixed timestamp (1980-01-01) for all entries.
        3. Preserves Unix file permissions (important for executables).
        """
        dest_zip.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            # os.walk is not guaranteed to be sorted, so we sort explicitly.
            for root, dirs, files in os.walk(src_dir):
                dirs.sort()
                files.sort()

                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(src_dir)

                    # Create a ZipInfo object with a fixed date to ensure determinism.
                    zinfo = zipfile.ZipInfo(
                        str(arcname), date_time=(1980, 1, 1, 0, 0, 0)
                    )

                    # Preserve Unix permissions (bits 16-31 of external_attr).
                    st = os.stat(file_path)
                    zinfo.external_attr = (st.st_mode & 0xFFFF) << 16
                    zinfo.compress_type = zipfile.ZIP_DEFLATED

                    with open(file_path, "rb") as f:
                        zf.writestr(zinfo, f.read())

        print(f"Exported ZIP: {dest_zip}")
