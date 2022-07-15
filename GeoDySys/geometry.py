#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import scipy.sparse as sp

import torch_geometric.utils as PyGu
from torch_geometric.nn import knn_graph, radius_graph
from torch_sparse import SparseTensor
from cknn import cknneighbors_graph

from sklearn.cluster import KMeans
from sklearn.metrics import pairwise_distances
from sklearn.manifold import TSNE

from ptu_dijkstra import ptu_dijkstra

from GeoDySys import utils


# =============================================================================
# Sampling
# =============================================================================
def sample_2d(N=100, interval=[[-1,-1],[1,1]], method='uniform', seed=0):
    
    if method=='uniform':
        x = np.linspace(interval[0][0], interval[1][0], int(np.sqrt(N)))
        y = np.linspace(interval[0][1], interval[1][1], int(np.sqrt(N)))
        x = np.stack([x,y],axis=1)
        
    elif method=='random':
        np.random.seed(seed)
        x = np.random.uniform((interval[0][0], interval[0][1]), 
                              (interval[1][0], interval[1][1]), 
                              (N,2))
        
    return x


def furthest_point_sampling(X, N=None, return_clusters=False):
    """
    A Naive O(N^2) algorithm to do furthest points sampling
    
    Parameters
    ----------
    D : ndarray (N, N) 
        An NxN distance matrix for points
    Return
    ------
    tuple (list, list) 
        (permutation (N-length array of indices), 
        lambdas (N-length array of insertion radii))
    """
    
    D = pairwise_distances(X, metric='euclidean')
    N = D.shape[0] if N is None else N
    
    #By default, takes the first point in the list to be the
    #first point in the permutation, but could be random
    perm = np.zeros(N, dtype=np.int64)
    lambdas = np.zeros(N)
    ds = D[0, :]
    for i in range(1, N):
        idx = np.argmax(ds)
        perm[i] = idx
        lambdas[i] = ds[idx]
        ds = np.minimum(ds, D[idx, :])
        
    if not return_clusters:
        return perm, lambdas
    else:
        clusters = [[] for i in range(N)]
        D = D[perm]
        D[D==0] = D.max()
        D[:,perm] = D.max()
        for i in range(X.shape[0]-N):
            idx = np.unravel_index(D.argmin(), D.shape)
            clusters[idx[0]].append(idx[1])
            D[:,idx[1]] = D.max()
            
        return perm, lambdas, clusters
        

# =============================================================================
# Clustering
# =============================================================================
def cluster_and_embed(x, cluster_typ='kmeans', embed_typ='tsne', n_clusters=15, proximity_order=True, seed=0):
    """Cluster & embed"""
    
    x = x.detach().numpy()

    clusters = cluster(x, cluster_typ, n_clusters, seed)
        
    #reorder to give close clusters similar labels
    if proximity_order:
        clusters = relabel_by_proximity(clusters)
        
    emb = np.vstack([x, clusters['centroids']])
    emb = embed(emb, embed_typ)
    clusters['centroids'] = emb[-n_clusters:]
    emb = emb[:-n_clusters]       
        
    return emb, clusters


def cluster(x, cluster_typ='kmeans', n_clusters=15, seed=0):
    
    clusters = dict()
    if cluster_typ=='kmeans':
        kmeans = KMeans(n_clusters=n_clusters, random_state=seed).fit(x)
        clusters['n_clusters'] = n_clusters
        clusters['labels'] = kmeans.labels_
        clusters['centroids'] = kmeans.cluster_centers_
    else:
        NotImplementedError
        
    return clusters


def embed(x, embed_typ='tsne'):
    
    if embed_typ=='tsne': 
        if x.shape[1]>2:
            print('Performed t-SNE embedding on embedded results.')
            emb = TSNE(init='random',learning_rate='auto').fit_transform(x)
    elif embed_typ=='umap':
        NotImplementedError
    else:
        NotImplementedError
    
    return emb


def relabel_by_proximity(clusters):
    
    pd = pairwise_distances(clusters['centroids'], metric='euclidean')
    pd += np.max(pd)*np.eye(clusters['n_clusters'])
    
    mapping = dict()
    id_old = 0
    for i in range(clusters['n_clusters']):
        id_new = np.argmin(pd[id_old,:])
        while id_new in mapping.keys():
            pd[id_old,id_new] += np.max(pd)
            id_new = np.argmin(pd[id_old,:])
        mapping[id_new] = i
        id_old = id_new
        
    l = clusters['labels']
    clusters['labels'] = np.array([mapping[l[i]] for i,_ in enumerate(l)])
    clusters['centroids'] = clusters['centroids'][list(mapping.keys())]
    
    return clusters


# =============================================================================
# Manifold operations
# =============================================================================
def adjacency_matrix(edge_index, size=None, value=None):
    """Adjacency matrix as torch_sparse tensor"""
    
    if value is not None:
        value=value[edge_index[0], edge_index[1]]
    if size is None:
        size = (edge_index.max()+1, edge_index.max()+1)
        
    adj = SparseTensor(row=edge_index[0], col=edge_index[1], 
                       value=value,
                       sparse_sizes=(size[0], size[1]))
    
    return adj


def fit_graph(x, graph_type='cknn', par=1):
    """Fit graph to node positions"""
    
    if graph_type=='cknn':
        ckng = cknneighbors_graph(x, n_neighbors=par, delta=1.0)
        ckng += sp.eye(ckng.shape[0])
        edge_index = np.vstack(ckng.nonzero())
        edge_index = utils.np2torch(edge_index, dtype='double')
    elif graph_type=='knn':
        edge_index = knn_graph(x, k=par)
    elif graph_type=='radius':
        edge_index = radius_graph(x, r=par)
    else:
        NotImplementedError
    
    edge_index = PyGu.to_undirected(edge_index)
    
    return edge_index


def compute_laplacian(data, normalization="rw"):
    
    L = PyGu.get_laplacian(data.edge_index, normalization=normalization)
    L = PyGu.to_scipy_sparse_matrix(L[0], edge_attr=L[1])
    
    return utils.np2torch(L.toarray())


def compute_connection_laplacian(L, R):
    """
    Connection Laplacian

    Parameters
    ----------
    L : nxn torch tensor
        Laplacian matrix.
    R : nxnxdimxdim torch tensor
        Connection matrices between all pairs of nodes.

    Returns
    -------
    n*dimxn*dim torch tensor
        Connection Laplacian.

    """    
    n = L.shape[0]
    dim = R.shape[2]
    
    #rearrange into block form
    L = L.repeat_interleave(dim, dim=0).repeat_interleave(dim, dim=1)
    R = R.swapaxes(1,2).reshape(n*dim, n*dim)
    
    return L*R


def compute_eigendecomposition(A, k=2, eps=1e-8):
    """
    Eigendecomposition of a square matrix A
    
    Parameters
    ----------
    A : square matrix A
    k : number of eigenvectors
    eps : small error term
    
    Returns
    -------
    evals : (k) list of eigenvalues of the Laplacian
    evecs : (V,k) list of eigenvectors of the Laplacian 
    grad_mat : (VxVxdim) sparse matrix which gives the gradient in the local basis at the vertex
    
    """
    
    # Compute the eigenbasis
    A_eigsh = (A + sp.identity(A.shape[0])*eps).tocsc()
    failcount = 0
    while True:
        try:
            evals, evecs = sp.linalg.eigsh(A_eigsh, k=k)
            
            # Clip off any eigenvalues that end up slightly negative due to numerical weirdness
            evals = np.clip(evals, a_min=0., a_max=float('inf'))

            break
        except Exception as e:
            print(e)
            if(failcount > 3):
                raise ValueError("failed to compute eigendecomp")
            failcount += 1
            print("--- decomp failed; adding eps ===> count: " + str(failcount))
            A_eigsh = A_eigsh + sp.identity(A.shape[0]) * (eps * 10**failcount)
    
    return utils.np2torch(evals), utils.np2torch(evecs)


def compute_tangent_frames(data, n_geodesic_nb=10, return_predecessors=False):

    X = data.pos.numpy().astype(np.float64)
    A = to_scipy_sparse_matrix(data.edge_index).tocsr()

    _, _, tangents, R = ptu_dijkstra(X, A, 2, n_geodesic_nb, return_predecessors)
    
    return tangents, R


# def vertex_normals(verts, n_nb=30):
    
#     _, neigh_inds = find_knn(verts, verts, n_nb, omit_diagonal=True, method='cpu_kd')
#     neigh_points = verts[neigh_inds,:]
#     neigh_vecs = neigh_points - verts[:,np.newaxis,:]
    
#     (u, s, vh) = np.linalg.svd(neigh_vecs, full_matrices=False)
#     normal = vh[:,2,:]
#     normal /= np.linalg.norm(normal,axis=-1, keepdims=True)
        
#     if torch.any(torch.isnan(normal)): raise ValueError("NaN normals :(")

#     return normal


# def build_grad_point_cloud(verts, frames, n_nb=30):

#     _, neigh_inds = find_knn(verts, verts, n_nb, omit_diagonal=True, method='cpu_kd')

#     edge_inds_from = np.repeat(np.arange(verts.shape[0]), n_nb)
#     edges = np.stack((edge_inds_from, neigh_inds.flatten()))
#     edge_tangent_vecs = edge_tangent_vectors(verts, frames, edges)#this is the F in Beaini (?)
    
#     return build_grad(verts, torch.tensor(edges), edge_tangent_vecs)


# def edge_tangent_vectors(verts, frames, edges):
#     edge_vecs = verts[edges[1, :], :] - verts[edges[0, :], :]
#     basisX = frames[edges[0, :], 0, :]
#     basisY = frames[edges[0, :], 1, :]

#     compX = edge_vecs.dot(basisX)
#     compY = edge_vecs.dot(basisY)
#     edge_tangent = torch.stack((compX, compY), dim=-1)

#     return edge_tangent


# def project_to_tangent(vecs, unit_normals):
#     dots = vecs.dot(unit_normals)
#     return vecs - unit_normals * dots.unsqueeze(-1)