#!/usr/bin/env python3
"""OPc = AES-128-ECB(Ki, OP) XOR OP   (3GPP TS 35.206 Milenage). Prints upper-case hex."""
import sys
from Crypto.Cipher import AES
ki, op = bytes.fromhex(sys.argv[1]), bytes.fromhex(sys.argv[2])
print(bytes(a ^ b for a, b in zip(AES.new(ki, AES.MODE_ECB).encrypt(op), op)).hex().upper())
