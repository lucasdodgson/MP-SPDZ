import math 
import random
import sys 
import os
from scipy.stats import sem
from statistics import fmean
import time

#MPC protocol to use in evaluation 
protocol = "mascot" 

debug = False
statistical_securtiy = 64

prime = 170141183460469231731687303715885907969
#prime = 57896044618658097711785492504343953926634992332820282019728792003956566065153

ell_com = None
ell_eval = None
ell = None

def parse_args():
    global ell_com, ell_eval, ell
    ell_com = int(sys.argv[1])
    ell_eval = int(sys.argv[2])
    ell = ell_com + ell_eval
    print("ell_com:", ell_com, "ell_eval:", ell_eval)


def compile_programs():
    os.system(f"./compile.py oprf_leg_ward {ell_com} {ell_eval} -O -D -P {prime}")


def offline_phase():
    start_time = time.time()
    offline_run_command1 = f"./mascot-offline.x  oprf_leg_ward-{ell_com}-{ell_eval} -P {prime} -S {statistical_securtiy}" 
    os.system(f"{offline_run_command1} -p 0 & {offline_run_command1} -p 1")
    offline_time = time.time()-start_time
    print()
    print(f"offline phase took {offline_time} seconds")

def eval_poly(p,x):
    e = 0
    xi = 1
    for i,ai in enumerate(p):
        e = (e + ai * xi) % prime
        xi = (xi * x) % prime
    return e 

def legendre_symbol(x):
    l = pow(x, (prime-1)//2, prime)
    if l > prime/2:
        l -= prime
    return l

def generate_inputs():

    # sample coefficients of f(x)
    f = [ random.randrange(prime) for _ in range(ell)]

    # evaluate f and f^2
    a = [ eval_poly(f, i) for i in range(ell) ]
    b = [ (eval_poly(f, i)**2 % prime) for i in range(2*ell - 1) ]

    # pick server key K and client input X
    K = random.randrange(prime)
    X = random.randrange(prime)

    # write coefficients to server input file
    with open("Player-Data/Input-P1-0","w", encoding='utf-8') as f:
        f.write(" ".join([ str(x) for x in (a + b) ]) + " " + str(K) + " \n ")

    # inputs from client
    with open("Player-Data/Input-P0-0","w", encoding='utf-8') as f:
        f.write(str(X) + " \n ")


    # choose random public r for probabilistic check 
    r = random.randrange(prime)

    # compute interpolation coefficients
    A = []
    for i in range(ell):
        lc_num = 1
        lc_denom = 1
        for j in range(ell):
            if i == j:
                continue
            lc_num = (lc_num * (r - j)) % prime
            lc_denom = (lc_denom * (i-j)) % prime
        lc = (lc_num * pow( lc_denom, -1, prime)) % prime
        A.append(lc)

    B = []
    for i in range(2*ell - 1):
        lc_num = 1
        lc_denom = 1
        for j in range(2*ell - 1):
            if i == j:
                continue
            lc_num = (lc_num * (r - j)) % prime
            lc_denom = (lc_denom * (i-j)) % prime
        lc = (lc_num * pow( lc_denom, -1, prime)) % prime
        B.append(lc)

    # choose random offsets points 
    # TODO: these should be fixed between evaluations of the OPRF instead of chosen each time

    I = [random.randrange(prime) for _ in range(ell)]

    Alpha = [ random.randrange(prime) for _ in range(ell_com) ]

    with open(f"Programs/Public-Input/oprf_leg_ward-{ell_com}-{ell_eval}","w", encoding='utf-8') as f:
        f.write(" ".join([ str(x) for x in ([r] + A + B + I + Alpha) ]) + "\n")
    

    key_commitment = [ legendre_symbol(K + i) for i in I[:ell_com] ]
    evaluation = [legendre_symbol(K + X + i) for i in I[ell_com:]]

    masked_output = [ (K + I[i])*b[i] for i in range(ell_com) ] 

    output_check_value = sum([Alpha[i] * masked_output[i] for i in range(ell_com)]) % prime

    return key_commitment, evaluation, masked_output, I, output_check_value


def run_protocol():

    output = os.popen(f"./Scripts/mascot.sh oprf_leg_ward-{ell_com}-{ell_eval} -F").read()
    print("output of protocol:")

    # extract legendre symbols
    legendre_symbols = []
    check_value = None
    lines = output.split("\n")
    for line in lines:
        print(line)
        if "masked output:" in line:
            mo = int(line[15:])
            l = pow(mo, (prime-1)//2, prime)
            if l> prime//2:
                l = l-prime
            legendre_symbols.append(l)
        if "check_value:" in line:
            check_value = int(line[12:])

    print("evaluation:", legendre_symbols)

    return check_value, legendre_symbols

        
if __name__ == '__main__':
    try:
        "Create directories, required on first run"
        os.system(f'mkdir Programs/Public-Input && mkdir Player-Data')
    except:
        pass

    parse_args()
    compile_programs()
    
    print()
    print("==========      Finished compiling programs       ==========")
    print()

    offline_phase()
    
    print()
    print("==========      Finished offline phase       ==========")
    print()
    
    com, eval, masked_output, I, check_value = generate_inputs()
    
    print()
    print("==========      Finished generating inputs and randomness       ==========")
    print()
    
    check_value2, eval2 = run_protocol()
    
    print()
    print("==========      Finished running protocol       ==========")
    print()

    if check_value2 < 0:
        check_value2 += prime

    if check_value != check_value2:
        print("check value is wrong!")
        print(check_value, check_value2)
    else:
        print("check value is correct!")

    if eval2 != eval:
        print("evaluation is wrong!")
        print("evaluation is supposed to be", eval)
    else:
        print("evaluation is correct!")

    