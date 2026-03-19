#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan  8 18:49:53 2023

@author: zima
"""

import numpy as np 
import matplotlib.pyplot as plt 

plt.close('all')
test = 2

name = ["01", "02", "03"]
name = "Samples/" + name[test] + ".npy"

#Columns = ['Point', 'Deci', 'Deriv']
data = np.load(name)[1:]
data = data.T




#Storage
d_0, d_1, d_2 = [],[],[]
st_pnts, end_pnts = [],[]
truemax_s, found_max = [],[]
r_sig, rmax_sig = [], []
d1_pred = []
diff = []

#Start Values
prev_d0 = -195680
prev2_d0 = -195680
prev_d1 = -195680

# Signals
start_press = False
end_press = True
peak_found = False
record_sig = False

#Thresholds
dd1_th = 5000
dd1_peak_th = 10000
deci_th_st = 185000
deci_th_end = 150000
true_max = [-1,-float('inf')]
t =0

for i in range(len(data[1][:-1])):     
    
    
    #Derivatives compute
    dd1 = data[1][i] - prev_d0    #Deci_(data[1]) - prevDeci = data[2]
    dd2 = dd1 - prev_d1           #Deriv_(data[2]) - preDeriv = deriv2
    
    d_0.append((data[1][i]))
    d_1.append(dd1)
    d_2.append(dd2)
    
    
    # Linear Predictor Implementation yf = 2y0 - yp
    xf = 0
    d1_p = (dd1 - prev_d1)*xf + dd1
    d1_pred.append(d1_p)
    # Linear Predictor Implementation yf = 2y0 - yp
    
    #Memory
    prev2_d0 = prev_d0
    prev_d0 = data[1][i]
    prev_d1 = dd1


    #Start Detection  ################################################################## 
    if end_press and dd1 > dd1_th and data[1][i] > -deci_th_st: 

      #Vline        
        st_pnts.append(data[0][i]) 
    
      #Signaling
        end_press = False       
        start_press = True
        record_sig = True

    #True Peak Detection ###############          
    if start_press and data[1][i]> true_max[1]: 
        true_max = [data[0][i],data[1][i], dd1] #RT Data
        true_rmax = t                                #Resume

    # #RT Peak Detection ###############              
    # if start_press and not(peak_found) and dd1 < dd1_peak_th: 

    #     peak_found = True    #Signaling
    #     peak_at = data[0][i]    #RT Data
    #     det_rmax = t                #Resume
        
    #RT Test Peak Detection ###############
    if start_press and not(peak_found) and d1_p < dd1_peak_th: 

        peak_found = True    #Signaling
        peak_at = data[0][i]    #RT Data
        det_rmax = t                #Resume


    #Signal Resume
    if record_sig: 
        r_sig.append([t, data[0][i],data[1][i], dd1, dd2])
        t = t +1
        
        # Integrator and Angle Detection 
        
    #     I_var = I_var + data[1][i]
    #     hip = data[1][i]/I_var
    #     a_I1.append( np.arctan2(hip,1)*180/np.pi) 

    #     I_1.append(I_var)
    
    # else: 
    #     I_1.append(I_var)
    #     I_var = 0
    #     a_I1.append(0)
        

    #End Detection #################################################################              
    if start_press and dd1 < 0 and dd2 > 0 and dd1 > -dd1_th and data[1][i] < -deci_th_end: 

        #Vlines
        end_pnts.append(data[0][i])

        # Signaling Reset
        start_press = False
        end_press = True   
        peak_found = False
        record_sig = False

        
        
        #Detection memory
        if peak_at != -1:
            found_max.append([peak_at, true_max[0]])
        peak_at = -1 #Reset
        
        #Real Peak Memory
        truemax_s.append(true_max)
        true_max = [-1,-float('inf')]

        #Resume Memory                
        rmax_sig.append([det_rmax, true_rmax])        
        t = 0


#Singal Accomodation
truemax_s = np.array(truemax_s).T
r_sig = np.array(r_sig).T
rmax_sig = np.array(rmax_sig).T
found_max = np.array(found_max).T

d_0 = np.array(d_0)
d_1 = np.array(d_1)
d_2 = np.array(d_2)
diff = np.array(diff)


# I_1 = np.array(I_1)
# a_I1 = np.array(a_I1)*100000
# #I_1 = I_1/I_1.max() * data[1].max()

################### Visualization

# Res Plot

# plt.figure()
# plt.hlines([-dd1_th,dd1_th], r_sig[0][0],r_sig[0][-1])
# plt.grid(which='both')

# plt.plot(r_sig[0], r_sig[2])
# plt.plot(r_sig[0], r_sig[3])
# #plt.plot(r_sig[0], r_sig[4])

# plt.scatter(r_sig[0], r_sig[2])
# plt.scatter(r_sig[0], r_sig[3])
# #plt.scatter(r_sig[0], r_sig[4])


# plt.vlines(rmax_sig[0], data.min(), data.max(), color='cyan')
#plt.vlines(rmax_sig[1], data.min(), data.max(), color='black')



#RT Plot       
plt.figure() 
plt.hlines([-dd1_peak_th,dd1_peak_th], data[0][0],data[0][-1])
plt.hlines([-deci_th_st,-deci_th_end], data[0][0],data[0][-1])
plt.grid(which='both')

plt.vlines(st_pnts, data.min(), data.max(), color='red')
plt.vlines(end_pnts, data.min(), data.max(), color='purple')
plt.vlines(truemax_s[0],data.min(), data.max(), color='cyan')
# plt.vlines(found_max[0],data.min(), data.max(), color='black')


plt.plot(data[0][:-1], d_0, label = 'd_0' )
plt.plot(data[0][:-1], d_1, label = 'd_1')
plt.plot(data[0][:-1], d_2, label = 'd_2')

# plt.plot(data[0][:-1], I_1, label = 'I_1')
# plt.plot(data[0][:-1], a_I1, label = 'a_I1')


plt.scatter(data[0][:-1], d_0)
plt.scatter(data[0][:-1], d_1)
plt.scatter(data[0][:-1], d_2)


# plt.plot(data[0][:-1], diff, label = 'diff')
# plt.scatter(data[0][:-1], diff)


# plt.scatter(data[0][:-1], I_1)
# plt.scatter(data[0][:-1], a_I1)



#Predictor 
# plt.plot(data[0][:-1]+xf,d1_pred/d_1.max(), label = 'd1_pred')
# plt.scatter(data[0][:-1]+xf,d1_pred/d_1.max(), label = 'd1_pred')
#Predictor





err =  found_max[0] - found_max[1]
erms = np.sqrt(sum(err**2)/len(err))
print("{}/{}".format(len(found_max[0]), len(truemax_s[0])))
print(err.mean(), err.std(), erms)
print(err)

plt.legend()
plt.show()


