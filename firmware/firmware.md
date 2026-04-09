# Firmware Documentation

## Overview

The system consists of two firmware targets — the **dongle** and the **band**. The dongle plugs into a PC via USB and relays motor commands to the band over ESP-NOW. The band receives motor commands, remaps them based on wrist orientation using an IMU, and drives the haptic motors.

```
PC  --[USB Serial]-->  Dongle  --[ESP-NOW]-->  Band  --> Motors
```

---

## Hardware

Both devices are **Seeed XIAO ESP32-C3** boards. The band additionally uses:
- **MPU6050** IMU for wrist orientation (I2C on SDA=D4, SCL=D5)
- **ULN2003A** motor driver for 4 haptic motors

### Antenna
The XIAO ESP32-C3 has a u.FL connector for an external antenna. The external antenna must be connected for reliable range. Without it the board relies on the weak onboard PCB trace antenna.

---

## Dongle Firmware

### Responsibilities
- Receives 4-byte motor commands from the PC over USB serial
- Relays them to the band via ESP-NOW

### Configuration

| Macro | Default | Description |
|-------|---------|-------------|
| `DONGLE_DUMMY_MODE` | `1` | When set to `1`, ignores serial and sends cycling dummy motor updates. Set to `0` for production. |
| `DONGLE_DUMMY_PERIOD_MS` | `2000` | Interval between dummy sends in milliseconds |

To build for production, set `DONGLE_DUMMY_MODE` to `0` in the source or via a PlatformIO build flag:
```ini
build_flags = -DDONGLE_DUMMY_MODE=0
```

### Band MAC Address
The band's MAC address is hardcoded in the dongle firmware:
```cpp
uint8_t bandAddress[] = {0xE8, 0xF6, 0x0A, 0x17, 0x00, 0xC0};
```
If the band is replaced, update this to match the new board's MAC address. The band prints its MAC address over serial on boot.

### ESP-NOW Channel
Both devices must be on the same channel. Default is channel `6`. To change it, update the `initESPNOW()` call in `setup()` on both devices.

### Serial Output
On boot the dongle prints:
```
MAC Address: XX:XX:XX:XX:XX:XX
ESP-NOW init result: 1
```
An init result of `1` means success, `0` means ESP-NOW failed to initialize, `-1` means the band peer failed to register.

During operation it prints either `Successfully sent motor update` or `Failed to send motor update` after each ESP-NOW transmission.

---

## Band Firmware

### Responsibilities
- Receives motor commands from the dongle via ESP-NOW
- Reads wrist orientation from the MPU6050 IMU
- Remaps motor commands based on wrist orientation
- Drives 4 haptic motors via the ULN2003A

### Motor Layout
Motors are indexed clockwise starting from the top:

```
      0 (top)
3 (left)  1 (right)
      2 (bottom)
```

Motor GPIO pin assignments:
```cpp
uint8_t mtrPins[] = {2, 3, 4, 5}; // top, right, bottom, left
```

### Wrist Orientation Remapping
The IMU measures roll angle and quantizes it into 4 quadrants (0°, 90°, 180°, 270°). Incoming motor commands are offset by the current quadrant so that a command for the "top" motor always vibrates whichever motor is physically on top of the wrist at that moment.

### IMU Calibration
The IMU calibrates on every boot. The user should hold their wrist still for a few seconds after powering on until calibration completes. The band will print `Calibration complete` over serial when ready.

IMU I2C pins:
```cpp
#define SDA_PIN 4
#define SCL_PIN 5
```

### ESP-NOW Channel
Default is channel `6`. Must match the dongle. Update the `initESPNOW()` call in `setup()` to change it.

### Serial Output
On boot the band prints:
```
MAC Address: XX:XX:XX:XX:XX:XX
ESP-NOW init result: 1
MPU6050 connection successful
Calibrating IMU, hold still...
Calibration complete
```

During operation it prints the received motor states each time a packet arrives.

---

## Flashing

Both targets are built and flashed using PlatformIO. Open the correct project, select the appropriate environment, connect the device via USB, and run upload.

If the device does not appear on a COM port after reset, hold the **B** (boot) button, tap **R** (reset), then release **B** to enter bootloader mode before flashing.

---

## Troubleshooting

| Symptom | Likely Cause |
|---------|--------------|
| Dongle prints `Failed to send motor update` | Band is powered off, out of range, or on a different channel |
| Band not receiving anything | Channel mismatch, or `esp_wifi_set_promiscuous` left enabled |
| Poor range | External antenna not connected to band or dongle |
| IMU not found | Wiring issue on SDA/SCL, or I2C address conflict |
| Motors not responding | GPIO pin assignments don't match physical wiring |