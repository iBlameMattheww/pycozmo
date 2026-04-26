#!/usr/bin/env python

import argparse
import collections
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pycozmo


def main():
    parser = argparse.ArgumentParser(description="Trace incoming packet/events and summarize discovery state.")
    parser.add_argument("--seconds", type=float, default=30.0, help="duration to trace")
    parser.add_argument("--verbose", action="store_true", help="enable debug logs")
    args = parser.parse_args()

    os.environ.setdefault("PYCOZMO_2313_DEBUG", "1")

    log_level = "DEBUG" if args.verbose else "INFO"
    pycozmo.setup_basic_logging(log_level=log_level, protocol_log_level=log_level, robot_log_level=log_level)

    counts = collections.Counter()
    ordered = []
    decode_failures = []

    class DecodeFailureLogHandler(logging.Handler):
        def emit(self, record):
            msg = record.getMessage()
            if "Failed to decode packet" in msg or "[2313-debug] Failed to decode packet" in msg:
                decode_failures.append(msg)

    pycozmo.logger_protocol.addHandler(DecodeFailureLogHandler())

    cli = pycozmo.Client(debug_2313=True)

    def on_packet(pkt):
        name = pkt.__class__.__name__
        counts[name] += 1
        ordered.append(name)
        print("{}: {}".format(len(ordered), name))

    cli.add_handler(pycozmo.event.EvtRobotFound, lambda _cli: print("[event] EvtRobotFound"))
    cli.add_handler(pycozmo.event.EvtRobotReady, lambda _cli: print("[event] EvtRobotReady"))
    cli.add_handler(pycozmo.event.EvtPacketReceived, on_packet)

    cli.start()
    cli.connect()
    end = time.time() + args.seconds
    while time.time() < end:
        time.sleep(0.1)

    print("\nSummary")
    for name, count in counts.most_common():
        print("  {}: {}".format(name, count))

    if cli._robot_found:
        print("Robot discovery: EvtRobotFound observed")
    else:
        print("Robot discovery: missing EvtRobotFound")

    if cli._robot_ready:
        print("Robot ready: EvtRobotReady observed")
    else:
        print("Robot ready: missing EvtRobotReady")

    if decode_failures:
        print("Decode failures: {}".format(len(decode_failures)))
    else:
        print("Decode failures: none observed")

    cli.disconnect()
    cli.stop()


if __name__ == "__main__":
    main()