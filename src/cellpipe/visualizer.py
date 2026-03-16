import logging
from pathlib import Path

import numpy as np
import scanpy as sc
from anndata import AnnData

from cellpipe import celltypist_annotater

logger = logging.getLogger(__name__)


def draw_cluster_overview(
        data: AnnData,
        marker_sets: dict[str, set[str]],
        cluster_column: str,
) -> None:
    _draw_umap(data, cluster_column, "on data")
    _draw_dotplot(data, marker_sets, cluster_column)


def draw_annotation_overview(
        data: AnnData,
        marker_sets: dict[str, set[str]],
        label_key: str,
) -> None:
    _draw_umap(data, label_key)
    _draw_dotplot(data, marker_sets, label_key)


def draw_celltypist_overview(
        data: AnnData,
        prefix: str
) -> None:
    Columns = celltypist_annotater.Columns
    for c in [Columns.LABEL, Columns.CLUSTER, Columns.MAJORITY_VOTING]:
        key = prefix + c
        if key in data.obs.columns:
            _draw_umap(data, key)


def draw_target_gene_figures(
        data: AnnData,
        target_genes: set[str],
        group_key: str,
        draw_smoothed: bool = False,
        use_raw: bool = True,
) -> None:
    source = data.raw if use_raw and data.raw is not None else data
    for gene in target_genes:
        if gene not in source.var_names:
            logger.warning(f"Skipped {gene}: Not found in dataset")
            continue

        _draw_umap(data, gene, use_raw=True)
        sc.pl.violin(
            data,
            keys=gene,
            groupby=group_key,
            stripplot=False,
            use_raw=use_raw,
            show=False,
        ).figure.savefig(_get_save_path(f"violin_{gene}.svg"))
        if draw_smoothed:
            draw_smoothed_target_gene_umap(data, gene, use_raw)


def draw_smoothed_target_gene_umap(
    data: AnnData,
    target_gene: str,
    use_raw: bool = True,
) -> None:
    source = data.raw if use_raw and data.raw is not None else data
    connectivity = data.obsp["connectivities"]
    expression = source[:, target_gene].X
    expression = expression.toarray() if hasattr(expression, "toarray") else np.asarray(expression)

    # For each cell, neighbors expression level * connectivity weight / total connectivity weight
    smoothed = connectivity.dot(expression).ravel() / np.asarray(connectivity.sum(axis=1)).ravel()

    column_name = f"{target_gene}_smoothed"
    data.obs[column_name] = smoothed
    _draw_umap(data, column_name, vmin=0, vmax="p99")


def _draw_umap(
        data: AnnData,
        key: str,
        legend_location="right margin",
        cmap="magma",
        **kwargs
) -> None:
    sc.pl.umap(
        data,
        color=key,
        alpha=0.4,
        legend_loc=legend_location,
        cmap=cmap,
        show=False,
        **kwargs
    ).figure.savefig(
        _get_save_path(f"umap_{key}.svg"),
        bbox_inches="tight"
    )


def _draw_dotplot(
    data: AnnData,
    var_names: str | list[str] | set[str] | dict[str, set[str]],
    group_by: str | list[str],
    **kwargs
) -> None:
    sc.pl.dotplot(
        data,
        var_names,
        groupby=group_by,
        standard_scale="var",
        show=False,
        return_fig=True,
        **kwargs
    ).savefig(str(_get_save_path(f"dotplot_{group_by}.svg")))


def _get_save_path(name: str) -> Path:
    return sc.settings.figdir / name