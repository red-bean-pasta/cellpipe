import argparse
from pathlib import Path
from typing import Callable, Sequence

from numpy import uint

from cellpipe import meta


class ExtendedArgumentParser(argparse.ArgumentParser):
    @property
    def validators(self) -> list[Callable[[argparse.Namespace], None]]:
        if not hasattr(self, '_validators'):
            self._validators = []
        return self._validators

    def parse_args(
            self,
            args: Sequence[str] | None = None,
            namespace: None = None
    ) -> argparse.Namespace:
        parsed = super().parse_args(args, namespace)
        self.validate(parsed)
        return parsed

    def validate(self, args: argparse.Namespace) -> None:
        for v in self.validators:
            v(args)


def _get_arg_parser() -> argparse.ArgumentParser:
    parser = ExtendedArgumentParser(
        prog=meta.MODULE_NAME,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description=(
            "A simple single-cell RNA-seq analysis pipeline using Scanpy. "
            "The pipeline"
            "loads an expression matrix, "
            "filters low-quality cells and genes, "
            "normalizes counts and log-transforms the data, "
            "selects highly variable genes, "
            "runs PCA, builds a neighbor graph, clusters cells with Leiden, computes UMAP, "
            "annotates cell types from marker genes and optionally CellTypist, "
            "and writes plots and summary tables"
        ),
        epilog="Provide no argument to invoke the GUI interface if PySide6 is installed",
        exit_on_error=False,
    )

    input = parser.add_argument_group("Input")
    input.add_argument(
        "--source-format",
        choices=["h5ad", "10x-h5", "10x-mtx", "text"],
        help="Input data. Omit to detect automatically"
    )
    input.add_argument(
        "--source",
        type=Path,
        required=True,
        metavar="PATH",
        help="Path to the input data. For 10x-mtx input, it should be the folder containing matrix.mtx, barcodes.tsv and features.tsv"
    )
    input.add_argument(
        "--h5-genome",
        metavar="GENOME",
        help="Genome to analyze in 10x .h5 dataset. Useful for mixed-species data. For example, 'hg38' in a dataset containing both 'hg38' and 'mm10'. Omit to analyze all genomes",
    )
    input.add_argument(
        "--mtx-prefix",
        metavar="PREFIX",
        help="Shared filename prefix for 10x-mtx input. For example, 'sample1_' for files like 'sample1_matrix.mtx'",
    )
    input.add_argument(
        "--text-delimiter",
        metavar="DELIM",
        help="Column separator for text input. For example, ',' for CSV files. Omit to detect automatically",
    )
    input.add_argument(
        "--text-no-transpose",
        action="store_true",
        help="Set to skip transposing text input. Use this if the file is already in cell x gene layout",
    )

    annot_input = parser.add_argument_group("Annotation Inputs")
    annot_input.add_argument(
        "--marker-file",
        type=Path,
        metavar="PATH",
        help="JSON file defining marker genes for cell-type annotation",
    )
    annot_input.add_argument(
        "--marker",
        nargs="+",
        action="append",
        metavar=("CELL", "GENE"),
        help="Use to directly define a marker set. This option can be used multiple times. Will be merged with markers from --marker-file. Example: --marker Tcell CD3D CD3E --marker Bcell MS4A1"
    )
    annot_input.add_argument(
        "--target-genes",
        nargs="+",
        default=[],
        help="Target genes to summarize and visualize",
    )

    output = parser.add_argument_group("Output")
    output.add_argument(
        "--output",
        required=True,
        type=Path,
        metavar="PATH",
        help="Output folder for SVG figures and CSV summary files",
    )
    output.add_argument(
        "--save-h5ad",
        type=Path,
        metavar="PATH",
        help="Save the processed dataset as an H5AD snapshot. Saved file can be reused as source to skip preprocessing steps with the same parameters. Annotation data are not cached",
    )

    prep = parser.add_argument_group("Preprocessing")
    prep.add_argument(
        "--filter-min-genes",
        type=uint,
        default=200,
        metavar="N",
        help="Filter out cells with fewer than N detected genes",
    )
    prep.add_argument(
        "--filter-min-cells",
        type=uint,
        default=3,
        metavar="N",
        help="Filter out genes detected in fewer than N cells",
    )
    prep.add_argument(
        "--normalize-sum",
        type=float,
        default=1e4,
        metavar="N",
        help="Target total count used for per-cell normalization",
    )
    prep.add_argument(
        "--n-hvg",
        type=uint,
        default=2000,
        metavar="N",
        help="Number of highly variable genes used for downstream analysis including PCA, neighbor graph and clustering",
    )
    prep.add_argument(
        "--hvg-scale-max",
        type=float,
        default=10.0,
        metavar="X",
        help="Ceiling value when scaling highly variable genes. This limits the influence of extreme outliers",
    )

    graph = parser.add_argument_group("Dimensionality Reduction")
    graph.add_argument(
        "--n-pcs",
        type=uint,
        default=50,
        metavar="N",
        help="Number of principal components to compute and use for neighbor graph construction",
    )
    graph.add_argument(
        "--n-neighbors",
        "--neighbors",
        type=uint,
        default=10,
        metavar="N",
        help="Number of nearest neighbors used to build the graph. Smaller values preserve finer local structure but may produce noisier clusters",
    )

    cluster = parser.add_argument_group("Clustering")
    cluster.add_argument(
        "--leiden-resolution",
        type=float,
        default=0.75,
        metavar="X",
        help="Leiden algorithm resolution. Larger values usually produce more yet smaller clusters",
    )
    cluster.add_argument(
        "--leiden-seed",
        type=uint,
        default=0,
        metavar="INT",
        help="Random seed for Leiden clustering. Different seed produces different graph. Internally maps to Scanpy's 'random_state' parameter",
    )

    umap = parser.add_argument_group("Umap Visualization")
    umap.add_argument(
        "--umap-min-dist",
        type=float,
        default=0.5,
        metavar="X",
        help="Minimum distance between points in UMAP space. Smaller values produce tighter clumps",
    )
    umap.add_argument(
        "--umap-spread",
        type=float,
        default=1.0,
        metavar="X",
        help="Overall spread of points in UMAP space. Usually adjusted together with --umap-min-dist",
    )
    umap.add_argument(
        "--umap-seed",
        type=uint,
        default=0,
        metavar="INT",
        help="Random seed for UMAP. Different seed produces different graph. Internally maps to Scanpy's random_state parameter",
    )
    umap.add_argument(
        "--smooth-umap",
        action="store_true",
        help="Set to additionally generate smoothed UMAP plots for target genes. Smoothed plots are less faithful to raw expression values but may help visually",
    )

    annot = parser.add_argument_group("Marker-based Annotation")
    annot.add_argument(
        "--annot-min-score",
        type=float,
        default=0.05,
        metavar="X",
        help="Minimum score required to assign a label. If all candidate cell types scored below set threshold, the label will be 'Unknown'",
    )
    annot.add_argument(
        "--annot-min-margin",
        type=float,
        default=0.05,
        metavar="X",
        help="Minimum score difference before ruling out other candidates. For example. if T=1.05 and NK=1.04 and the margin is 0.03, the result will be 'T or NK'",
    )

    celltypist = parser.add_argument_group("Celltypist Annotation")
    celltypist.add_argument(
        "--celltypist-model",
        metavar="MODEL",
        help="CellTypist model name or path to the .pkl model file. If provided, a second annotation result will be predicted and added with CellTypist",
    )
    celltypist.add_argument(
        "--celltypist-majority-voting",
        action="store_true",
        help="Enable majority voting for CellTypist annotation. This aggregates predictions from multiple classifiers therefore improve robustness at the cost of longer runtime",
    )

    parser.validators.append(_ensure_marker_provided)

    return parser


def _ensure_marker_provided(args: argparse.Namespace) -> None:
    if not args.marker and not args.marker_file:
        raise argparse.ArgumentError(None, "No markers provided")


def _ensure_celltypist_normalize_sum(args: argparse.Namespace) -> None:
    if args.celltypist_model and args.normalize_sum != 1e4:
        raise ValueError(f"CellTypist requires log1p normalized expression with 10000 normalized sum while yours is {args.normalize_sum}")


parser = _get_arg_parser()