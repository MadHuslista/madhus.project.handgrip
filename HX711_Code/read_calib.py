#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Sep 25 11:12:22 2022

@author: zima
"""

import serial
import pandas as pd
import numpy as np 

port = serial.Serial('/dev/ttyUSB0', 115200)
sample = [] 

book = pd.DataFrame({'Intercept':[], 'Value':[],'Kg':[]})

def add_data(samples, ref, g): 
    
    data = pd.DataFrame(np.array(samples), columns=['Intercept', 'Value']) 
    data['Kg'] = ref
    g = pd.concat([g,data], ignore_index=True, sort=False)    
    print(g.info())
    return g


n_samples = 100
sample_point = 0

wait = 'N'

while True: 
   
    chunk = port.readline().decode('UTF-8').strip().split('\t')
    
    if chunk[0] == "0": 
        print("Power Off")
        port.reset_input_buffer()
        continue
    
    elif (chunk[0] == "-2") or (chunk[0] == "-1"): 
        print(chunk)
        port.reset_input_buffer()
        sample = []
        sample_point = 0
        
        continue
    
    # elif (chunk[0] == "1"):
    #     chunk = chunk[1:]
    chunk = chunk[1:]
        

    # if chunk[0] == "404": 
    #     print("Power Off")
    #     port.reset_input_buffer()

    #     continue
    # continue    
    # if chunk[0] == '': 
    #     continue
    
    # if chunk[0] == "0":
    #     print(chunk)
    #     continue
    # elif chunk[0] == "1": 
    #     chunk = chunk[1:]
    

    sample.append(chunk)
    sample_point += 1
    

    if sample_point%10 == 0: 
        print(chunk)

    if (sample_point >= n_samples):
        ref = float(input('Ingrese ref Kg: '))

        if ref == -1:
            print("Saving File...")
            book.to_csv("calib_session1.csv", sep=",", index_label='Dat')
            break

        if ref == -2:
            print('Ignoring Segment..')
            sample = []
            sample_point = 0
            port.reset_input_buffer()
            continue

        print("Adding Segment...")
        book = add_data(sample,ref,book)

        while wait != 'Y':
            wait = input("Adapted?: ")

        sample = []
        sample_point = 0
        wait = "N"
        port.reset_input_buffer()



port.close()
