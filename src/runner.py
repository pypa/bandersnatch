#!/usr/bin/env python3

# Simple Script to replace cron for Docker

import argparse
import sys
from subprocess import run
from time import sleep, time


def main() -> None:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-c",
        "--config",
        default="/conf/bandersnatch.conf",
        help="Configuration location",
    )
    parser.add_argument("interval", help="Time in seconds between runs")
    args = parser.parse_args()

    print(f"Running bandersnatch every {args.interval}s", file=sys.stderr)
    while True:
        start_time = time()
        run(["/usr/bin/bandersnatch", "--config", args.conf, "mirror"])
        run_time = time() - start_time
        if run_time < args.interval:
            sleep_time = args.interval - run_time
            print(f"Sleeping for {sleep_time}s", file=sys.stderr)
            sleep(sleep_time)


if __name__ == "__main__":
    main()
