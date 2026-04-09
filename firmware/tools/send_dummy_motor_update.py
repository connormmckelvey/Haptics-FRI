#!/usr/bin/env python3
"""Send dummy `motor_update_t` packets over a serial port.

Packet format (matches `include/packet_types.h`):
- motor_states[4] : uint8_t (0 or 1)

Total: 4 bytes per packet.
"""

from __future__ import annotations

import argparse
import sys
import time


MOTOR_COUNT = 4


def build_packet(on_index: int | None) -> bytes:
    motor_states = [0] * MOTOR_COUNT
    if on_index is not None:
        motor_states[on_index % MOTOR_COUNT] = 1

    return bytes(motor_states)


def main() -> int:
    parser = argparse.ArgumentParser(description="Send dummy motor_update_t packets over serial")
    parser.add_argument("--port", default="COM6", help="Serial port (e.g. COM6)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--period", type=float, default=0.2, help="Seconds between packets")
    parser.add_argument(
        "--mode",
        choices=["chase", "all_off", "all_on"],
        default="chase",
        help="Pattern to send",
    )
    args = parser.parse_args()

    try:
        import serial  # type: ignore
    except Exception:
        print("Missing dependency: pyserial. Install with: pip install pyserial", file=sys.stderr)
        return 2

    print(f"Opening {args.port} @ {args.baud}...")
    try:
        ser = serial.Serial(
            port=args.port,
            baudrate=args.baud,
            timeout=0,
            write_timeout=1,
        )
    except Exception as exc:
        print(f"Failed to open {args.port}: {exc}", file=sys.stderr)
        return 1

    with ser:
        i = 0
        print("Sending packets. Ctrl+C to stop.")
        try:
            while True:
                if args.mode == "all_off":
                    packet = build_packet(on_index=None)
                elif args.mode == "all_on":
                    packet = bytes([1] * MOTOR_COUNT)
                else:  # chase
                    packet = build_packet(on_index=i)

                ser.write(packet)
                ser.flush()

                i += 1
                time.sleep(args.period)
        except KeyboardInterrupt:
            print("\nStopped.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
