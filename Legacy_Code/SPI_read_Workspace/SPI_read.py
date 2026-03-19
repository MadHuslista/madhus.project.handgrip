#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Oct 31 11:28:04 2022

@author: zima
"""



import serial
import pandas as pd
import numpy as np 
import matplotlib.pyplot as plt

port = serial.Serial('/dev/ttyACM0', 115200)
sample = [] 

book = pd.DataFrame({'Point':[], 'Deci':[],'Deriv':[]})

while True: 

    chunk = port.readline().decode('UTF-8').strip().split('\t')
    #print(chunk)

    if chunk[0] == '': 
        continue
    sample.append(chunk)
    if int(chunk[0])%10 == 0: 
        print(chunk)
    if (int(chunk[0]) >= 2000):
        book = pd.DataFrame(np.array(sample), columns=['Point', 'Deci','Deriv'])
        break


book = book.astype('int')
print(book.info)

plt.plot(book['Point'], book['Deci'])
plt.plot(book['Point'], book['Deriv'])
plt.grid()


name = input("filename: ")
name = "Samples/" + name + ".npy"

np.save(name, book)
