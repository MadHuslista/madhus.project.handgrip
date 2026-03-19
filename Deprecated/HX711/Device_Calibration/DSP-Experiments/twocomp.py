#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Sep 25 05:54:49 2022

@author: zima
"""

def tb(bit):
    
    N = len(bit)
    val = -1*int(bit[0])*2**(N-1)
    
    for i in range(1,N): 
        print(N-i-1)
        val += int(bit[i])*2**(N-i-1)
    return val

def bt(bit): 
    a = list(bit)
    
    for i in range(len(a)):
        a[i] = conv(a[i])
    
    d = ""
    d = d.join(a)
    print(bit)
    print(d)
    

def conv(b): 
    if b == '1': 
        return '0'
    else: 
        return '1'

val = "111111001111101010100010"

print(tb(val))

