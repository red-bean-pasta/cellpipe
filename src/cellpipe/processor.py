import scanpy as sc
from anndata import AnnData


def filter_cells_and_genes(data: AnnData, min_genes: int, min_cells: int) -> AnnData:
    """
    Filter low quality cells with too few genes and low quality genes with too few cells
    :param data:
    :param min_genes:
    :param min_cells:
    :return:
    """
    # No need for min_counts. And Scanpy recommends one threshold per filter
    sc.pp.filter_cells(data, min_genes=min_genes)
    sc.pp.filter_genes(data, min_cells=min_cells)
    return data


def normalize_and_log_transform(
    data: AnnData,
    target_sum: float,
    key_added: str
) -> AnnData:
    """
    Scale different cell to same amount.
    Log the amount of genes.
    :param data:
    :param target_sum:
    :param key_added:
    :return:
    """
    # scale the total amount of cells to the same base
    # so that the total genes amount of each cell are comparable
    sc.pp.normalize_total(
        data,
        target_sum=target_sum,
        exclude_highly_expressed=False,
        key_added=key_added,
    )
    # log the amount of each genes as gene expression counts are very skewed
    sc.pp.log1p(data)
    return data


def select_variable_genes_and_scale(
        data: AnnData,
        n_top_genes: int,
        scale_max: float,
) -> AnnData:
    """
    Pick genes with the strongest variation.
    Scale picked genes to same amount.
    Directly subset on passed data. Back up first if needed.
    :param data:
    :param n_top_genes:
    :param scale_max:
    :return:
    """
    # pick genes with strong count variation across cells
    # genes with low variation doesn't help distinguish cells
    sc.pp.highly_variable_genes(
        data,
        n_top_genes=n_top_genes,
        subset=True)
    # scale picked genes to equalize each gene's contribution
    # else genes with larger variance dominate
    sc.pp.scale(data, zero_center=False, max_value=scale_max) # set zero_center to false to avoid densifying and RAM blow
    return data


def compute_principal_components(
        data: AnnData,
        n_comps: int,
) -> AnnData:
    """

    :param data:
    :param n_comps: the number of calculated principal components
    :return:
    """
    # PCA: Principal Component Analysis
    # principal components are linear combinations of genes, like geneA*0.3 + geneB*0.2 - geneC*0.1
    # it helps reduce dimensionality
    sc.pp.pca(data, n_comps=n_comps)
    return data


def build_neighbor_graph(
        data: AnnData,
        n_neighbors: int,
        n_pcs: int,
) -> AnnData:
    # K-nearest Neighbors
    # pick n_pcs PCAs, calculate cell distances, connect each with n_neighbors closet neighbors
    sc.pp.neighbors(data, n_neighbors=n_neighbors, n_pcs=n_pcs)
    return data


def build_leiden_graph(
        data: AnnData,
        resolution: float,
        random_state: int,
        key_added: str,
) -> AnnData:
    """

    :param data:
    :param resolution: determines the cluster size and count
    :param random_state: like seed in games
    :param key_added:
    :return:
    """
    sc.tl.leiden(
        data,
        resolution=resolution,
        random_state=random_state,
        key_added=key_added,
        use_weights=True, # avoid Scanpy behavior change
        flavor="igraph",
        n_iterations = 2,
        directed=False
    )
    return data


def build_umap_graph(
        data: AnnData,
        min_dist: float,
        spread: float,
        random_state: int,
) -> AnnData:
    """

    :param data:
    :param min_dist:
        minimum distance between drawn points,
        determining how spread or clustered result image is
    :param spread:
        distance scaled between points,
        also determining how clustered final image is
    :param random_state:
        seed
    :return:
    """
    print(f"Random state: {random_state}")
    sc.tl.umap(
        data,
        min_dist=min_dist,
        spread=spread,
        random_state=random_state
    )
    return data