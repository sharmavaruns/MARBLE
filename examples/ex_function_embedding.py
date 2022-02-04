#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import torch
import matplotlib.pyplot as plt
import sys
from GeoDySys.plotting import set_colors
from GeoDySys import plotting, embedding
from GeoDySys.embedding import SAGE, model_eval, train
from torch_geometric.utils.convert import to_networkx
from torch_geometric.data.collate import collate
from tensorboardX import SummaryWriter
from datetime import datetime

def main():

    n=200
    k=10
    
    ind = np.arange(n)
      
    x0 = np.random.uniform(low=(-1,-1),high=(1,1),size=(n,2))
    x1 = np.random.uniform(low=(-1,-1),high=(1,1),size=(n,2))
    x2 = np.random.uniform(low=(-1,-1),high=(1,1),size=(n,2)) 
    x3 = np.random.uniform(low=(-1,-1),high=(1,1),size=(n,2))
    x = [x0, x1, x2, x3]
    y = [f0(x0), f1(x1), f2(x2), f3(x3)]
    
    data_list = []
    G = []
    for i, y_ in enumerate(y):
        #fit knn before adding function as node attribute
        data_ = embedding.fit_knn_graph(x[i], ind, k=k)
        G_ = to_networkx(data_, node_attrs=['x'], edge_attrs=None, to_undirected=True,
                    remove_self_loops=True)
        
        data_ = embedding.traintestsplit(data_, test_size=0.1, val_size=0.5, seed=0)
        data_.x = torch.hstack((data_.x,y_)) #add new node feature
        data_.num_nodes = len(x[i])
        data_.num_node_features = data_.x.shape[1]
        data_.y = torch.ones(data_.num_nodes, dtype=int)*i
        
        G.append(G_)
        data_list.append(data_)
        
    #collate datasets
    data, slices, _ = collate(data_list[0].__class__,
                           data_list=data_list,
                           increment=True,
                           add_batch=False)
    
    #set up and train sage model
    par = {'num_node_features': data.x.shape[1],
           'hidden_channels': 64,
           'batch_size': 20,
           'num_layers': 2,
           'epochs': 50,
           'lr': 0.01}
    
    writer = SummaryWriter("./log/" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    
    # build model
    model = SAGE(par['num_node_features'], 
                 hidden_channels=par['hidden_channels'], 
                 num_layers=par['num_layers'])
    
    model = train(model, data, par, writer)
    
    #embed data
    emb = model_eval(model, data)
    
    
    #plotting
    
    model_vis(emb, data)
    
    fig, axs = plt.subplots(2,2)
       
    c= set_colors(y[0], cbar=False)
    axs[0,0].scatter(x[0][:,0],x[0][:,1], c=c)
    axs[0,0].set_aspect('equal', 'box')
    plotting.graph(G[0],node_colors=None,show_colorbar=False,ax=axs[0,0],node_size=5,edge_width=0.5)

    c= set_colors(y[1], cbar=False)
    axs[1,0].scatter(x[1][:,0],x[1][:,1], c=c)
    axs[1,0].set_aspect('equal', 'box')
    plotting.graph(G[1],node_colors=None,show_colorbar=False,ax=axs[1,0],node_size=5,edge_width=0.5)
    
    c= set_colors(y[2], cbar=False)
    axs[1,1].scatter(x[2][:,0],x[2][:,1], c=c)
    axs[1,1].set_aspect('equal', 'box')
    plotting.graph(G[2],node_colors=None,show_colorbar=False,ax=axs[1,1],node_size=5,edge_width=0.5)
    
    c= set_colors(y[3], cbar=False)
    axs[0,1].scatter(x[3][:,0],x[3][:,1], c=c)
    axs[0,1].set_aspect('equal', 'box')
    plotting.graph(G[3],node_colors=None,show_colorbar=False,ax=axs[0,1],node_size=5,edge_width=0.5)
    
    fig.tight_layout()
    
def model_vis(emb, data):
    from sklearn.manifold import TSNE
    import matplotlib.pyplot as plt
    colors = ["red", "orange", "green", "blue", "purple", "brown", "black"]
    colors = [colors[y] for y in data.y]
    xs, ys = zip(*TSNE().fit_transform(emb.detach().numpy()))
    plt.scatter(xs, ys, color=colors)
    
def f0(x):
    f = x[:,[0]]*0
    return torch.tensor(f).float()

def f1(x):
    f = x[:,[0]] + x[:,[1]]
    return torch.tensor(f).float()

def f2(x):
    f = x[:,[0]]**2 + x[:,[1]]**2
    return torch.tensor(f).float()

def f3(x):
    f = x[:,[0]]**2 - x[:,[1]]**2
    return torch.tensor(f).float()


if __name__ == '__main__':
    sys.exit(main())