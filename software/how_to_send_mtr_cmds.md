# Dongle Serial Protocol

## Overview

The dongle accepts raw bytes over USB serial and relays them to the wearable band via ESP-NOW. There is no framing, no handshake, and no acknowledgement.

## Connection Settings

| Parameter | Value |
|-----------|-------|
| Baud rate | 115200 |

## Packet Format

Every motor command is exactly **4 bytes**, one byte per motor:

| Byte | Motor | Position |
|------|-------|----------|
| 0 | Motor 0 | Top |
| 1 | Motor 1 | Right |
| 2 | Motor 2 | Bottom |
| 3 | Motor 3 | Left |

Each byte is either `0x00` (off) or `0x01` (on).

## Rules

- Send all 4 bytes together — do not insert delays between bytes. The dongle will reset its buffer if a partial packet stalls for more than 10ms.
- There is no acknowledgement back from the dongle.
- There is no start byte or header — do not send anything before the 4 motor bytes.
- Do not send newline characters or any other framing.

## Examples

Vibrate top motor only:
```
0x01 0x00 0x00 0x00
```

Vibrate right motor only:
```
0x00 0x01 0x00 0x00
```

Vibrate all motors:
```
0x01 0x01 0x01 0x01
```

All motors off:
```
0x00 0x00 0x00 0x00
```

## Python Example

```python
import serial

ser = serial.Serial('COM3', 115200)  # replace COM3 with your port

# Vibrate top motor only
ser.write(bytes([1, 0, 0, 0]))

# Vibrate right motor only
ser.write(bytes([0, 1, 0, 0]))

# All motors off
ser.write(bytes([0, 0, 0, 0]))
```

## Notes

- The band automatically remaps motor commands based on wrist orientation using the onboard IMU. A command for the "top" motor will always vibrate whichever motor is physically on top of the wrist at that moment.
- If the band is out of range or powered off, the dongle will silently drop the packet.