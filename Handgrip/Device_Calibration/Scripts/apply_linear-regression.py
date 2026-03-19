#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Sep 25 10:38:51 2022

@author: zima
"""

import pandas as pd 
import matplotlib.pyplot as plt 
import numpy as np 
from sklearn.linear_model import LinearRegression as LR

data = pd.read_csv('calib_session.csv')

#data.loc[data['Kg'] ==0, 'Value'] = -187000

#print(data['Value'])

x = np.array(data['Value']).reshape((-1,1))
y = np.array(data['Kg'])


model = LR()
model.fit(x,y)
print(model.score(x,y))
print(model.intercept_, model.coef_[0],model.intercept_/ model.coef_[0] )

#-161978.40 = 1.2
#-174606.29 = 0.7

