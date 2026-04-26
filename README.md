# Haptics-FRI

Haptics-FRI is a wearable vibrotactile feedback system developed in the UT Austin Human Enabled Robotics Lab (HERL) for the Freshman Research Initiative (FRI) stream. The project explores how lightweight haptic cues can support motor learning and robotic teleoperation.

At a system level, a host computer sends motor activation commands to a USB dongle, the dongle relays those commands over ESP-NOW to a wearable band, and the band drives four vibration motors after remapping commands based on wrist orientation from an IMU.

## Project Goals

- Build a low-latency, wireless haptic communication loop
- Provide intuitive directional feedback using a 4-motor wearable band
- Keep feedback aligned to the user's physical orientation using IMU-based remapping
- Support rapid prototyping from both embedded firmware and host-side Python tools

## System Architecture

PC -> USB Serial -> Dongle (ESP32-C3) -> ESP-NOW -> Band (ESP32-C3 + MPU6050 + motor driver) -> 4 haptic motors

## Repository Structure

- firmware/: PlatformIO project for embedded firmware, protocol types, and test tooling
- firmware/src/dongle.cpp: Active dongle firmware (serial-to-ESP-NOW bridge)
- firmware/excluded_src/band.cpp: Band firmware (IMU-aware motor remapping and motor control)
- firmware/include/packet_types.h: Shared packet and IMU data structures
- firmware/tools/test_send_mtr_cmd.py: Python utility that sends random 4-byte motor packets
- masterpod_pcb_kicad/: KiCad design files and Gerber outputs for the wearable board
- software/Pose.py: MoveNet-based wrist tracking prototype for vision-driven haptic logic
- software/how_to_send_mtr_cmds.md: Serial packet protocol reference for host applications

## Hardware and Firmware

### Hardware

- 2x Seeed XIAO ESP32-C3 (dongle and band)
- MPU6050 IMU on band
- ULN2003A motor driver
- 4 haptic motors arranged as top/right/bottom/left
- External antenna recommended for reliable ESP-NOW range

### Firmware Responsibilities

- Dongle firmware:
	- Reads raw 4-byte motor commands from USB serial at 115200 baud
	- Forwards commands to the band via ESP-NOW
	- Tracks send success/failure on serial logs

- Band firmware:
	- Receives motor commands over ESP-NOW
	- Reads IMU orientation
	- Remaps motor indices to preserve directional meaning relative to wrist orientation
	- Drives motor output pins

### Packet Format

Each command is exactly 4 bytes:

- Byte 0: top motor
- Byte 1: right motor
- Byte 2: bottom motor
- Byte 3: left motor

Each byte is 0 (off) or 1 (on).

## Software Components

### Host Command Interface

- software/how_to_send_mtr_cmds.md documents the serial protocol
- firmware/tools/test_send_mtr_cmd.py provides a quick motor-command generator for validation

### Computer Vision Prototype

- software/Pose.py runs MoveNet (TensorFlow Hub) on webcam frames
- Detects wrist keypoints and demonstrates where haptic feedback logic can plug in
- Current feedback hook prints decisions; it is not yet wired to serial transmission

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/connormmckelvey/Haptics-FRI
cd Haptics-FRI
```

### 2. Firmware setup (PlatformIO)

The firmware project is configured in firmware/platformio.ini for seeed_xiao_esp32c3.

From the firmware directory:

```bash
platformio run
platformio run --target upload
platformio device monitor -b 115200
```

Notes:

- The active source in firmware/src is the dongle firmware.
- Band firmware currently lives in firmware/excluded_src/band.cpp and is not in the default build path.
- Ensure dongle and band use the same ESP-NOW channel.
- Update the hardcoded band MAC address in firmware/src/dongle.cpp when changing hardware.

### 3. Python tooling setup

For motor command testing:

```bash
pip install pyserial
python firmware/tools/test_send_mtr_cmd.py
```

For vision prototype (software/Pose.py):

```bash
pip install opencv-python numpy tensorflow tensorflow-hub
python software/Pose.py
```

## Engineering Notes

- IMU calibration is performed at band startup; keep the device still during calibration.
- The serial command path uses raw bytes without framing, acknowledgements, or checksums.
- If packets stop midway, dongle firmware resets partial serial reads after a short timeout.

## Current Status and Known Gaps

- Root-level documentation is now expanded, but some subsystem docs are still in-progress.
- software/cv_docs.md is currently empty.
- Pose-to-haptics closed-loop integration is not complete yet.
- Band firmware is stored under excluded_src and may need project reconfiguration for direct builds.

## Suggested Next Milestones

1. Promote band firmware into an actively built PlatformIO target.
2. Add requirements files for reproducible Python environments.
3. Implement serial output from software/Pose.py into the 4-byte dongle protocol.
4. Add repeatable validation tests for motor mapping and IMU remapping behavior.

## Acknowledgment

This project was created in the UT Austin Freshman Research Initiative within the Human Enabled Robotics Lab (HERL), with the goal of combining embedded systems, wearable haptics, and human-robot interaction research.
