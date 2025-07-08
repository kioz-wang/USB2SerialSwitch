#!/usr/bin/env python3

import argparse
import time
from typing import Optional, Set
import serial
from datetime import datetime
from enum import Enum, auto
import sys


class Color(Enum):
    Debug = "\033[0;90m"
    Info = "\033[0;32m"
    Time = "\033[0;2;3;4m"
    Reset = "\033[0m"
    def __str__(self) -> str:
        return self.value


class OpCode(Enum):
    Off = 0x00
    On = 0x01
    OffAck = 0x02
    OnAck = 0x03
    NegateAck = 0x04
    QueryAck = 0x05
    Unknown = auto()


class Frame:
    BeginCode: int = 0xA0

    def __init__(self, opcode: OpCode = OpCode.On, addr: int = 0x01):
        assert opcode != OpCode.Unknown
        self.addr = addr
        self.opcode = opcode

    def chksum(self) -> int:
        return (self.BeginCode + self.addr + self.opcode.value) & 0xFF

    def __str__(self) -> str:
        return f"Frame {{ addr: {self.addr:02x}, op: {self.opcode.name}, chksum: {self.chksum():02x} }}"

    def toBytes(self) -> bytes:
        return bytes([self.BeginCode, self.addr, self.opcode.value, self.chksum()])

    @staticmethod
    def fromBytes(data: bytes) -> "Frame":
        self = Frame(OpCode(data[2]), data[1])
        if self.toBytes() != data:
            raise RuntimeError(f"Invalid Frame Data: {data}")
        return self

    def transfer(self, ser: serial.Serial, log: bool = False) -> Optional["Frame"]:
        ser.write(self.toBytes())
        if log:
            print(
                f"{Color.Time}{datetime.now().isoformat(' ', 'microseconds')}{Color.Info} send {self}{Color.Reset}"
            )
        match self.opcode:
            case OpCode.Off | OpCode.On:
                return None
        ack_bytes = ser.read(4)
        if not ack_bytes:
            raise RuntimeError(f"Serial not supports {self.opcode.name}")
        ack = self.fromBytes(ack_bytes)
        if log:
            print(
                f"{Color.Time}{datetime.now().isoformat(' ', 'microseconds')}{Color.Info} recv {ack}{Color.Reset}"
            )
        return ack


class Feature(Enum):
    Ack = auto()
    Dummy = auto()

    @classmethod
    def parser(cls):
        def f(s: str):
            for item in list(cls):
                if s == item.name:
                    return item
            raise RuntimeError(f"Unable to parse {s} as {cls.__name__}")

        return f


class Switch:
    def __init__(
        self,
        port: str,
        addr: int = 1,
        baudrate: int = 9600,
        log: bool = False,
        features: Set[Feature] = set(),
    ):
        self.port = port
        self.addr = addr
        self.baudrate = baudrate
        self.log = log
        self.features = features
        self.ser = serial.Serial(port, baudrate, timeout=0.5)
        self.status = OpCode.Unknown
        if Feature.Ack in self.features:
            self._transfer(OpCode.QueryAck)
        if self.log:
            print(f"{Color.Debug}{self} init{Color.Reset}")

    def __del__(self):
        if hasattr(self, "ser"):
            self.ser.close()
            if self.log:
                print(f"{Color.Debug}{self} del{Color.Reset}")

    def __str__(self):
        return f"Switch({self.port}:{self.addr}, {self.baudrate}, {self.status.name})"

    def _transfer(self, opcode: OpCode):
        ack = Frame(opcode, self.addr).transfer(self.ser, self.log)
        match opcode:
            case OpCode.Off | OpCode.OffAck:
                self.status = OpCode.Off
            case OpCode.On | OpCode.OnAck:
                self.status = OpCode.On
            case OpCode.NegateAck | OpCode.QueryAck:
                if ack:
                    self.status = ack.opcode
                else:
                    raise RuntimeError("unreacheable")

    def _require(self, feature: Feature):
        if feature not in self.features:
            raise RuntimeError(f"Require feature {feature.name}")

    def get_status(self):
        return self.status.name

    def on(self):
        if self.status != OpCode.On:
            self._transfer(OpCode.On)

    def off(self):
        if self.status != OpCode.Off:
            self._transfer(OpCode.Off)

    def toggle(self):
        self._require(Feature.Ack)
        self._transfer(OpCode.NegateAck)

    def reset(self, delay: float = 1, reverse: bool = False):
        self.on() if reverse else self.off()
        time.sleep(delay)
        self.off() if reverse else self.on()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="USB2Serial Switch")
    parser.add_argument(
        "-p", "--port", help="Serial port, ie. /dev/ttyUSB0", required=True
    )
    parser.add_argument("-b", "--baudrate", help="Baudrate", default=9600)
    parser.add_argument("-a", "--addr", type=int, help="Address [1, 0xFF)", default=1)
    parser.add_argument("-l", "--log", help="Log", action="store_true")
    parser.add_argument(
        "--traceback", help="Enable Python traceback", action="store_true"
    )
    parser.register("type", "Feature", Feature.parser())
    parser.add_argument(
        "--feature",
        help=f"Support features {set(Feature.__members__.keys())}",
        action="append",
        type="Feature",
        default=[],
    )
    action = parser.add_subparsers(help="Action to do", required=True, dest="action")
    action.add_parser("on")
    action.add_parser("off")
    action.add_parser("toggle")
    action_reset = action.add_parser("reset")
    action_reset.add_argument(
        "-d",
        "--delay",
        help="Delay in seconds",
        type=float,
        default=1,
    )
    action_reset.add_argument(
        "-r", "--reverse", help="Reverse reset", action="store_true"
    )
    action.add_parser("status")
    args = parser.parse_args()

    if not args.traceback:
        sys.tracebacklimit = 0

    if args.addr not in range(1, 0xFE):
        raise RuntimeError(f"Invalid Address {args.addr} at {args.port}")

    switch = Switch(args.port, args.addr, args.baudrate, args.log, set(args.feature))
    if args.action == "on":
        switch.on()
    elif args.action == "off":
        switch.off()
    elif args.action == "toggle":
        switch.toggle()
    elif args.action == "reset":
        switch.reset(args.delay, args.reverse)
    elif args.action == "status":
        print(switch.get_status())
