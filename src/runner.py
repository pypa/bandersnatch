#!/usr/bin/env python3

# Simple Script to replace cron for Docker

import argparse
import sys
import time
from subprocess import run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("interval", help="Time in seconds between jobs")
    parser.parse_args()

    print(f"Running bandersnatch every {args.interval}s", file=sys.stderr)
    while True:
        start_time = time.time()
        run(["/usr/bin/bandersnatch", "mirror"])
        run_time = time.time() - start_time
        if run_time < args.interval:
            sleep_time = args.interval - run_time
            print(f"Sleeping for {sleep_time}s", file=sys.stderr)
            time.sleep(sleep_time)


if __name__ == "__main__":
    main()
