from enum import StrEnum
from pathlib import Path

import scanpy as sc
from anndata import AnnData


class Format(StrEnum):
    H5AD = "h5ad"
    H5 = "10x-h5"
    MTX = "10x-mtx"
    TEXT = "text"


def check_format(path: Path) -> Format:
    if path.is_dir():
        if list(path.glob("*matrix.mtx*")):
            return Format.MTX
        raise ValueError(f"Cannot infer format from directory: {path}")

    suffixes = path.suffixes
    if suffixes == [".h5ad"]:
        return Format.H5AD
    if suffixes == [".h5"]:
        return Format.H5
    if ".txt" in suffixes:
        return Format.TEXT
    raise ValueError(f"Unable to infer the format of {path}")


def load_h5ad(path: Path) -> AnnData:
    return sc.read_h5ad(path)


def load_h5(path: Path, genome: str | None) -> AnnData:
    return sc.read_10x_h5(path, genome=genome, gex_only=True)


def load_mtx(folder: Path, prefix: str| None) -> AnnData:
    return sc.read_10x_mtx(
        folder,
        var_names="gene_symbols",
        make_unique=True,
        cache=False,
        gex_only=True,
        prefix=prefix
    )


def load_txt(path: Path, delimiter: str | None, transpose: bool) -> AnnData:
    data = sc.read_text(
        path,
        delimiter=delimiter
    )
    if transpose:
        data = data.T
    return data