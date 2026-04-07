#!/usr/bin/env python3
"""Send dummy `motor_update_t` packets over a serial port.

Firmware expects the raw bytes of:
- motor_states[12] : uint8_t (0 or 1)
- amount_of_motors : uint8_t

Total: 13 bytes per packet.
"""

from __future__ import annotations

import argparse
import sys
import time


def build_packet(amount_of_motors: int, on_index: int | None) -> bytes:
    if not (1 <= amount_of_motors <= 12):
        raise ValueError("amount_of_motors must be in [1, 12]")

    motor_states = [0] * 12
    if on_index is not None:
        motor_states[on_index % amount_of_motors] = 1

    return bytes(motor_states) + bytes([amount_of_motors])


def main() -> int:
    parser = argparse.ArgumentParser(description="Send dummy motor_update_t packets over serial")
    parser.add_argument("--port", default="COM6", help="Serial port (e.g. COM6)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--motors", type=int, default=4, help="amount_of_motors field (1-12)")
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
                    packet = build_packet(args.motors, on_index=None)
                elif args.mode == "all_on":
                    # Set first N motors on, remaining off.
                    motor_states = [1] * min(args.motors, 12) + [0] * (12 - min(args.motors, 12))
                    packet = bytes(motor_states) + bytes([args.motors])
                else:  # chase
                    packet = build_packet(args.motors, on_index=i)

                ser.write(packet)
                ser.flush()

                i += 1
                time.sleep(args.period)
        except KeyboardInterrupt:
            print("\nStopped.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
