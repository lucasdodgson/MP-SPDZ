import math 
import random
import sys 
import os
from scipy.stats import sem
from statistics import fmean

#If should run full benchmark suite or just a single evaluation. Note: If running full benchmark please make sure to set nparallel to be equal to or greater than 100, otherwise not enough inputs will be generated. 
full_benchmark = False
 
#If benchmark should include time used for preprocessing or consider only the online phase. 
online_phase_benchmark = False

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
    os.system(f"./compile.py oprf_leg_ward_1 {ell_com} {ell_eval} -O -D -P {prime}")
    os.system(f"./compile.py oprf_leg_ward_2 {ell_com} {ell_eval} -O -D -P {prime}")


def offline_phase():
    offline_run_command1 = f"./mascot-offline.x  oprf_leg_ward_1-{ell_com}-{ell_eval} -P {prime} -S {statistical_securtiy} -F x" 
    os.system(f"{offline_run_command1} -p 0 & {offline_run_command1} -p 1")
    offline_run_command2 = f"./mascot-offline.x  oprf_leg_ward_2-{ell_com}-{ell_eval} -P {prime} -S {statistical_securtiy}" 
    s.system(f"{offline_run_command2} -p 0 -m old & {offline_run_command2} -p 1 -m old")

def eval_poly(p,x):
    e = 0
    xi = 1
    for i,ai in enumerate(p):
        e = (e + ai * xi) % prime
        xi = (xi * x) % prime
    return e 

def phase1():

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

    #  run phase 1
    os.system(f"./Scripts/mascot.sh oprf_leg_ward_1-{ell_com}-{ell_eval}")

def phase2():
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


    with open(f"Programs/Public-Input/oprf_leg_ward_2-{ell_com}-{ell_eval}","w", encoding='utf-8') as f:
        f.write(" ".join([ str(x) for x in ([r] + A + B + I) ]) + "\n")

    #  run phase 2
    output = os.popen(f"./Scripts/mascot.sh oprf_leg_ward_2-{ell_com}-{ell_eval} -b {ell+10} -m old").read()
    print("output of protocol:")

    # extract legendre symbols
    legendre_symbols = []
    lines = output.split("\n")
    for line in lines:
        print(line)
        if "masked output:" in line:
            mo = int(line[15:])
            l = pow(mo, (prime-1)//2, prime)
            if l> prime//2:
                l = l-prime
            legendre_symbols.append(l)
    
    print("key commitment:", legendre_symbols[:ell_com])
    print("evaluation:", legendre_symbols[ell_com:])


    


def run_protocol(full_benchmark, version, nparallel, protocol, prime, online_phase_benchmark = False,):
    """Once input files have been generated, actually runs the MPC protocol. Argument is used to specify if full benchmark suite should be run or just a single evaluation as well as arguments for the actual MPC protocol being run. 
    Also an optional argument to choose if want benchmark results to include preprocessing phase or not"""
    if False: 
        #No longer used, but gives option to run evaluation and get number of rounds in a single command.
        os.system(f"Scripts/compile-run.py {version} {nparallel} {eval_len} -E {protocol} -P {prime}")
    else:
        if full_benchmark:
            nparallel_arr = [1,10]
            batch_size_arr = [65, 185, 325, 645, 1285, 3250, 6500]
            repeat = 100
            if online_phase_benchmark or protocol == "hemi":
                # Batch size has no effect for the online phase, so there is no point in using various values for it in that case
                batch_size_arr = [1000]
        else:
            nparallel_arr = [nparallel]
            batch_size_arr = [322] # 322 , 643
            repeat = 1
        #Output file to log experiment runs 
        output_file = open(f"output_{version}_{eval_len}_{protocol}_{online_phase_benchmark}.csv", 'w')

        output_file.write(f'Number Parallel,Batch Size,Numer Rounds,Amount of Data,Time in seconds,Version,Evaluation Length,Protocol,Online\n')
        
        #Make offline and online functionality for protocol. The offline phase is used to run the offline phase seperately from the online phase. Only a few protocol suties in MP-SPDZ support this, but Mascot is one of them.
        os.system(f"make {protocol}-offline.x")
        os.system(f"make -j8 {protocol}-party.x")

        npar = nparallel
        #Run protocol for all batch sizes and number of parallel executions we are considering 
        for nparallel in nparallel_arr:
            for batch_size in batch_size_arr:

                all_times = []
                all_mb_sent = []
                all_mb_total = [] 
                all_rounds = []
                #Compile the program        
                os.system(f"./compile.py {version} {nparallel} {eval_len}  -O -D -P {prime}")

                #Make sure public-input file exists for this exact configuration.
                os.system(f'cp Programs/Public-Input/{version}-{npar}-{eval_len} Programs/Public-Input/{version}-{nparallel}-{eval_len}')

                #Run repeat many repetitions
                for _ in range(repeat):
                    # Run offline phase to prepare data 
                    offline_run_command = f"./{protocol}-offline.x  {version}-{nparallel}-{eval_len} -P {prime} -S {statistical_securtiy}" 
                    os.system(f"{offline_run_command} -p 0 & {offline_run_command} -p 1")

                    # This lets us specify if we want to perform the preprocessing live or use the above generated values. -F says to use preprocessing data saved to a file, so if -F is specified we skip the offline phase.
                    additional = "" 
                    if online_phase_benchmark:
                        additional = "-F"

                    # Run the protocol and then parse the output to extract the rounds, mb sent and time required.
                    resp = os.popen(f"Scripts/{protocol}.sh {version}-{nparallel}-{eval_len} -b {batch_size} --direct -P {prime} -S {statistical_securtiy} {additional}").read()
                    if debug:
                        print(resp)
                    rounds = 0
                    mb_sent = 0.0
                    mb_total = 0.0
                    time = 'Failed to find'
                    for i in resp.split("\n"):
                        if "Data sent =" in i:
                            mb_sent = float(i.split("=")[1].split()[0])
                            rounds = int(i.split("~")[1].split()[0])
                        if "data sent" in i: 
                            mb_total = float(i.split("=")[1].split()[0])
                        if "Time =" in i:
                            time = float(i.split("=")[1].split()[0])
                            if 'seconds' not in i:
                                raise Exception(f"Time not in seconds? {i}")
                    if time == 'Failed to find':
                        print("no time:", resp)
                    else:
                        all_rounds.append(rounds)
                        all_times.append(time)
                        all_mb_sent.append(mb_sent)
                        all_mb_total.append(mb_total)
                    print(batch_size, nparallel, rounds, all_times, flush=True)
                print("Finished experiment run", flush=True)
                print(all_mb_sent, all_mb_total, all_times, all_rounds, flush=True)
                try:
                    if repeat == 1:
                        print(f"Prime {prime}. Run with {nparallel} parallel evaluations, ran {len(all_mb_sent)} many repetitions. Used batch size of {batch_size}. It took {fmean(all_rounds)} many rounds, total data sent is {fmean(all_mb_total)} MB, and data sent by party one is {fmean(all_mb_sent)} MB. Execution took {fmean(all_times)} seconds ", flush = True)
                        output_file.write(f'{nparallel},{batch_size}, {fmean(all_rounds)},{fmean(all_mb_total)},{fmean(all_times)},{version},{eval_len},{protocol},{online_phase_benchmark}\n')
                    else:
                        # Log output and write benchmark results to a file.
                        print(f"Prime {prime}. Run with {nparallel} parallel evaluations, ran {len(all_mb_sent)} many repetitions. Used batch size of {batch_size}. It took {fmean(all_rounds)}+-{sem(all_rounds)} many rounds, total data sent is {fmean(all_mb_total)}+-{sem(all_mb_total)} MB, and data sent by party one is {fmean(all_mb_sent)}+-{sem(all_mb_sent)} MB. Execution took {fmean(all_times)}+-{sem(all_times)} seconds ", flush = True)
                        output_file.write(f'{nparallel},{batch_size}, {fmean(all_rounds)}+-{sem(all_rounds)},{fmean(all_mb_total)}+-{sem(all_mb_total)},{fmean(all_times)}+-{sem(all_times)},{version},{eval_len},{protocol},{online_phase_benchmark}\n')
                except:
                    print(f"Prime {prime}. Run with {nparallel} parallel evaluations, ran {len(all_mb_sent)} many repetitions. Used batch size of {batch_size}. It took {rounds} many rounds, total data sent is ?")
                    output_file.write(f'{nparallel},{batch_size},{rounds},?,?,{version},{eval_len},{protocol},{online_phase_benchmark}\n')
        output_file.close()


def verify_results(eval_len, nparallel, user_input, server_k, indexes, prime):
    """Verify that the computed Legendre Symbols are the correct ones"""
    
    # Read the output binary.    
    results = [] 
    with open("Player-Data/Binary-Output-P0-0",'rb') as f:
        a = f.read()
        for i in range(0,len(a),8):
            res = int.from_bytes(a[i:i+8],'little')
            results.append(res)


    # Locally compute expected output 
    for i in range(eval_len):
        for j in range(nparallel):
            user_x = int(user_input[j])
            
            res = (user_x + server_k + indexes[i])
            bitres = pow(res, (prime-1)//2,prime)
            
            if debug:
                print(j+i*nparallel,user_x, server_k, bitres)
            
            if results[j+i*nparallel] == 1 or bitres == 1:
                # Compare the two output bits, ensure that if one is 1 then so is the other.
                if results[j+i*nparallel] != bitres:
                    raise Exception(f"Verifying results failed! Something went wrong {results[j+i*nparallel]} {bitres}")
    print("Test passed")
    print(version, nparallel, len(results))

        
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
    
    #offline_phase()
    
    #print()
    #print("==========      Finished offline_phase       ==========")
    #print()
    
    phase1()
    
    print()
    print("==========      Finished phase 1       ==========")
    print()
    
    phase2()
    
    print()
    print("==========      Finished phase 2       ==========")
    print()