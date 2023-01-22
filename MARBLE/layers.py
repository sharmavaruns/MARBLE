#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import torch
import torch.nn as nn
from torch.nn.functional import normalize

from torch_geometric.nn.conv import MessagePassing
from torch_geometric.nn import MLP

from .lib import geometry as g
from .lib import utils


def setup_layers(model):
    
    par = model.par
    
    s, e, o = par['dim_signal'], par['dim_emb'], par['order']
    
    #diffusion
    diffusion = Diffusion()
    
    #gradient features
    grad = nn.ModuleList(AnisoConv(par['vec_norm']) for i in range(o))
        
    #cumulated number of channels after gradient features
    cum_channels = s*(1-e**(o+1))//(1-e)
    if par['inner_product_features']:
        cum_channels //= s
        if s==1:
            cum_channels = o+1
    
        inner_products = InnerProductFeatures(cum_channels, s)
    else:
        inner_products = None
    
    #encoder
    channel_list = [cum_channels] + \
                    (par['n_lin_layers']-1) * [par['hidden_channels']] + \
                    [par['out_channels']]

    enc = MLP(channel_list=channel_list,
              dropout=par['dropout'],
              norm=par['batch_norm'],
              bias=par['bias']
              )
    
    model.diffusion, model.grad, model.inner_products, model.enc = \
        diffusion, grad, inner_products, enc
        
    return model


# =============================================================================
# Layer definitions
# =============================================================================
class Diffusion(nn.Module):
    """Diffusion with learned t."""

    def __init__(self, tau0=0.0):
        super().__init__()
                
        self.diffusion_time = nn.Parameter(torch.tensor(float(tau0)))
                
    def forward(self, x, L, Lc=None, method='spectral', normalise=False):
        
        if method=='spectral':
            assert len(L)==2, 'L must be a matrix or a pair of eigenvalues \
                                and eigenvectors'
        
        # making sure diffusion times are positive
        with torch.no_grad():
            self.diffusion_time.data = torch.clamp(self.diffusion_time, min=1e-8)
            
        t = self.diffusion_time
        
        if Lc is not None:
            out = g.vector_diffusion(x, t, method, Lc, normalise)
        else:
            out = [g.scalar_diffusion(x_, t, method, L) for x_ in x.T]
            out = torch.cat(out, axis=1)
            
        return out
    
    
class AnisoConv(MessagePassing):
    """Anisotropic Convolution"""
    def __init__(self, vec_norm=False, **kwargs):
        super().__init__(aggr='add', **kwargs)
        
        self.vec_norm = vec_norm
        
    def forward(self, x, edge_index, size, kernels, R=None):
        
        edge_index = edge_index[[1,0], :]
        size = (size[1], size[0])
        
        if R is not None:
            dim = len(kernels)
            size = (size[0]*dim, size[1]*dim)
            edge_index = utils.expand_edge_index(edge_index, dim)
            
        #apply kernels
        out = []
        for K in utils.to_list(kernels):
            if R is not None:
                # K = torch.sparse_coo_tensor(edge_index, 
                #                             K.values().repeat_interleave(dim*dim))
                K = torch.kron(K, torch.ones((dim,dim), device=x.device))
                K *= R
                
            #transpose to change from source to target
            K = utils.to_SparseTensor(edge_index, size, value=K)
            
            out.append(self.propagate(K, x=x))
            
        #[[dx1/du, dx2/du], [dx1/dv, dx2/dv]] -> [dx1/du, dx1/dv, dx2/du, dx2/dv]
        out = torch.stack(out, axis=2)
        out = out.view(out.shape[0], -1)
        
        if self.vec_norm:
            out = normalize(out, dim=-1, p=2)
            
        return out

    def message_and_aggregate(self, K_t, x):
        """Message passing step. If K_t is a txs matrix (s sources, t targets),
           do matrix multiplication K_t@x, broadcasting over column features. 
           If K_t is a t*dimxs*dim matrix, in case of manifold computations,
           then first reshape, assuming that the columns of x are ordered as
           [dx1/du, x1/dv, ..., dx2/du, dx2/dv, ...].
           """
        n, dim = x.shape
        
        if (K_t.size(dim=1) % n*dim)==0:
            n_ch = n*dim // K_t.size(dim=1)
            x = x.view(-1, n_ch)
            
        x = K_t.matmul(x, reduce=self.aggr)
            
        return x.view(-1, dim)

    
class InnerProductFeatures(nn.Module):
    """
    Compute scaled inner-products between channel vectors.
    
    Input: (V x C*D) vector of (V x n_i) list of vectors with \sum_in_i = C*D
    Output: (VxC) dot products
    """

    def __init__(self, C, D):
        super().__init__()

        self.C, self.D = C, D
        
        self.O = nn.ModuleList()
        for i in range(C):
            self.O.append(nn.Linear(D, D, bias=False))
        
        self.reset_parameters()
        
    def reset_parameters(self):
        for i in range(len(self.O)):
            self.O[i].weight.data = torch.eye(self.D)

    def forward(self, x):
        
        if not isinstance(x, list):
            x = [x]
            
        x = [x_.view(x_.shape[0], -1, self.D) for x_ in x]
            
        #for scalar signals take magnitude
        if self.D==1:
            x = [x_.norm(dim=2) for x_ in x]
            
            return torch.cat(x, axis=1)
        
        #for vector signals take inner products
        else:
            #bring to form where all columns are vector in the tangent space
            #so taking inner products is possible
            #[ x1 dx1/du ...]
            #  x2 dx1/dv
            #  x3 dx1/dw
            x = [x_.swapaxes(1,2) for x_ in x]
            x = torch.cat(x, axis=2)
            
            assert x.shape[2]==self.C, 'Number of channels is incorrect!'
            
            #O_ij@x_j
            Ox = [self.O[j](x[...,j]) for j in range(self.C)]
            Ox = torch.stack(Ox, dim=2)
            
            #\sum_j x_i^T@O_ij@x_j
            xOx = torch.einsum('bki,bkj->bi', x, Ox)
            
            return torch.tanh(xOx).reshape(x.shape[0], -1)