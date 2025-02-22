import math 
import random
import sys 
import os
from scipy.stats import sem
from statistics import fmean
from sympy.ntheory import primefactors

#If should run full benchmark suite or just a single evaluation. Note: If running full benchmark please make sure to set nparallel to be equal to or greater than 100, otherwise not enough inputs will be generated. 
full_benchmark = False

#If benchmark should include time used for preprocessing or consider only the online phase. 
online_phase_benchmark = False

 #MPC protocol to use in evaluation 
protocol = "mascot" 

debug = False 
statistical_securtiy = 64

bit_len = 128 
def parse_args():
    """Parse system arguments to get exact version we are running (number parallel evaluations, prime bit length and if using version with more preprocessing)"""
    global bit_len
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

    order = 2 
    # Third system argument: Order of residuals to be used (By default 2 which is equivalent to the legendre symbol)
    if len(sys.argv) > 3:
        order = int(sys.argv[3])
        eval_len = math.ceil(bit_len * (2.5)/(math.log2( (order) / (1 + order/math.sqrt(prime) + 2 * order / prime))))

    # Fourth system argument: If want to use "improved" version that uses more preprocessing
    improved = False 
    version = "oprf_higher_order_residuals"
    if len(sys.argv) > 4: #Use improved version that moves more to preprocessing phase.
        version = "oprf_higher_order_residuals_improved"
        improved = True 
    
    print(sys.argv)
    print("Running with:", version, prime.bit_length(), "Evaluation length:", eval_len, 'order', order)
    return nparallel, eval_len, prime, version, improved, order

def generate_input(prime, eval_len, nparallel, improved, order):
    """Generate input for both parties and write to input file location."""
    user_input = [str(random.randint(0,1000)) for _ in range(0, 2 * eval_len * nparallel + nparallel)]
    server_input = [str(random.randint(0,1000)) for _ in range(0,eval_len * nparallel + 1)]

    if improved:
        user_input = [str(random.randint(0,1000)) for _ in range(0, nparallel)]
        server_input = [str(random.randint(0,1000)) for _ in range(0, + 1)]

    #Generate the indexes
    indexes = [random.randint(0,1000) for _ in range(0,eval_len)]

    if debug:
        print("Offset Indexes:", indexes)
        print("User input:", " ".join(user_input))
        print("Server input:", " ".join(server_input))

    generator = find_gen(prime)
    #Write the public input (randomly chosen indexes, and the parties input)
    with open(f"Programs/Public-Input/{version}-{nparallel}-{eval_len}-{order}-{generator}","w", encoding='utf-8') as f:
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
    with open(f"Programs/Public-Input/{version}-{nparallel}-{eval_len}-{order}-{generator}","a", encoding='utf-8') as f:
        f.write(" ".join(str_masks) + "\n")

    return user_input, server_k, indexes, generator


def run_protocol(full_benchmark, version, nparallel, protocol, prime, order, generator, online_phase_benchmark = False):
    """Once input files have been generated, actually runs the MPC protocol. Argument is used to specify if full benchmark suite should be run or just a single evaluation as well as arguments for the actual MPC protocol being run. 
    Also an optional argument to choose if want benchmark results to include preprocessing phase or not"""
    if False: 
        #No longer used, but gives option to run evaluation and get number of rounds in a single command.
        os.system(f"Scripts/compile-run.py {version} {nparallel} {eval_len} {order} {generator} -E {protocol} -P {prime}")
    else:
        if full_benchmark:
            nparallel_arr = [1,10]
            batch_size_arr = [50, 65, 75, 100, 150, 185, 200, 250, 300, 325, 350, 450, 600, 645, 750, 1000, 1285]
            repeat = 5
            if online_phase_benchmark or protocol == "hemi":
                # Batch size has no effect for the online phase, so there is no point in using various values for it in that case
                batch_size_arr = [1000]
        else:
            nparallel_arr = [nparallel]
            batch_size_arr = [1000]
            repeat = 1
        #Output file to log experiment runs 
        output_file = open(f"output_{version}_{bit_len}_{eval_len}_{protocol}_{order}_{online_phase_benchmark}.csv", 'w')
        output_file.write(f'Number Parallel,Batch Size,Numer Rounds,Amount of Data,Time in seconds,Version,Evaluation Length,Protocol,Online,Order,Prime Size\n')
        
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
                os.system(f"./compile.py {version} {nparallel} {eval_len} {order}  {generator} -O -D -P {prime}")

                #Make sure public-input file exists for this exact configuration.
                os.system(f'cp Programs/Public-Input/{version}-{npar}-{eval_len}-{order}-{generator} Programs/Public-Input/{version}-{nparallel}-{eval_len}-{order}-{generator}')

                #Run repeat many repetitions
                for _ in range(repeat):
                    # Run offline phase to prepare data 
                    offline_run_command = f"./{protocol}-offline.x  {version}-{nparallel}-{eval_len}-{order}-{generator} -P {prime} -S {statistical_securtiy}" 
                    os.system(f"{offline_run_command} -p 0 & {offline_run_command} -p 1")

                    # This lets us specify if we want to perform the preprocessing live or use the above generated values. -F says to use preprocessing data saved to a file, so if -F is specified we skip the offline phase.
                    additional = "" 
                    if online_phase_benchmark:
                        additional = "-F"

                    # Run the protocol and then parse the output to extract the rounds, mb sent and time required.
                    resp = os.popen(f"Scripts/{protocol}.sh {version}-{nparallel}-{eval_len}-{order}-{generator} --direct -b {batch_size} -P {prime} -S {statistical_securtiy} {additional}").read()
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
                print(all_mb_sent, all_mb_total, all_times, flush=True)
                try:
                    # Log output and write benchmark results to a file.
                    if repeat == 1:
                        print(f"Prime {prime}. Run with {nparallel} parallel evaluations, ran {len(all_mb_sent)} many repetitions. Used batch size of {batch_size}. It took {fmean(all_rounds)} many rounds, total data sent is {fmean(all_mb_total)} MB, and data sent by party one is {fmean(all_mb_sent)} MB. Execution took {fmean(all_times)} seconds ", flush = True)
                        output_file.write(f'{nparallel},{batch_size}, {fmean(all_rounds)},{fmean(all_mb_total)},{fmean(all_times)},{version},{eval_len},{protocol},{online_phase_benchmark},{order},{bit_len}\n')

                    else:
                        print(f"Prime {prime}. Run with {nparallel} parallel evaluations, ran {len(all_mb_sent)} many repetitions. Used batch size of {batch_size}. It took {fmean(all_rounds)}+-{sem(all_rounds)} many rounds, total data sent is {fmean(all_mb_total)}+-{sem(all_mb_total)} MB, and data sent by party one is {fmean(all_mb_sent)}+-{sem(all_mb_sent)} MB. Execution took {fmean(all_times)}+-{sem(all_times)} seconds ", flush = True)
                        output_file.write(f'{nparallel},{batch_size}, {fmean(all_rounds)}+-{sem(all_rounds)},{fmean(all_mb_total)}+-{sem(all_mb_total)},{fmean(all_times)}+-{sem(all_times)},{version},{eval_len},{protocol},{online_phase_benchmark},{order},{bit_len}\n')
                except:
                    print(f"Prime {prime}. Run with {nparallel} parallel evaluations, ran {len(all_mb_sent)} many repetitions. Used batch size of {batch_size}. It took {rounds} many rounds, total data sent is ?")
                    output_file.write(f'{nparallel},{batch_size},{rounds},?,?,{version},{eval_len},{protocol},{online_phase_benchmark},{order},{bit_len}\n')
        output_file.close()


def find_gen(prime):
    """Finds a generator for the group, required since we need one for computing the higher-order residues."""
    factors = primefactors(prime-1)
    gen = 1
    while pow(gen,2,prime) == 1:
        gen = random.randint(1,prime)
        for i in factors:
            if pow(gen, (prime-1)//i,prime) == 1:
                gen = 1 
                break
    return gen 

def compute_residual(element, prime, generator, order):
    """Computes the higher order residual of an element in a group."""
    for i in range(order):
        i = i + 1
        div = pow(generator,-i,prime)
        if pow(element * div, (prime-1)//order, prime) == 1:
            return i 
    return 0 


def verify_results(eval_len, nparallel, user_input, server_k, indexes, prime, order, generator):
    """Verify that the implementation computes the correct higher-power residue symbols"""
    
    results = [] 
    with open("Player-Data/Binary-Output-P0-0",'rb') as f:
        a = f.read()
        current_value = 0
        index = 1
        for offset in range(0,nparallel):
            for i in range(offset * 8,len(a),8 * nparallel):
                # This implementation, outputs power/order many values for each item and the actual symbol is the index of these that contains value 1.
                res = int.from_bytes(a[i:i+8],'little')
                if res == 1 and current_value == 0:
                    current_value = index 
                index += 1
                if index > order:
                    results.append(current_value)
                    index = 1 
                    current_value = 0
                    if debug:  
                        print(current_value)

    # Locally compute expected output 
    for i in range(eval_len):
        for j in range(nparallel):
            user_x = int(user_input[j])
            res = (user_x + server_k + indexes[i])
            output = compute_residual(res, prime, generator, order)
            if debug:
                print(i+j*eval_len, user_x, server_k, res, output, results)
            if results[i+j*eval_len] != output:
                # Compare the two output values and ensure they are equal.
                raise Exception(f"Verifying results failed! Something went wrong {results[j+i*nparallel]} {output}")
    print("Test passed")
    print(version, nparallel, len(results))

        
if __name__ == '__main__':
    try:
        "Create directories, required on first run"
        os.system(f'mkdir Programs/Public-Input && mkdir Player-Data')
    except:
        pass
    nparallel, eval_len, prime, version, improved, order = parse_args()
    user_input, server_k, indexes, generator = generate_input(prime, eval_len, nparallel, improved, order)
    run_protocol(full_benchmark, version, nparallel, protocol, prime, order, generator, online_phase_benchmark)
    verify_results(eval_len, nparallel, user_input, server_k, indexes, prime, order, generator)