#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov 11 14:38:21 2022

@author: zima
"""

import numpy as np 
import matplotlib.pyplot as plt


cte = 0.1
A = 10000
t = np.linspace(-100,100,10000)

f = lambda x: A*np.e**(-t*cte) 

y = f(t)

plt.plot(t,y)