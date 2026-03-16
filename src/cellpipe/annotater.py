import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
import scanpy as sc
from anndata import AnnData


score_suffix = "_score"

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AnnotationConfig:
    cluster_key: str
    label_key: str = "cell_type"
    min_score: float = 0.05
    min_margin: float = 0.05
    no_candidate_label: str = "Unknown: No candidate"
    use_raw: bool = True


def annotate_cell_types(
    data: AnnData,
    markers: dict[str, set[str]],
    config: AnnotationConfig,
) -> None:
    """Annotate clusters using marker-gene scoring and cluster-level score aggregation."""
    present, missing = _find_available_markers(data, markers, use_raw=config.use_raw)
    for cell in [cell for cell, genes in present.items() if not genes]:
        logger.warning(f"{cell}: No usable marker genes defined")
    for cell, genes in missing.items():
        if genes: logger.warning(f"{cell}: Missing marker genes in database: {genes}")

    markable_sets = {k: v for k, v in present.items() if v}
    logger.debug(f"Annotating marked cells: {markable_sets.keys()}...")
    logger.debug("Scoring all marker cells' genes for each cell...")
    score_columns = _score_marker_sets(
        data,
        markable_sets,
        use_raw=config.use_raw,
    )
    logger.debug(f"Summarizing scores by cluster column {config.cluster_key}...")
    cluster_scores = _summarize_scores_by_cluster(
        data,
        cluster_key=config.cluster_key,
        score_columns=score_columns,
    )
    logger.debug("Assigning possible cell labels to each cluster...")
    cluster_labels = _assign_cluster_labels(
        cluster_scores,
        min_score=config.min_score,
        score_margin=config.min_margin,
        no_candidate_label=config.no_candidate_label,
    )

    logger.debug("Assigning labeled cells to each cells in database...")
    data.obs[config.label_key] = data.obs[config.cluster_key].map(cluster_labels)
    logger.debug("Saving annotation analysis results...")
    data.uns[f"{config.label_key}_scores"] = cluster_scores
    data.uns[f"{config.label_key}_labels"] = cluster_labels.to_dict()


def _find_available_markers(
    data: AnnData,
    markers: dict[str, set[str]],
    use_raw: bool = True,
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """
    Split genes into present and missing for all defined markers in database
    :param data:
    :param markers:
    :param use_raw:
    :return:
    """
    present: dict[str, set[str]] = {}
    missing: dict[str, set[str]] = {}
    var_names = data.raw.var_names if use_raw and data.raw is not None else data.var_names
    for cell_type, genes in markers.items():
        present[cell_type] = set(g for g in genes if g in var_names)
        missing[cell_type] = set(g for g in genes if g not in var_names)
    return present, missing


def _score_marker_sets(
    data: AnnData,
    markers: dict[str, set[str]],
    use_raw: bool = True,# Assign annotated label ba
) -> list[str]:
    """
    Score the expression of marker genes as a whole in each set for all database cells
    :param data:
    :param markers: dict[cell, set[genes]]
    :param use_raw:
    :return: Names of created columns
    """
    created_scores: list[str] = []
    for cell_type, genes in markers.items():
        if not genes: continue
        score_name = cell_type + score_suffix
        sc.tl.score_genes( # Score samples all present genes in database first and divide them into "bins" based on expression level. Then for each marker gene, randomly select multiple genes as samples from corresponding bins. Finally, score based on `mean(all marker genes) − mean(picked sample genes)`
            data,
            gene_list=list(genes),
            score_name=score_name,
            use_raw=use_raw,
            ctrl_as_ref=False,
            random_state=0
        )
        created_scores.append(score_name)
    return created_scores


def _summarize_scores_by_cluster(
    data: AnnData,
    cluster_key: str,
    score_columns: list[str],
) -> pd.DataFrame:
    """
    Group all cells in database by cluster and average all score columns
    :param data:
    :param cluster_key:
    :param score_columns:
    :return:
    """
    return data.obs \
        .groupby(
            cluster_key,
            observed=True # Preserve only groups with rows
         )[list(score_columns)] \
        .mean()


def _assign_cluster_labels(
        cluster_scores: pd.DataFrame,
        min_score: float = 0.05,
        score_margin: float = 0.05,
        no_candidate_label: str = "Unknown: No candidate",
) -> pd.Series:
    """

    :param cluster_scores:
    :param min_score:
        Minimum score for a label to be considered valid,
        in case all labels scored too low,
        and the difference only comes from noise
    :param score_margin:
        Minimum margin between labels' scores to consider not tied,
        in case the difference is caused by noise
    :param no_candidate_label:
        Used when all labels scored under min_score
    :return:
    """
    result = []
    columns = np.array(cluster_scores.columns)
    labels = np.array([c.removesuffix(score_suffix) for c in columns])

    for cluster, row in cluster_scores.iterrows():
        values = row.to_numpy(dtype=float)

        logger.debug(f"Cluster {cluster}: Sorting scores...")
        order = np.argsort(values)[::-1]
        sorted_values = values[order]
        sorted_labels = labels[order]
        top_value = sorted_values[0]
        top_label = sorted_labels[0]

        logger.debug(f"Cluster {cluster}: Applying minium score requirements...")
        condition = sorted_values >= min_score
        qualified_values = sorted_values[condition]
        qualified_labels = sorted_labels[condition]

        if qualified_values.size == 0:
            logger.warning(f"Cluster '{cluster}': Unable to label: No candidate, with highest score {top_value} from {top_label}' still lower than minimum requirement {min_score}")
            result.append(no_candidate_label)
            continue

        logger.debug(f"Cluster {cluster}: Evaluating candidates labels...")
        candidate_labels = [top_label]
        for label, value in zip(qualified_labels[1:], qualified_values[1:]):
            if top_value - value >= score_margin:
                break
            candidate_labels.append(label)
        joined_label = " or ".join(candidate_labels)
        logger.info(f"Cluster '{cluster}': Assigned with label '{joined_label}': { {label: float(value) for label, value in zip(candidate_labels, qualified_values)} }",)
        result.append(joined_label)

    return pd.Series(result, index=cluster_scores.index)