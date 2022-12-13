#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import sys
from MARBLE import plotting, utils, geometry, net, postprocessing
import matplotlib.pyplot as plt

def main():
    
    #parameters
    n = 512
    k = 15
    n_clusters = 15
    
    par = {'epochs': 20, #optimisation epochs
           'order': 1, #order of derivatives
           'n_lin_layers': 2,
           'hidden_channels': 16, #number of internal dimensions in MLP
           'out_channels': 3,
           'inner_product_features': False,
           'autoencoder': False
           }
    
    #evaluate functions
    # f0: linear, f1: point source, f2: point vortex, f3: saddle
    x = [geometry.sample_2d(n, [[-1,-1],[1,1]], 'random') for i in range(4)]
    y = [f0(x[0]), f1(x[1]), f2(x[2]), f3(x[3])] #evaluated functions
        
    #construct PyG data object
    data = utils.construct_dataset(x, y, graph_type='cknn', k=k)
    
    #train model
    model = net(data, **par)
    model.run_training(data)
    
    #evaluate model on data
    data = model.evaluate(data)
    data = postprocessing(data, n_clusters=n_clusters, cluster_typ='kmeans')
    
    #plot
    titles=['Linear left','Linear right','Vortex right','Vortex left']
    plotting.fields(data, titles=titles, col=2)
    plt.savefig('../results/fields.svg')
    plotting.embedding(data, data.y.numpy(),titles=titles)
    plt.savefig('../results/embedding.svg')
    plotting.histograms(data, titles=titles)
    plt.savefig('../results/histogram.svg')
    plotting.neighbourhoods(data)
    plt.savefig('../results/neighbourhoods.svg')
    
def f0(x):
    return x*0 + np.array([-1,-1])

def f1(x):
    return x*0 + np.array([1,1])

# def f2(x):
#     return x*0 + np.array([1,0])

def f3(x):
    return x*0 + np.array([0,1])

# def f1(x):
#     eps = 1e-3
#     norm = np.sqrt(x[:,[0]]**2 + x[:,[1]]**2) + eps
#     u = 2*x[:,[0]]/norm
#     v = 2*x[:,[1]]/norm
#     return np.hstack([u,v])

def f2(x):
    eps = 1e-1
    norm = np.sqrt((x[:,[0]]+1)**2 + x[:,[1]]**2 + eps)
    u = x[:,[1]]/norm
    v = -(x[:,[0]]+1)/norm
    return np.hstack([u,v])

def f3(x):
    eps = 1e-1
    norm = np.sqrt((x[:,[0]]-1)**2 + x[:,[1]]**2 + eps)
    u = x[:,[1]]/norm
    v = -(x[:,[0]]-1)/norm
    return np.hstack([u,v])

# def f3(x):
#     eps = 1e-1
#     norm = x[:,[0]]**2 + x[:,[1]]**2 + eps
#     u = x[:,[1]]/norm
#     v = x[:,[0]]/norm
#     return torch.tensor(np.hstack([u,v])).float() 


if __name__ == '__main__':
    sys.exit(main())