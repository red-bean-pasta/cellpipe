import logging
import os
from pathlib import Path

import scanpy as sc
from anndata import AnnData

logger = logging.getLogger(__name__)


def check_cache_metadata(data: AnnData, key: str, **kwargs) -> bool | None:
    meta = data.uns.get(key)
    if not meta:
        logger.debug(f"Metadata validation skipped: Cannot find metadate '{key}'")
        return None
    if not isinstance(meta, dict):
        logger.error(f"Unexpected metadata format: {type(meta)}: {meta}")
        logger.warning("Overwriting invalid metadata...")
        data.uns[key] = {}
        return False
    for k, v in kwargs.items():
        if meta.get(k) != v:
            logger.debug(f"Metadata validation failed for '{k}': {meta.get(k)}: {v}")
            return False
    return True


def cache_with_metadata(path: Path, data: AnnData, key: str, **kwargs) -> None:
    data.uns[key] = kwargs
    _save_cache(data, path)


# Obsolete
def _read_cache(path: Path | str) -> AnnData | None:
    """

    :param path: .h5ad file path
    :return:
    """
    return sc.read_h5ad(path) if Path(path).exists() else None


def _save_cache(data: AnnData, path: Path | str) -> None:
    normalized_path = Path(path)
    tmp_path = normalized_path.with_suffix('.tmp')
    data.write(tmp_path, compression='lzf')
    os.replace(tmp_path, normalized_path)