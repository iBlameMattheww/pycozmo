#!/usr/bin/env python

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pycozmo


ROBOT_EVENTS = [
    pycozmo.event.EvtRobotFound,
    pycozmo.event.EvtRobotReady,
    pycozmo.event.EvtRobotStateUpdated,
    pycozmo.event.EvtRobotOrientationChange,
    pycozmo.event.EvtRobotPickedUpChange,
    pycozmo.event.EvtRobotWheelsMovingChange,
]

class DecodeFailureLogHandler(logging.Handler):

    def __inti__(self):
        super().__init__(level=logging.DEBUG)
        self.failures = []

    def emit(self, record):
        msg = record.getMessage()
        if "Failed to decode packet" in msg or "[2313-debug] Failed to decode packet" in msg:
            self.failures.append(msg)
            print("[decode failure] {}".format(msg))

def main():
    parser = argparse.ArgumentParser(description="Probe robot discovery behavior for firmware 2313.")
    parser.add_argument("--timeout", type=float, default=10.0, help="wait_for_robot timeout in seconds")
    parser.add_argument("--verbose", action="store_true", help="enable verbose PyCozmo logging")
    parser.add_argument("--raw-log", action="store_true", help="enable protocol-level raw/decode logging")
    parser.add_argument("--try-display", action="store_true", help="send one safe display test pattern")
    parser.add_argument("--try-motors", action="store_true", help="send small head/lift/wheel commands")
    args = parser.parse_args()

    os.environ.setdefault("PYCOZMO_DEBUG_2313", "1")
    os.environ.setdefault("PYCOZMO_2313_IGNORE_WIFI_UPDATE_MISMATCH", "1")

    log_level = "DEBUG" if args.verbose else "INFO"
    protocol_level = "DEBUG" if (args.verbose or args.raw_log) else "INFO"
    robot_level = "DEBUG" if args.verbose else "INFO"
    pycozmo.setup_basic_logging(log_level=log_level, protocol_log_level=protocol_level, robot_log_level=robot_level)

    decode_handler = DecodeFailureLogHandler()
    pycozmo.logger_protocol.addHandler(decode_handler)

    cli = pycozmo.Client(debug_2313=True, compatibility_2313_ignore_wifi_update_mismatch=True)

    def on_robot_event(evt_name):
        def _h(*_args):
            print("[event] {}".format(evt_name))
        return _h

    for evt in ROBOT_EVENTS:
        cli.add_handler(evt, on_robot_event(evt.__name__))

    try:
        print("Starting client")
        cli.start()
        cli.connect()

        robot_obj = cli.wait_for_robot(timeout=args.timeout)
        print("wait_for_robot(timeout={}) -> {}".format(args.timeout, robot_obj))
        print("cli.robot -> {}".format(cli.robot))
        print("firmware -> {}".format(None if cli.robot_fw_sig is None else cli.robot_fw_sig.get("version")))
        print("body serial -> {}".format(None if cli.serial_number is None else hex(cli.serial_number)))
        print("body hw version -> {}".format(cli.body_hw_version))

        if args.try_display:
            print("Sending display test image")
            cli.display_image(Image.new("1", (128, 32), color=1), duration=0.5)

        if args.try_motors:
            print("Sending minimal motor commands")
            cli.move_head(0.05)
            time.sleep(0.2)
            cli.move_head(0.0)
            cli.move_lift(0.05)
            time.sleep(0.2)
            cli.move_lift(0.0)
            cli.drive_wheels(10.0, 10.0, duration=0.2)

        print("Listening for 30 seconds...")
        end = time.time() + 30.0
        while time.time() < end:
            time.sleep(0.1)

        print("Decode failures observed: {}".format(len(decode_handler.failures)))
    except Exception as e:
        print("Probe failed: {}".format(e), file=sys.stderr)
        raise
    finally:
        try:
            cli.disconnect()
        finally:
            cli.stop()


if __name__ == "__main__":
    main()