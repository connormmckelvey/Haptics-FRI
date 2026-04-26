"""
Motor command test script
Sends random motor commands to the dongle over USB serial.

Install dependencies:
    pip install pyserial

Usage:
    python test_motors.py
"""

import serial
import serial.tools.list_ports
import time
import random

BAUD_RATE = 115200
SEND_INTERVAL = 0.5  # seconds between commands


def find_dongle_port():
    """Auto-detect the dongle's COM port by looking for a USB serial device."""
    ports = list(serial.tools.list_ports.comports())

    if not ports:
        print("No serial ports found.")
        return None

    # If there's only one port, use it
    if len(ports) == 1:
        print(f"Found port: {ports[0].device} ({ports[0].description})")
        return ports[0].device

    # If there are multiple, prefer one with ESP32 in the description
    for port in ports:
        if any(keyword in port.description for keyword in ["CP210", "CH340", "UART", "ESP"]):
            print(f"Found likely dongle port: {port.device} ({port.description})")
            return port.device

    # Otherwise list them and ask the user to pick
    print("Multiple serial ports found:")
    for i, port in enumerate(ports):
        print(f"  [{i}] {port.device} - {port.description}")
    choice = int(input("Select port number: "))
    return ports[choice].device


def send_motor_command(ser, motor_states):
    """Send a 4-byte motor command over serial."""
    data = bytes(motor_states)
    ser.write(data)


def random_motor_command():
    """Generate a random motor command with at least one motor on."""
    while True:
        states = [random.randint(0, 1) for _ in range(4)]
        if any(states):  # ensure at least one motor is on
            return states


def motor_label(index):
    return ["top", "right", "bottom", "left"][index]


def main():
    port = find_dongle_port()
    if port is None:
        print("Could not find a serial port. Is the dongle plugged in?")
        return

    print(f"\nConnecting to {port} at {BAUD_RATE} baud...")
    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=1)
    except serial.SerialException as e:
        print(f"Failed to open port: {e}")
        return

    time.sleep(1)  # wait for device to be ready
    print("Connected. Sending random motor commands. Press Ctrl+C to stop.\n")

    try:
        while True:
            states = random_motor_command()
            active = [motor_label(i) for i, s in enumerate(states) if s]
            print(f"Sending: {states}  ->  motors on: {', '.join(active)}")
            send_motor_command(ser, states)
            time.sleep(SEND_INTERVAL)

    except KeyboardInterrupt:
        print("\nStopped.")
        # Turn all motors off on exit
        send_motor_command(ser, [0, 0, 0, 0])
        print("All motors off.")
        ser.close()


if __name__ == "__main__":
    main()