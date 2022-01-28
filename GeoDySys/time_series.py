import numpy as np
from sklearn.neighbors import NearestNeighbors
import numpy.ma as ma


def delay_embed(x, k, tau=1, typ='asy'):
    """
    Delay-embedding for multi-dimensional time series x(t)

    Parameters
    ----------
    x : Txd array
        Multi-dimensional time series.
    k : int
        Embedding dimension. Needs to be at most 2*d+1, possibly smaller..
    tau : int, optional
        Delay parameter. The default is 1.
    typ : TYPE, optional
        Embedding based on points on one side (asymmetric) of both side of
        points (symmetric). The default is 'asy'.

    Returns
    -------
    Yd : (T-(k-1)*tau)*kd numpy array
        Time asymmetric or symmetric embedding. The default is 'asy'..

    """
    
    if len(x.shape)==1:
        x = x[:,None]
        
    dim = x.shape[1]
    
    #delay embed all dimensions
    Y = []
    for d in range(dim):
        Ytmp = delay_embed_scalar(x[:,d], k, tau, typ='asy')
        Y.append(Ytmp)
    
    #interleave dimensions
    shape = (Y[0].shape[0], Y[0].shape[1]*len(Y))
    # Y = np.vstack(Y).reshape(shape)
    Yd = np.empty(shape)
    for i in range(dim):
        Yd[:,i::dim]=Y[i]
    
    return Yd


def delay_embed_scalar(x, k, tau=-1, typ='asy'):
    """
    Delay-embedding for scalar time-series x(t).
    Builds prekictive coorkinates Y=[x(t), x(t-tau), ..., x(t-(k-1)*tau)]

    Parameters
    ----------
    x : Tx1 array
        Scalar time series.
    k : int
        Embedding dimension. Needs to be at most 2*d+1, possibly smaller.
    tau : int, optional
        Delay parameter. The default is 1.
    typ : 'asy', 'sym', optional
        Embedding based on points on one side (asymmetric) of both side of
        points (symmetric). The default is 'asy'.

    Returns
    -------
    Y : (T-(k-1)*tau)*k numpy array
        Delay embedded coorkinates.

    """
    
    #check if delay is in past (predictive embedding)
    if tau<0:
        tau = abs(tau)
        flip = True
    else:
        flip = False
        
    T = x.shape[0] #length of time series
    N = T - (k-1)*tau # length of embedded signal
    Y = np.zeros([N,k])
        
    if typ == 'asy':  
        for ki in range(k):
            ind = np.arange(ki*tau, N+ki*tau)
            Y[:,ki] = x[ind]
            
        if flip:
            Y = np.flip(Y, axis=1)
            
    elif typ == 'sym' and k % 2 == 0:
        for ki in range(-k//2,k//2):
            ind = np.arange((k//2+ki)*tau, N+(k//2+ki)*tau)
            Y[:,ki] = x[ind]
            
    elif typ == 'sym' and k % 2 == 1:    
        for ki in range(-(k-1)//2,(k-1)//2+1):
            ind = np.arange(((k-1)//2+ki)*tau, N+((k-1)//2+ki)*tau)
            Y[:,ki] = x[ind]
            
    return Y


def find_nn(x_query, X, nn=1, nmax=10, n_jobs=-1):
    """
    Find nearest neighbors of a point on the manifold

    Parameters
    ----------
    x_query : 2d np array, list[2d np array]
        Coordinates of points whose nearest neighbors are needed.
    x : nxd array (dimensions are columns!)
        Coordinates of n points on a manifold in d-dimensional space.
    nn : int, optional
        Number of nearest neighbors. The default is 1.
    nmax : int, optional
        Maximum number of nearest neighbors. The default is 10.
    n_jobs : int, optional
        Number of processors to use. The default is -1 (all processors).
        
    Returns
    -------
    dist_nn : list[list]
        Distance of nearest neighbors.
    ind_nn : list[list]
        Index of nearest neighbors.

    """
        
    if isinstance(x_query, list):
        x_query = np.vstack(x_query)
    
    neigh = NearestNeighbors(n_neighbors=nn,
                             algorithm='auto',
                             metric='minkowski',
                             p=2,
                             n_jobs=-1)
    
    #Fit neighbors estimator object
    neigh.fit(X)
    
    #Ask for nearest neighbors
    dist_nn, ind_nn = neigh.kneighbors(x_query, nn+nmax, return_distance=True)
    
    #take only nonzero distance neighbors
    first_n = (dist_nn!=0).argmax(axis=1)
    last_n = first_n+nn
    
    ind_nn = [ind_nn[i,first_n[i]:last_n[i]] for i in range(len(first_n))]
    dist_nn = [dist_nn[i,first_n[i]:last_n[i]] for i in range(len(first_n))]
    
    return dist_nn, ind_nn


def valid_flows(t_ind, ts, T):
    """
    Mask out invalid trajectories.

    Parameters
    ----------
    t_ind : list[int]
        Time indices corresponding to the sampled short trajectories.
    ts : list[int]
        Start of trajectory.
    T : int or list[int]
        End of trajectory or time horizon.

    Returns
    -------
    tt : list[int]
        Start of trajectory.
    ts : list[int]
        End of trajectory.

    """
    
    if isinstance(T, int):
        tt = [ts[i]+T for i in range(len(ts))]
    else:
        tt = T
        assert len(tt)==len(ts), 'Number of source points must equal to the \
            number of target points.'
            
    t_breaks = np.zeros_like(t_ind)
    t_breaks[np.array(t_ind)==0] = 1
    t_breaks[0] = 0
    
    invalid = np.zeros_like(tt)
    for i,(s,t) in enumerate(zip(ts,tt)):
        if t>len(t_ind)-2 or s<0 or t<=s or np.sum(t_breaks[s:t])>0:
            invalid[i] = 1
        
    ts = ma.array(ts, mask=invalid)
    tt = ma.array(tt, mask=invalid)
        
    return ts, tt


def generate_flow(X, ts, T):
    """
    Obtain trajectories of between timepoints.

    Parameters
    ----------
    X : np array
        Trajectories.
    ts : int or np array or list[int]
        Source timepoint.
    T : int or list[int]
        End of trajectory or time horizon.

    Returns
    -------
    X_sample : list[np array].
        Set of flows of length T.

    """
    
    ts = ma.array(ts, dtype=int)
    
    if isinstance(T, int):
        tt = ma.array([ts[i]+T for i in range(len(ts))])
        tt = ma.array(tt, mask=ts.mask, dtype=int)
    else:
        tt = ma.array(T)
        assert len(tt)==len(ts), 'Number of source points must equal to the \
            number of target points.'
    
    X_sample = []
    for s,t in zip(ts,tt):
        if not ma.is_masked(s) and not ma.is_masked(t):
            X_sample.append(X[s:t+1])

    return X_sample, ts[~ts.mask], tt[~tt.mask]


def random_projection(X, dim_out=1, seed=1):
    """
    Randomly project dynamical system to a low dimensional plane

    Parameters
    ----------
    X : nxd array (dimensions are columns!)
        Coordinates of n points on a manifold in d-dimensional space.
    dim_out : int, optional
        Dimension of the projection plane. The default is 1 (scalar time 
                                                             series).

    Returns
    -------
    x_proj : nxdim_out array
        Projected dynamics.

    """
    
    from scipy.stats import special_ortho_group
    from numpy.random import RandomState
    
    dim = X.shape[1]
    rs = RandomState(seed)
    
    R = special_ortho_group.rvs(dim, random_state=rs)
    
    x_proj = np.matmul(R, X.T).T
    x_proj = x_proj[:,:dim_out]
    
    return x_proj