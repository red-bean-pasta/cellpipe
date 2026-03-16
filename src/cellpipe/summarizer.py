import logging
from pathlib import Path

import numpy as np
import pandas as pd
from anndata import AnnData


logger = logging.getLogger(__name__)


def summarize_target_genes(
    data: AnnData,
    target_genes: set[str],
    group_key: str,
    output_folder: Path,
    use_raw: bool = True,
) -> None:
    var_names = data.raw.var_names if data.raw is not None else data.var_names

    for gene in target_genes:
        if gene not in var_names:
            logger.warning(f"Skipping {gene}: gene not found in dataset")
            continue

        x = data.raw[:, gene].X if use_raw and data.raw is not None else data[:, gene].X
        x = np.asarray(x.todense()).ravel() if hasattr(x, "todense") else np.asarray(x).ravel() # Scanpy may store data in sparse matrix to save disk usage. Yet Numpy requires it to be dense.
        tmp = pd.DataFrame(
            {
                group_key: data.obs[group_key].to_numpy(),
                "expression": x,
                "is_positive": (x > 0).astype(int),
            },
            index=data.obs_names,
        )
        summary = tmp \
            .groupby(group_key, observed=True)[["expression", "is_positive"]] \
            .agg(
                mean_expression=("expression", "mean"),
                median_expression=("expression", "median"),
                positive_fraction=("is_positive", "mean"),
                positive_cells=("is_positive", "sum"),
                cell_count=("is_positive", "size")
            )
        summary["positive_fraction"] = (summary["positive_fraction"] * 100).round(1)
        summary = summary.sort_values(
            ["positive_fraction", "median_expression"],
            ascending=False
        )

        output_folder.mkdir(parents=True, exist_ok=True)
        output_file = output_folder / f"{gene}_expression_by_{group_key}.csv"
        summary.to_csv(output_file)
        logger.info(f"Saved summary for {gene} grouped by {group_key} at {output_file}")