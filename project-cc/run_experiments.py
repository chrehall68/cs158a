from argparse import ArgumentParser
from typing import Literal
import subprocess


def main(
    experiment_name: str,  # ie e1, e2, etc
    n: int,  # number of trials to take
    congestion_control_types: list[Literal["reno"] | Literal["cubic"] | Literal["bbr"]],
):
    desired_stdin = []
    data_dir = f"./data/{experiment_name}"
    subprocess.call(["mkdir", "-p", data_dir])
    for cc in congestion_control_types:
        for i in range(1, n + 1):
            desired_stdin.append(
                f"snd0 timeout 65 sh -c 'while :; do date +%s.%N; ss -tin dst 10.0.0.101:5201; sleep 0.01; done' > {data_dir}/{experiment_name}_b1_{cc}_t{i}_ss.txt &"
            )
            desired_stdin.append(
                f"snd0 iperf3 -c 10.0.0.101 -C {cc} -t 60 -i 0.5 -J --logfile {data_dir}/{experiment_name}_b1_{cc}_t{i}.json"
            )
            # wait for logging script to stop
            desired_stdin.append("sh sleep 10")
    desired_stdin.append("exit")
    input = "\n".join(desired_stdin).encode()

    subprocess.run(["sudo", "python3", "dumbbell.py"], input=input)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("n", type=int)
    parser.add_argument("--experiment-name", type=str, default="e1")
    parser.add_argument("--cc", type=str, nargs="+", default=["reno", "cubic", "bbr"])
    args = parser.parse_args()
    main(args.experiment_name, int(args.n), args.cc)
