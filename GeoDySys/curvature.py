#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
from scipy.interpolate import splprep, splev
from scipy.spatial import ConvexHull
from scipy.spatial.distance import cdist, pdist, squareform
import numpy.ma as ma

def curvature_geodesic(dst):
    """
    Compute manifold curvature at a given set of points.

    Parameters
    ----------
    dst : np.array
        Geodesic distances for all points in the manifold (with a given time 
                                                           horizon, T).
        First row corresponds to geodesic distance on the manifold from a 
        set of points x(t) to points x(t+T).
        Rows from 2 to n correspond to geodesic distances between x(nn_t) and
        x(nn_t(t)+T), where nn_i(t) is the index of the nearest neighbor of 
        x_i(t) on attractor i.

    Returns
    -------
    kappa : list[float]
        List of curvature at timepoints t.

    """
     
    return 1-np.nanmean(dst[:,1:],axis=1)/dst[:,0]


def all_geodesic_dist(X, ts, tt, interp=False):
    """
    Compute all geodesic distances 

    Parameters
    ----------
    X : np array
        Datapoints.
    tt : list[int]
        Start of trajectory.
    ts : list[int]
        End of trajectory.
    interp : bool, optional
        Cubic interpolation between points. The default is false.

    Returns
    -------
    dst : np.array
        Geodesic distance from a set of timepoints with horizon T.

    """
    
    r,c = ts.shape
    ts = ts.flatten()
    tt = tt.flatten()
            
    dst = ma.array(np.zeros(r*c), mask=np.zeros(r*c))
    for i,(s,t) in enumerate(zip(ts,tt)):
        if not ma.is_masked(s) and not ma.is_masked(t):
            dst[i] = geodesic_dist(s, t, X, interp=interp)
        else:
            dst.mask[i] = 1
    
    return dst.reshape(r,c)


def geodesic_dist(s, t, x, interp=False):
    """
    Find the geodesic distance between points x1, x2

    Parameters
    ----------
    s : int
        Index of first endpoint of geodesic.
    t : int
        Index of second endpoint of geodesic.
    x : nxd array (dimensions are columns!)
        Coordinates of n points on a manifold in d-dimensional space.
    interp : bool, optional
        Interpolate between points. The default is 0.

    Returns
    -------
    dist : float
        Geodesic distance.

    """
        
    assert s<t, 'First point must be before second point!'
    
    if interp:
        #compute spline through points
        tck, u = fit_spline(x.T, degree=3, smoothing=0.0, per_bc=0)
        u_int = [u[s], u[t]]
        x = eval_spline(tck, u_int, n=1000)
    else:
        x = x[s:t,:]
    
    dij = np.diff(x, axis=0)
    dij *= dij
    dij = dij.sum(1)
    dij = np.sqrt(dij)
        
    dist = dij.sum()
        
    return dist


def fit_spline(X, degree=3, smoothing=0.0, per_bc=0):
    """
    Fit spline to points

    Parameters
    ----------
    X : nxd array (dimensions are columns!)
        Coordinates of n points on a manifold in d-dimensional space.
    degree : int, optional
        Order of spline. The default is 3.
    smoothing : float, optional
        Smoothing. The default is 0.0.
    per_bc : bool, optional
        Periodic boundary conditions (for closed curve). The default is 0.

    Returns
    -------
    tck : TYPE
        DESCRIPTION.
    u : TYPE
        DESCRIPTION.

    """
    
    tck, u = splprep(X, u=None, s=smoothing, per=per_bc, k=degree) 
    
    return tck, u


def eval_spline(tck, u_int, n=100):
    """
    Evaluate points on spline

    Parameters
    ----------
    tck : tuple (t,c,k)
        Vector of knots returned by splprep().
    u_int : list
        Parameter interval to evaluate the spline.
    n : int, optional
        Number of points to evaluate. The default is 100.

    Returns
    -------
    x_spline : TYPE
        DESCRIPTION.

    """
    
    u = np.linspace(u_int[0], u_int[1], n)
    x_spline = splev(u, tck, der=0)
    x_spline = np.vstack(x_spline).T
    
    return x_spline


def curvature_centroid(X, tt, metric='euclidean'):

    n = tt.shape[0]
    kappa = np.zeros(n)
    for i in range(n):
        if tt[i,0] is None:
            kappa[i]=None
        else:
            tn = [t for t in tt[i,1:] if t is not None]
            t = tt[i,0]
            # centroid = X[tn,:].mean(0, keepdims=True)
            distn = squareform(pdist(X[tn,:])).mean()
            dist = cdist(X[tn,:],X[[t],:],metric=metric).mean()
            kappa[i] = 1 - distn/dist
            
    return kappa


def curvature_ball(X, ts, tt):
    
    ts = ts.T
    tt = tt.T

    n = ts.shape[1]
    kappa = np.zeros(n)
    for i in range(n):

        s = [t for t in ts[:,i] if t is not None]
        t = [t for t in tt[:,i] if t is not None]
        if len(s)<3 or len(t)<3:
            kappa[i] = None
        else:
            kappa[i] = 1 - volume_simplex(X, t)/volume_simplex(X, s) 
            
    return kappa


def volume_simplex(X,t):
    """
    Volume of convex hull of points

    Parameters
    ----------
    X : np.array
        Points on manifold.
    t : list[int]
        Time index of simplex vertices.

    Returns
    -------
    V : float
        Volume of simplex.

    """
    
    X_vertex = X[t,:]
    ch = ConvexHull(X_vertex)
    
    return ch.volume