"""Plot cwnd(t) for E1, averaged over trials.

Usage:
    python analyze_e1.py data/e1                 # every config found in the dir
    python analyze_e1.py data/e1 --out e1.png    # save instead of show

Files are expected to be named <experiment>_<setting>_<algorithm>_t<trial>_ss.txt
(e.g. e1_b1_reno_t3_ss.txt). Trials of the same config are grouped together.
"""

import re
from argparse import ArgumentParser
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

SS_NAME = re.compile(r"^(?P<config>.+)_t(?P<trial>\d+)_ss\.txt$")


def is_float(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def parse_socket_info(info_line: str) -> dict:
    parts = info_line.strip().split()
    out = {"type": parts[0]}
    for token in parts[1:]:
        kv = token.split(":")
        if len(kv) == 2:
            out[kv[0]] = kv[1]
    return out


def extract_info(filename: Path) -> list[dict]:
    # returns one dict per sample that has the iperf3 data connection open.
    with open(filename, "r") as f:
        lines = f.readlines()
    print("reading", filename)

    samples = []
    i = 0
    while i < len(lines):
        # each sample is a timestamp line, the ss header, then an
        # (state line, detail line) pair per socket.
        timestamp = float(lines[i])
        i += 1
        assert lines[i].startswith("State"), f"{filename}:{i + 1}: expected ss header"
        i += 1
        body = []
        while i < len(lines) and not is_float(lines[i]):
            body.append(lines[i])
            i += 1
        # take all details
        sockets = [parse_socket_info(body[j]) for j in range(1, len(body), 2)]
        if len(sockets) < 2:
            continue
        # then take just the data connection
        data_sock = max(sockets, key=lambda s: int(s.get("bytes_acked", 0)))
        data_sock["timestamp"] = timestamp
        samples.append(data_sock)
    return samples


def load_trial(filename: Path) -> tuple[np.ndarray, np.ndarray]:
    samples = extract_info(filename)
    if not samples:
        raise ValueError(f"{filename}: no samples with a data connection")
    times = np.array([s["timestamp"] for s in samples])
    cwnd = np.array([int(s["cwnd"]) for s in samples])
    return times - times[0], cwnd


def closest_point(t: np.ndarray, y: np.ndarray, grid: np.ndarray) -> np.ndarray:
    idx = np.searchsorted(t, grid, side="right") - 1
    return y[np.clip(idx, 0, len(y) - 1)]


def find_trials(dir: Path) -> dict[str, list[Path]]:
    assert dir.is_dir(), f"{dir} is not a directory"
    files = sorted(dir.glob("*_ss.txt"))
    groups = defaultdict(list)
    for f in files:
        m = SS_NAME.match(f.name)
        if m is None:
            print(f"skipping {f} (name doesn't match <config>_t<N>_ss.txt)")
            continue
        groups[m["config"]].append(f)
    return dict(sorted(groups.items()))


def plot_config(ax, config: str, files: list[Path], dt: float, steady_start: float):
    trials = [load_trial(f) for f in files]
    # to allow us to report means/stds, we trim trials to min length and then
    # sample at discrete time points (since not all trials are sampled at the same by ss)
    t_end = min(t[-1] for t, _ in trials)
    grid = np.arange(0, t_end, dt)
    stacked = np.stack([closest_point(t, c, grid) for t, c in trials])
    mean = stacked.mean(axis=0)
    std = stacked.std(axis=0, ddof=1) if len(trials) > 1 else np.zeros_like(mean)

    for t, c in trials:
        ax.plot(t, c, lw=0.6, alpha=0.3, color="gray")
    ax.plot(grid, mean, lw=1.5, color="C0", label=f"mean of {len(trials)} trials")
    ax.fill_between(
        grid, mean - std, mean + std, color="C0", alpha=0.25, label="±1 std"
    )
    ax.set_title(config)
    ax.set_xlabel("Time since data connection opened (s)")
    ax.set_ylabel("cwnd (packets)")
    ax.legend(loc="upper right")

    # Per-trial scalar summary, reported as mean ± std over trials
    per_trial_mean = [c[t >= steady_start].mean() for t, c in trials]
    per_trial_max = [c.max() for _, c in trials]
    sd = lambda xs: np.std(xs, ddof=1) if len(xs) > 1 else 0.0
    print(f"{config}: {len(trials)} trials ({', '.join(f.name for f in files)})")
    print(
        f"  steady-state cwnd (t >= {steady_start:g}s): "
        f"{np.mean(per_trial_mean):.1f} ± {sd(per_trial_mean):.1f} packets"
    )
    print(
        f"  peak cwnd: {np.mean(per_trial_max):.1f} ± {sd(per_trial_max):.1f} packets"
    )


def main(dir: Path, out: Path | None, dt: float, steady_start: float):
    groups = find_trials(dir)
    if not groups:
        raise SystemExit("no *_ss.txt files found")
    fig, axes = plt.subplots(
        len(groups), 1, figsize=(10, 4 * len(groups)), squeeze=False
    )
    for ax, (config, files) in zip(axes[:, 0], groups.items()):
        plot_config(ax, config, files, dt, steady_start)
    fig.tight_layout()
    if out:
        fig.savefig(out, dpi=150)
        print(f"saved {out}")
    else:
        plt.show()


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "dir",
        type=Path,
        help="directories containing *_ss.txt files",
    )
    parser.add_argument(
        "--out", type=Path, help="save the figure here instead of showing it"
    )
    parser.add_argument(
        "--dt",
        type=float,
        default=0.01,
        help="timedelta to use when gridding data to line up samples, in seconds",
    )
    parser.add_argument(
        "--steady-start",
        type=float,
        default=5.0,
        help="ignore samples before this time (s) for the steady-state summary",
    )
    args = parser.parse_args()
    main(args.dir, args.out, args.dt, args.steady_start)
