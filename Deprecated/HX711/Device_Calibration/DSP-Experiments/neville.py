#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov 11 04:20:48 2022

@author: zima
"""

def neville(datax, datay, x):
    """
    Finds an interpolated value using Neville's algorithm.
    Input
      datax: input x's in a list of size n
      datay: input y's in a list of size n
      x: the x value used for interpolation
    Output
      p[0]: the polynomial of degree n
    """
    n = len(datax)
    p = n*[0]
    for k in range(n):
        for i in range(n-k):
            if k == 0:
                p[i] = datay[i]
            else:
                p[i] = ((x-datax[i+k])*p[i]+ (datax[i]-x)*p[i+1])/ \
                                    (datax[i]-datax[i+k])
    return p[0]

import numpy as np 
import matplotlib.pyplot as plt 
import time

def P(i,j, x, dt_x, dt_y): 
    
    n = len(dt_x)
    if (n < j) or (j < i): 
        return 'f'
    
    if i == j: 
        return dt_y[i]
    
    else: 
        num = (x - dt_x[i])* P(i+1,j, x, dt_x, dt_y) - (x- dt_x[j])*P(i, j-1, x, dt_x, dt_y)
        den = dt_x[j] - dt_x[i]
        return num/den 




f = lambda x: 3*x**2  + 4*x -5

t = np.linspace(-10,100,1000)
y = f(t)

plt.plot(t, y)


dt_x = np.array([-5, 0, 5])
dt_y = f(dt_x)

plt.scatter(dt_x,dt_y)

interp_x = 81
nev_st = time.time()
interp_y = neville(dt_x, dt_y, interp_x)
nev_del = time.time() - nev_st

rec_st = time.time()
p_y = P(0,2, interp_x, dt_x, dt_y)
rec_del = time.time() - rec_st

plt.scatter(interp_x,p_y)










