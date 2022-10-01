#!/usr/bin/env python3

# Simple Script to replace cron for Docker

import argparse
import re
import sys
from datetime import datetime
from subprocess import CalledProcessError, run
from time import sleep, time


def parseNumList(string):
    m = re.match(r"(\d+)(?:-(\d+))?$", string)
    if not m:
        raise argparse.ArgumentTypeError(
            f"'{string}' is not a range. Expected '0-5', '20-6' or '1'."
        )
    start = int(m.group(1))
    end = int(m.group(2) or start)
    if start <= end:
        return list(range(start, end + 1))
    return list(range(start, 23 + 1)) + list(range(0, end + 1))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        default="/conf/bandersnatch.conf",
        help="Configuration location",
    )
    parser.add_argument("interval", help="Time in seconds between runs", type=int)
    parser.add_argument(
        "--hours-range",
        default="0-23",
        help="Hours of day interval expresses as 0-23 or 2",
        type=parseNumList,
    )
    args = parser.parse_args()

    print(f"Running bandersnatch every {args.interval}s", file=sys.stderr)
    try:
        while True:
            if datetime.now().hour in args.hours_range:
                start_time = time()

                try:
                    cmd = [
                        sys.executable,
                        "-m",
                        "bandersnatch.main",
                        "--config",
                        args.config,
                        "mirror",
                    ]
                    run(cmd, check=True)
                except CalledProcessError as cpe:
                    return cpe.returncode

                run_time = time() - start_time
                if run_time < args.interval:
                    sleep_time = args.interval - run_time
                    print(f"Sleeping for {sleep_time}s", file=sys.stderr)
                    sleep(sleep_time)
            else:
                sleep(60)
    except KeyboardInterrupt:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
