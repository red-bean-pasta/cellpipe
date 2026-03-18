import argparse
import datetime
import logging
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

import matplotlib
import scanpy as sc
from anndata import AnnData

from cellpipe import annotater, celltypist_annotater
from cellpipe import processor
from cellpipe import source_loader, cache_handler, marker_parser
from cellpipe import summarizer, visualizer
from cellpipe.annotater import AnnotationConfig
from cellpipe.meta import MODULE_NAME, PIPELINE_VERSION
from cellpipe.source_loader import Format


logger = logging.getLogger(__name__)


pipeline_meta_key: str = "pipeline_version"

fresh_backup_layer: str = "counts"

normalize_key: str = "size_factor"
leiden_key: str = "leiden"
annotation_key: str = "cell_type"
celltypist_prefix: str = "celltypist_"


def run(args: argparse.Namespace):
    matplotlib.use('svg')
    sc.settings.figdir = args.output
    sc.set_figure_params(figsize=(8, 6), dpi=300, transparent=True, format="svg")

    logger.debug("Loading source dataset...")
    data = _load_source(args)
    markers = marker_parser.parse(args.marker_file, args.marker)
    logger.debug(f"Merged markers: {markers}")

    logger.debug("Performing preprocess...")
    data, ran = _filter_normalize_and_cache(data, args)
    logger.debug("Selecting highly variable genes...")
    data, ran = _hvg_and_cache(data, args, ran)
    logger.debug("Computing principal components...")
    data, ran = _pca_and_cache(data, args, ran)
    logger.debug("Building neighborhood graph with KNN...")
    data, ran = _neighbor_and_cache(data, args, ran)
    logger.debug("Clustering with LEIDEN...")
    data, ran = _leiden_and_cache(data, args, ran)
    logger.debug("Reducing dimensionality with UMAP...")
    data, ran = _umap_and_cache(data, args, ran)
    logger.debug("Annotating cell types...")
    _annotate(data, markers, args)
    logger.debug("Drawing output plots...")
    _visualize(data, markers, args)
    logger.debug("Summarizing for target genes if applicable...")
    _summarize(data, args)
    logger.info("All done!")


def _load_source(args) -> AnnData:
    path = args.source
    fmt = Format(args.source_format.lower() if args.source_format else source_loader.check_format(path))

    if fmt == Format.H5:
        return source_loader.load_h5(path, args.h5_genome)
    if fmt == Format.H5AD:
        return source_loader.load_h5ad(path)
    if fmt == Format.MTX:
        return source_loader.load_mtx(path, args.mtx_prefix)
    if fmt == Format.TEXT:
        return source_loader.load_txt(path, args.text_delimiter, not args.text_no_transpose)
    raise ValueError(f"Unexpected format: {fmt}")


def _filter_normalize_and_cache(
        data: AnnData,
        args: argparse.Namespace
) -> tuple[AnnData, bool]:
    key = "preprocess"
    metadata = {
        "filter_min_genes": args.filter_min_genes,
        "filter_min_cells": args.filter_min_cells,
        "normalize_sum": args.normalize_sum,
        "normalize_key_added": normalize_key,
    }
    valid = _check_cache(data, key, **metadata)
    if valid is False:
        raise ValueError("Cannot recompute filtering or normalization from cached source. Please rerun with the original data.")
    _log_cache_validation(valid, key)
    if not valid: # valid is None
        logger.debug("Filtering low quality cells and genes...")
        processor.filter_cells_and_genes(data, args.filter_min_genes, args.filter_min_cells)
        logger.debug("Normalize cell numbers...")
        processor.normalize_and_log_transform(data, args.normalize_sum, normalize_key)
        logger.debug("Backing up raw data...")
        data.raw = data.copy()  # Backup raw data
    _try_cache(args.save_h5ad, data, key, **metadata, source=Path(args.source).name)
    return data, not valid


def _hvg_and_cache(
        data: AnnData,
        args: argparse.Namespace,
        reran: bool
) -> tuple[AnnData, bool]:
    key = "hvg"
    metadata = {
        "n_top_genes": args.n_hvg,
        "scale_max": args.hvg_scale_max,
    }
    if _check_cache(data, key, **metadata) is False:
        data = data.raw.to_adata()
        data.raw = data.copy()
    return _check_run_cache(
        data,
        reran,
        key,
        metadata,
        processor.select_variable_genes_and_scale,
        args.save_h5ad
    )


def _pca_and_cache(
        data: AnnData,
        args: argparse.Namespace,
        reran: bool
) -> tuple[AnnData, bool]:
    metadata = {
        "n_comps": args.n_pcs,
    }
    return _check_run_cache(
        data,
        reran,
        "pca",
        metadata,
        processor.compute_principal_components,
        args.save_h5ad
    )


def _neighbor_and_cache(
        data: AnnData,
        args: argparse.Namespace,
        reran: bool,
) -> tuple[AnnData, bool]:
    metadata = {
        "n_neighbors": args.n_neighbors,
        "n_pcs": args.n_pcs,
    }
    return _check_run_cache(
        data,
        reran,
        "neighbors",
        metadata,
        processor.build_neighbor_graph,
        args.save_h5ad
    )


def _leiden_and_cache(
        data: AnnData,
        args: argparse.Namespace,
        reran: bool
) -> tuple[AnnData, bool]:
    metadata = {
        "resolution": args.leiden_resolution,
        "random_state": args.leiden_seed,
        "key_added": leiden_key
    }
    return _check_run_cache(
        data,
        reran,
        "leiden",
        metadata,
        processor.build_leiden_graph,
        args.save_h5ad
    )


def _umap_and_cache(
        data: AnnData,
        args: argparse.Namespace,
        reran: bool,
) -> tuple[AnnData, bool]:
    metadata = {
        "min_dist": args.umap_min_dist,
        "spread": args.umap_spread,
        "random_state": args.umap_seed
    }
    return _check_run_cache(
        data,
        reran,
        "umap",
        metadata,
        processor.build_umap_graph,
        args.save_h5ad
    )


def _annotate(
        data: AnnData,
        markers: dict[str, set[str]],
        args: argparse.Namespace
) -> None:
    annotation_config = AnnotationConfig(
        cluster_key=leiden_key,
        label_key=annotation_key,
        min_score=args.annot_min_score,
        min_margin=args.annot_min_margin,
    )
    logger.debug("Annotating using provided markers...")
    annotater.annotate_cell_types(data, markers, annotation_config)

    if not args.celltypist_model:
        return
    logger.debug(f"Annotating with CellTypist using model {args.celltypist_model}...")
    if data.raw.n_obs >= 50000:
        logger.warning(f"Running CellTypist on large dataset with {data.raw.n_obs} cells requires substantial RAM and may get killed when the system run out of memory")
    if args.celltypist_majority_voting:
        logger.info("Running CellTypist with majority voting enabled. This significantly increase memory usage on large datasets")
    celltypist_annotater.annotate_with_celltypist(
        data,
        args.celltypist_model,
        args.celltypist_majority_voting,
        prefix=celltypist_prefix
    )


def _visualize(
        data: AnnData,
        markers: dict[str, set[str]],
        args: argparse.Namespace
) -> None:
    logger.debug("Drawing cluster overviews...")
    visualizer.draw_cluster_overview(data, markers, leiden_key)
    logger.debug("Drawing annotation overviews...")
    visualizer.draw_annotation_overview(data, markers, annotation_key)
    if args.celltypist_model:
        logger.debug("Drawing celltypist overviews...")
        visualizer.draw_celltypist_overview(data, celltypist_prefix)
    if args.target_genes:
        logger.debug("Drawing overviews for target genes...")
        visualizer.draw_target_gene_figures(data, args.target_genes, annotation_key, args.smooth_umap)


def _summarize(
        data: AnnData,
        args: argparse.Namespace
) -> None:
    if args.target_genes:
        logger.debug("Summarizing grouped by cell types...")
        summarizer.summarize_target_genes(data, args.target_genes, annotation_key, args.output) # by cell type
        logger.debug("Summarizing grouped by cluster indices")
        summarizer.summarize_target_genes(data, args.target_genes, leiden_key, args.output) # by leiden


def _check_run_cache(
    data: AnnData,
    reran: bool,
    key: str,
    metadata: dict,
    func: Callable,
    cache_path: str | Path | None,
) -> tuple[AnnData, bool]:
    valid = _check_cache(data, key, **metadata)
    recompute = reran or not valid
    _log_cache_validation(
        None if valid is None else True if not reran and valid else False,
        key
    )
    if recompute:
        func(data, **metadata)
    _try_cache(cache_path, data, key, **metadata)
    return data, recompute


def _check_cache(data: AnnData, key: str, **kwargs) -> bool | None:
    field = f"{MODULE_NAME}_{key}"
    return cache_handler.check_cache_metadata(data, field, **kwargs, pipeline_meta_key = PIPELINE_VERSION)


def _try_cache(path: Path | None, data: AnnData, key: str, **kwargs) -> None:
    if not path:
        return
    logger.debug(f"Caching process '{key}' result...")
    cache_handler.cache_with_metadata(
        path,
        data,
        f"{MODULE_NAME}_{key}",
        **kwargs,
        pipeline_meta_key = PIPELINE_VERSION,
        timestamp = datetime.datetime.now(tz=ZoneInfo("UTC")).isoformat()
    )


def _log_cache_validation(result: bool | None, name: str) -> None:
    if result:
        logger.debug(f"Skipping running process '{name}' on valid cache...")
    elif result is None:
        logger.debug(f"Running process '{name}' on fresh data...")
    else:
        logger.debug(f"Rerunning process '{name}' on parameter change...")

