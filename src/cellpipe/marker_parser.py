import json
from pathlib import Path


def parse(
        marker_file: Path | None,
        marker_args: list[list[str]] | None
) -> dict[str, set[str]]:
    result = {m[0]: set(m[1:]) for m in marker_args or []}
    if marker_file:
        with marker_file.open("r") as f:
            file_markers = json.load(f)
        for cell, genes in file_markers.items():
            if genes is None:
                genes = []
            elif isinstance(genes, str):
                genes = [genes]
            if not isinstance(genes, list) or any(not isinstance(g, str) for g in genes):
                raise ValueError(f"Unexpected marker genes in {marker_file}: {genes}")
            result.setdefault(cell, set()).update(genes)
    return result