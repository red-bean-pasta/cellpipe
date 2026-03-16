import logging
from enum import StrEnum
from pathlib import Path

from anndata import AnnData


logger = logging.getLogger(__name__)


class Columns(StrEnum):
    LABEL = "predicted_labels"
    CONFIDENCE = "conf_score"
    CLUSTER = "over_clustering" # Only when majority voting is enabled
    MAJORITY_VOTING = "majority_voting"


def annotate_with_celltypist(
        data: AnnData,
        model: str | Path,
        majority_voting: bool = False,
        use_raw: bool = True,
        prefix: str = "celltypist_",
) -> None:
    """
    Annotate cell types using CellTypist
    Stored in data.obs[{prefix}_label], [{prefix}_confidence] and [{prefix}_majority_voting]
    :param data:
    :param model: CellTypist model path
    :param use_raw:
    :param majority_voting: Whether to aggregate predictions using cluster majority voting
    :param prefix: Prefix for predicted columns before adding to `data`
    :return:
    """
    try:
        import celltypist
    except ImportError:
        raise RuntimeError("CellTypist not installed. Install it first to use it")

    raw = data.raw.to_adata() if use_raw and data.raw is not None else data
    prediction = celltypist.annotate(
        raw,
        model=str(model),
        mode="best match",
        majority_voting=majority_voting,
    )
    annotated = prediction.to_adata(
        insert_labels=True,
        insert_conf=True,
        insert_prob=False,
        prefix=prefix,
    )
    for c in Columns:
        key = prefix + c
        if key in annotated.obs.columns:
            data.obs[key] = annotated.obs[key]