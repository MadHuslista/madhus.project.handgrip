#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Oct 31 11:52:04 2022

@author: zima
"""

import serial
import pandas as pd
import numpy as np 
import matplotlib.pyplot as plt
from filter_coefs import pCoeffs 

plt.close('all')

test = 3
name = ["baseline_00", "01_t", "02_t","03_t"]
name = "Samples/" + name[test] + ".npy"


data = np.load(name)[1:]

df = pd.DataFrame(np.array(data), columns=['Point', 'Deci','Deriv'])
data = data.T


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



dd1_th = 10000
dd1_peak_th = 10000
deci_th = 150000


start_press = False
end_press = True
peak_found = False
pred_peak_found = False
record_sig = False

prev_d0 = -195680
prev_d1 = -195680
prev2_d1 = -195680
prev3_d1 = -195680


d_0 = []
d_1 = []
d_2 = []
I_1 = []
a_I1 = []
I_var = 0

d1_pred = []


# #Filter Implementation

# def LPF(buf, W_pos, s):
#     out_val = 0
#     fir_pos = W_pos
    
#     #Los coeffs están en time reverse order (el b_t0 es el último, y b_tlast es preset time). 
    
#     for i in range(1,len(pCoeffs)+1): 
#         val = buf[fir_pos] * pCoeffs[-i]
#         out_val = out_val + val 
        
#         fir_pos = (fir_pos -1) + (fir_pos <= 0)*s

#     return out_val

# size = 10 
# d_1f = []

# buffer = [prev1]*10
# Wbuf_pos = 0



truemax_s = []
found_max = []

true_max = [-1,-float('inf')]
peak_at = -1
r_sig = []
rmax_sig = []
t = 0

st_pnts = []
end_pnts = []


for i in range(len(data[2][:-1])):     
    
    dd1 = data[1][i] - prev_d0    #Deci_(data[1]) - prevDeci = data[2]
    dd2 = dd1 - prev_d1           #Deriv_(data[2]) - preDeriv = deriv2
    
    
    d_0.append((data[1][i]))
    d_1.append(dd1)
    d_2.append(dd2)
    
    # #Filter implementation 
    # buffer[Wbuf_pos] = dd1
    # Wbuf_pos = (Wbuf_pos +1)*(Wbuf_pos < (size-1))

    # if i > size: 
    #     d_1f.append(
    #             #t       d_1     d_1f
    #         [data[0][i], dd1, LPF(buffer, Wbuf_pos, size)]
    # )
    # #Filter implementation 
    
    
    # # Linear Predictor Implementation yf = 2y0 - yp
    # d1_p = 2*dd1 - prev_d1
    # d1_pred.append(d1_p)
    # # Linear Predictor Implementation yf = 2y0 - yp
    
#     # Neville Predictor
#     dt_x = [-1, 0]
#     dt_y = [prev_d1, dd1]
# #    print(np.array(dt_y))
    
#     d1_p = P(0,len(dt_x)-1, 1, dt_x, dt_y)
#     d1_pred.append(d1_p)    
#     # Neville Predictor
    
    prev_d0 = data[1][i]
    prev3_d1 = prev2_d1
    prev2_d1 = prev_d1
    prev_d1 = dd1


    #Start Detection  ################################################################## 
    if end_press and dd1 > dd1_th and data[1][i] > -deci_th: 
        st_pnts.append(data[0][i])
    
        end_press = False
        start_press = True
        record_sig = True

    #True Peak Detection ###############          
    if start_press and data[1][i]> true_max[1]: 
        true_max = [data[0][i],data[1][i], dd1]
        rmax = t

    #RT Peak Detection ###############              
    if start_press and not(peak_found) and dd1 < dd1_peak_th: 
        peak_found = True
        print(dd1, end = "  ")
        peak_at = data[0][i]

        
    if start_press and not(pred_peak_found) and dd1 < dd1_peak_th: 
        pred_peak_found = True
        rpeak_at = t
        


    if record_sig: 
        r_sig.append(
            [t, data[0][i],data[1][i], dd1, dd2]
            )
        t = t +1
        
        # Integrator and Angle Detection 
        
        I_var = I_var + data[1][i]
        hip = data[1][i]/I_var
        a_I1.append( np.arctan2(hip,1)*180/np.pi) 

        I_1.append(I_var)
    
    else: 
        I_1.append(I_var)
        I_var = 0
        a_I1.append(0)
        

    #End Detection #################################################################              
    if start_press and dd1 < 0 and dd2 > 0 and dd1 > -dd1_th and data[1][i] < -deci_th: 
        #plt.vlines(data[0][i], data.min(), data.max(), color='purple')
        start_press = False
        end_press = True   
        peak_found = False
        pred_peak_found = False
        record_sig = False
        end_pnts.append(data[0][i])
        
        
        if peak_at != -1:
            found_max.append([peak_at, true_max[0]])
        
        rmax_sig.append([rpeak_at, rmax])
        truemax_s.append(true_max)
        true_max = [-1,-float('inf')]
        peak_at = -1
        
        t = 0



truemax_s = np.array(truemax_s).T
r_sig = np.array(r_sig).T
rmax_sig = np.array(rmax_sig).T
found_max = np.array(found_max).T


I_1 = np.array(I_1)
a_I1 = np.array(a_I1)*100000
#I_1 = I_1/I_1.max() * data[1].max()

# # Res Plot

# plt.figure()
# plt.hlines([-dd1_th,dd1_th], r_sig[0][0],r_sig[0][-1])
# plt.grid(which='both')

# plt.plot(r_sig[0], r_sig[2])
# plt.plot(r_sig[0], r_sig[3])
# plt.plot(r_sig[0], r_sig[4])

# plt.scatter(r_sig[0], r_sig[2])
# plt.scatter(r_sig[0], r_sig[3])
# plt.scatter(r_sig[0], r_sig[4])


# plt.vlines(rmax_sig[0], data.min(), data.max(), color='cyan')
# #plt.vlines(rmax_sig[1], data.min(), data.max(), color='black')



#RT Plot       
plt.figure() 
plt.hlines([-dd1_th,dd1_th], data[0][0],data[0][-1])
plt.grid(which='both')

plt.vlines(st_pnts, data.min(), data.max(), color='red')
plt.vlines(end_pnts, data.min(), data.max(), color='purple')
plt.vlines(truemax_s[0], data.min(), data.max(), color='cyan')
plt.vlines(found_max[0], data.min(), data.max(), color='black')


plt.plot(data[0][:-1], d_0, label = 'd_0' )
plt.plot(data[0][:-1], d_1, label = 'd_1')
plt.plot(data[0][:-1], d_2, label = 'd_2')
# plt.plot(data[0][:-1], I_1, label = 'I_1')
# plt.plot(data[0][:-1], a_I1, label = 'a_I1')


plt.scatter(data[0][:-1], d_0)
plt.scatter(data[0][:-1], d_1)
plt.scatter(data[0][:-1], d_2)
# plt.scatter(data[0][:-1], I_1)
# plt.scatter(data[0][:-1], a_I1)
# # Filter Implementation 
# d_1f = np.array(d_1f).T
# plt.scatter(d_1f[0],d_1f[2])
# plt.plot(d_1f[0],d_1f[2],  label = 'd_1f')

# # Filter Implementation 

#Predictor 
# plt.plot(data[0][:-1], d1_pred, label = 'd1_pred')
# plt.scatter(data[0][:-1], d1_pred)
#Predictor


plt.legend()
plt.show()



err =  found_max[0] - found_max[1]
erms = np.sqrt(sum(err**2)/len(err))
print("{}/{}".format(len(found_max[0]), len(truemax_s[0])))
print(err.mean(), err.std(), erms)
print(err)









######################### LEG CODE #############3
# deriv2 = data[2][1:] - data[2][:-1]
# dd1_sig = []
# dd2_sig = []


# for i in range(len(data[0])): 
#         dd1 = data[1][i] - prev1
#         dd2 = dd1 - prev2 
        
#         prev2 = dd1
#         prev1 = data[1][i]
        
#         dd1_sig.append(dd1)
#         dd2_sig.append(dd2)
        
# plt.plot(data[0], dd1_sig, label = "DD1_rt")
# plt.plot(data[0], dd2_sig, label = "DD2_rt")
# plt.legend()


# for i in range(len(data[2][:-1])):     
    
#     if end_press and data[2][i] > dd1_th: 
#         plt.vlines(data[0][i], data.min(), data.max(), color='yellow')
#         end_press = False
#         start_press = True
    
#     if start_press and data[2][i] < 0 and deriv2[i] > 0 and data[2][i] > -dd1_th and data[1][i] < -deci_th: 
#         plt.vlines(data[0][i], data.min(), data.max(), color='black')
#         start_press = False
#         end_press = True

