#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov 11 00:25:19 2022

@author: zima
"""

import numpy as np 
import matplotlib.pyplot as plt 
plt.close('all')

plt.figure()

t = np.linspace(0.75,1.75,100)
s_d0 = np.sin(2*3.14*t)
I_var = 0

s_d1 = s_d0[1:] - s_d0[:-1]
s_d2 = s_d1[1:] - s_d1[:-1]

I1 = []
a_I1 = []
for i in range(len(s_d0)): 
    I_var = I_var + s_d0[i]
    I1.append(I_var)
    
    hip = s_d0[i]/I_var
    a_I1.append(  np.arctan2(hip,1))

#a_I1 = np.arctan2(s_d0,[1]*s_d0.size)*180/np.pi

a_I1 = np.array(a_I1)

plt.scatter(t,s_d0)
plt.scatter(t[1:],s_d1*10)
plt.scatter(t[2:],s_d2*100)
plt.scatter(t,a_I1)
plt.hlines(0,0.75,1.75)