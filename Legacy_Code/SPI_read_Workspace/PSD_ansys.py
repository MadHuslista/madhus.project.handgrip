#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Nov  1 08:10:52 2022

@author: zima
"""

import serial
import pandas as pd
import numpy as np 
import matplotlib.pyplot as plt
from psd import *
from filter_coefs import pCoeffs 
plt.close('all')

name = ["baseline_00", "01_t", "02_t","03_t"]
name = "Samples/" + name[3] + ".npy"

data = np.load(name)[1:].T


def LPF(buf, W_pos):
    out_val = 0
    fir_pos = W_pos
    
    #Los coeffs están en time reverse order (el b_t0 es el último, y b_tlast es preset time). 
    
    for i in range(1,len(pCoeffs)+1): 
        val = buf[fir_pos] * pCoeffs[-i]
        out_val = out_val + val 
        
        fir_pos = (fir_pos -1) + (fir_pos <= 0)*10

    return out_val

#psd(data[1], fs = 25.64) #1000/39 ms

zero = -195680
prev = zero 

buffer = [zero] * 10
Wbuf_pos = 0

out_sig = []
d1_s = []

for i in range(len(data[0])):
    
    
    d_1 = data[1][i] - prev
    prev = data[1][i]
    
    # buffer[Wbuf_pos] = data[1][i]
    buffer[Wbuf_pos] = d_1
    Wbuf_pos = (Wbuf_pos +1)*(Wbuf_pos < 9)
    
    if i > 30: 
        out_sig.append(
            #t          deci          d1 filt         d1 orig
        [data[0][i],data[1][i],LPF(buffer, Wbuf_pos), d_1]
        )
    
out_sig = np.array(out_sig).T
    
plt.scatter(out_sig[0], out_sig[1], label = 'sig')
plt.scatter(out_sig[0], out_sig[2], label = 'd1 filt')
plt.scatter(out_sig[0], out_sig[3], label = 'd1 orig')

plt.plot(out_sig[0], out_sig[1], label = 'sig')
plt.plot(out_sig[0], out_sig[2], label = 'd1 filt')
plt.plot(out_sig[0], out_sig[3], label = 'd1 orig')
plt.grid()
plt.legend()
#plt.plot(data[0], data[1])

    
# psd(out_sig[1], fs = 25.64) #1000/39 ms
# psd(out_sig[2], fs = 25.64) #1000/39 ms

    
    