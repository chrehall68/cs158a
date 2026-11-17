from argparse import ArgumentParser
from typing import Literal
import subprocess
import dumbbell
from pathlib import Path


def main(
    experiment_name: str,  # ie e1, e2, etc
    n: int,  # number of trials to take
    congestion_control_types: list[Literal["reno"] | Literal["cubic"] | Literal["bbr"]],
):
    print("running experiments for", congestion_control_types)
    net = dumbbell.start_net(
        dumbbell.DEFAULT_BW,
        dumbbell.DEFAULT_DELAY,
        dumbbell.DEFAULT_DELAY1,
        dumbbell.DEFAULT_BUF,
        dumbbell.DEFAULT_LOSS,
    )
    data_dir = Path("data") / experiment_name
    subprocess.call(["mkdir", "-p", str(data_dir)])
    for cc in congestion_control_types:
        for i in range(1, n + 1):
            output_txt = data_dir / f"{experiment_name}_b1_{cc}_t{i}_ss.txt"
            output_json = data_dir / f"{experiment_name}_b1_{cc}_t{i}.json"
            if output_txt.exists():
                # erase
                subprocess.call(["rm", str(output_txt)])
            if output_json.exists():
                subprocess.call(["rm", str(output_json)])

            net.get("snd0").cmd(
                f"timeout 65 sh -c 'while :; do date +%s.%N; ss -tin dst 10.0.0.101:5201; sleep 0.01; done' > {str(output_txt)} &"
            )
            # wait a little to make sure the logging script starts
            net.get("snd0").cmd("sleep 1")
            net.get("snd0").cmd(
                f"iperf3 -c 10.0.0.101 -C {cc} -t 60 -i 0.5 -J --logfile {str(output_json)}"
            )
            # wait for logging script to stop
            net.get("snd0").cmd("sleep 5")

    dumbbell.stop_net(net)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("n", type=int)
    parser.add_argument("--experiment-name", type=str, default="e1")
    parser.add_argument("--cc", type=str, nargs="+", default=["reno", "cubic", "bbr"])
    args = parser.parse_args()
    main(args.experiment_name, int(args.n), args.cc)
