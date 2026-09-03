import argparse
import subprocess

def setup_and_run(n: int, base_port: int):
    procs = []
    for i in range(n):
        config_file = f"config{i + 1}.txt"
        log_file = f"log{i + 1}.txt"
        with open(config_file, "w") as f:
            f.write(f"0.0.0.0, {base_port + i}\n")
            f.write(f"0.0.0.0, {base_port + (i + 1) % n}")
        procs.append(subprocess.Popen(["python3", "myleprocess.py", config_file, log_file]))

    for proc in procs:
        proc.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("n", type=int)
    parser.add_argument("--base-port", type=int, default=8900)
    args = parser.parse_args()

    setup_and_run(args.n, args.base_port)

