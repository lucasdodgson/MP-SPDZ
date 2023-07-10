import os 

#Helper script that runs all the evaluated benchmarks. 
#Output logs are written to the output directory and the csv files with the performance results will be written to the current direcotry.

protocols = ["mascot","semi","hemi"]

prime_sizes = [128, 256]

improved = [True, False]

online = [True, False]

os.system("mkdir output")

#Legendre OPRF:
for prime in prime_sizes:
    for protocol in protocols:
        for onl in online:
            for imp in improved if onl == True else [False]:
                #Make sure running the desired configuration:
                os.system(f"sed -i '10s/.*/full_benchmark = True/' legendre_oprf_benchmark.py")
                os.system(f"sed -i '13s/.*/online_phase_benchmark = {onl}/' legendre_oprf_benchmark.py")
                os.system(f"sed -i '16s/.*/protocol = \"{protocol}\" /' legendre_oprf_benchmark.py")
                #Run the file:
                if imp:
                    os.system(f"python3 legendre_oprf_benchmark.py 10 {prime} improved > output/legendre_oprf_{protocol}_{prime}_{onl}_{imp}_out.txt")
                else:
                    os.system(f"python3 legendre_oprf_benchmark.py 10 {prime} > output/legendre_oprf_{protocol}_{prime}_{onl}_{imp}_out.txt")


for prime in prime_sizes:
    for protocol in protocols:
        for onl in online:
            for imp in improved if onl == True else [False]:
                for order in [2,4,8,16,32,64,128,256]:
                    os.system(f"sed -i '10s/.*/full_benchmark = True/' higher_order_oprf_benchmark.py")
                    os.system(f"sed -i '13s/.*/online_phase_benchmark = {onl}/' higher_order_oprf_benchmark.py")
                    os.system(f"sed -i '16s/.*/protocol = \"{protocol}\" /' higher_order_oprf_benchmark.py")
                    if imp:
                        os.system(f"python3 higher_order_oprf_benchmark.py 10 {prime} {order} improved > output/higher_order_oprf_{protocol}_{prime}_{order}_{onl}_{imp}_out.txt")
                    else:
                        os.system(f"python3 higher_order_oprf_benchmark.py 10 {prime} {order} > output/higher_order_oprf_{protocol}_{prime}_{order}_{onl}_{imp}_out.txt")