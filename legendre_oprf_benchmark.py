import math 
import random
import sys 
import os
from scipy.stats import sem
from statistics import fmean



full_benchmark = False #If should run full benchmark suite or just a single evaluation. Note: If running full benchmark please make sure to set nparallel to be equal to or greater than 100, otherwise not enough inputs will be generated. 
online_phase_benchmark = False #If benchmark should include time used for preprocessing or consider only the online phase. 

protocol = "mascot" #MPC protocol to use in evaluation 
debug = False 
statistical_securtiy = 64


def parse_args():
    """Parse system arguments to get exact version we are running (number parallel evaluations, prime bit length and if using version with more preprocessing)"""

    # First system argument: Number of symbols to evaluate in parallel 
    nparallel = 1
    if len(sys.argv) > 1:
        nparallel = int(sys.argv[1])

    # Evaluation length
    eval_len = 321 #math.ceil(prime.bit_length () * 2.5000001)

    # Second system argument: Optionally specify to use 256 bit prime instead of 128 bit.
    prime = 170141183460469231731687303715885907969
    bit_len = 128
    if len(sys.argv) > 2 and int(sys.argv[2]) == 256:
        prime = 57896044618658097711785492504343953926634992332820282019728792003956566065153
        eval_len = 641
        bit_len = 256

    # Third system argument: If want to use "improved" version that uses more preprocessing
    improved = False 
    version = "oprf_leg"
    if len(sys.argv) > 3: #Use improved version that moves more to preprocessing phase.
        version = "oprf_leg_improved"
        improved = True 
    
    print(sys.argv)

    print("Running with:", version, prime.bit_length(), "Evaluation length:", eval_len)
    return nparallel, eval_len, prime, version, improved

def generate_input(prime, eval_len, nparallel, improved):
    """Generate input for both parties and write to input file location."""
    user_input = [str(random.randint(0,prime)) for _ in range(0, 2 * eval_len * nparallel + nparallel)]
    server_input = [str(random.randint(0,prime)) for _ in range(0,eval_len * nparallel + 1)]

    if improved:
        user_input = [str(random.randint(0,prime)) for _ in range(0, nparallel)]
        server_input = [str(random.randint(0,prime)) for _ in range(0, + 1)]

    #Generate the indexes
    indexes = [random.randint(0,prime) for _ in range(0,eval_len)]

    if debug:
        print("Offset Indexes:", indexes)
        print("User input:", " ".join(user_input))
        print("Server input:", " ".join(server_input))

    #Write the public input (randomly chosen indexes, and the parties input)
    with open(f"Programs/Public-Input/{version}-{nparallel}-{eval_len}","w", encoding='utf-8') as f:
        str_indexes = [str(i) for i in indexes]
        f.write(" ".join(str_indexes) + " \n ")
    with open("Player-Data/Input-P0-0","w", encoding='utf-8') as f:
        f.write(" ".join(user_input) + " \n ")
    with open("Player-Data/Input-P1-0","w", encoding='utf-8') as f:
        for i in range(nparallel-1): #To read a nparallel vector all containing the same key, need to write it nparallel times to the file.
            f.write(f"{server_input[0]} ")
        f.write(" ".join(server_input) + " \n ")

    server_k = int(server_input[0])
    
    #Another (slight) limitation of the library, is that for our custom output-masking implementation it's easiest if we specify those also as "public inputs". Observe though, that there is no point in time in which the server will need those. An alternative would be for us to output the masked values from the script that runs in Mascot and then have our "checker" compute the Legendre Symbols. This approach doesn't direclty work though, since the library only supports outputting 64-bit elements.
    str_masks = user_input[nparallel + eval_len * nparallel:]
    with open(f"Programs/Public-Input/{version}-{nparallel}-{eval_len}","a", encoding='utf-8') as f:
        f.write(" ".join(str_masks) + "\n")

    return user_input, server_k, indexes


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
            if online_phase_benchmark:
                # Batch size has no effect for the online phase, so there is no point in using various values for it in that case
                batch_size_arr = [1000]
        else:
            nparallel_arr = [nparallel]
            batch_size_arr = [1000]
            repeat = 1
        #Output file to log experiment runs 
        output_file = open(f"output_{version}_{eval_len}_{protocol}.csv", 'w')
        output_file.write(f'Number Parallel,Batch Size,Numer Rounds,Amount of Data,Time in seconds\n')
        
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
                    resp = os.popen(f"Scripts/{protocol}.sh {version}-{nparallel}-{eval_len} --direct -b {batch_size} -P {prime} -S {statistical_securtiy} {additional}").read()
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

                    all_times.append(time)
                    if time == 'Failed to find':
                        print("no time:", resp)
                    all_mb_sent.append(mb_sent)
                    all_mb_total.append(mb_total)
                    print(batch_size, nparallel, rounds, all_times, flush=True)
                print("Finished experiment run", flush=True)
                print(all_mb_sent, all_mb_total, all_times, flush=True)
                try:
                    # Log output and write benchmark results to a file.
                    print(f"Prime {prime}. Run with {nparallel} parallel evaluations, ran {len(all_mb_sent)} many repetitions. Used batch size of {batch_size}. It took {rounds} many rounds, total data sent is {fmean(all_mb_total)}+-{sem(all_mb_total)} MB, and data sent by party one is {fmean(all_mb_sent)}+-{sem(all_mb_sent)} MB. Execution took {fmean(all_times)}+-{sem(all_times)} seconds ", flush = True)
                    output_file.write(f'{nparallel},{batch_size},{rounds},{fmean(all_mb_total)}+-{sem(all_mb_total)},{fmean(all_times)}+-{sem(all_times)}\n')
                except:
                    print(f"Prime {prime}. Run with {nparallel} parallel evaluations, ran {len(all_mb_sent)} many repetitions. Used batch size of {batch_size}. It took {rounds} many rounds, total data sent is ?")
                    output_file.write(f'{nparallel},{batch_size},{rounds},?,?\n')
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
    nparallel, eval_len, prime, version, improved = parse_args()
    user_input, server_k, indexes = generate_input(prime, eval_len, nparallel, improved)
    run_protocol(full_benchmark, version, nparallel, protocol, prime, online_phase_benchmark)
    verify_results(eval_len, nparallel, user_input, server_k, indexes, prime)