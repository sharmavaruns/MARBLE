#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Aug 31 18:13:32 2022

@author: gosztola
"""

from GeoDySys import geometry


def preprocessing(data, par):
    gauges, _ = geometry.compute_gauges(data, 
                                        par['local_gauge'], 
                                        par['n_geodesic_nb'])
    
    #kernels
    # kernel = geometry.gradient_op(data)
    kernel = geometry.DD(data.pos, data.edge_index, gauges)
    
    return gauges, kernel