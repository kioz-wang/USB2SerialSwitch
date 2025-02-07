#!/usr/bin/env python3

import argparse
import time
import serial
from datetime import datetime
import inspect


class Switch:
    def __init__(self, port: str, baudrate: int = 9600, log: bool = False):
        self.log = log
        self.ser = serial.Serial(port, baudrate)
        self._status = False
        self.port = port
        self.baudrate = baudrate
        if self.log:
            print(f"\033[90m{self} init\033[0m")

    def __del__(self):
        self.ser.close()
        if self.log:
            print(f"\033[90m{self} del\033[0m")

    def status(self):
        return self._status

    def __str__(self):
        return (
            f"Switch({self.port}, {self.baudrate}, {'On ' if self._status else 'Off'})"
        )

    def on(self):
        self.ser.write(bytes.fromhex("a00101a2"))
        if self.log:
            print(
                f"{self} \033[32m{inspect.currentframe().f_code.co_name:3s} {datetime.now().isoformat(' ', 'microseconds')}\033[0m"
            )
        self._status = True

    def off(self):
        self.ser.write(bytes.fromhex("a00100a1"))
        if self.log:
            print(
                f"{self} \033[31m{inspect.currentframe().f_code.co_name:3s} {datetime.now().isoformat(' ', 'microseconds')}\033[0m"
            )
        self._status = False

    def toggle(self):
        if self._status:
            self.off()
        else:
            self.on()

    def reset(self, delay: float = 1):
        self.off()
        time.sleep(delay)
        self.on()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p", "--port", help="Serial port, ie. /dev/ttyUSB0", required=True
    )
    parser.add_argument("-b", "--baudrate", help="Baudrate", default=9600)
    parser.add_argument("-l", "--log", help="Log", action="store_true")
    action = parser.add_subparsers(help="Action to do", required=True, dest="action")
    action.add_parser("on")
    action.add_parser("off")
    action.add_parser("toggle")
    action.add_parser("reset").add_argument(
        "-d",
        "--delay",
        help="Delay in seconds",
        type=float,
        default=1,
    )
    args = parser.parse_args()

    switch = Switch(args.port, args.baudrate, args.log)
    if args.action == "on":
        switch.on()
    elif args.action == "off":
        switch.off()
    elif args.action == "toggle":
        switch.toggle()
    elif args.action == "reset":
        switch.reset(args.delay)
