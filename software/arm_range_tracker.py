import cv2
import numpy as np
import tensorflow as tf
import tensorflow_hub as hub
import math
import serial

# -----------------------------
# Configuration
# -----------------------------
MODEL_URL = "https://tfhub.dev/google/movenet/singlepose/lightning/4"
INPUT_SIZE = 192
CONF_THRESHOLD = 0.3

LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST = 5, 7, 9
RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_WRIST = 6, 8, 10

SERIAL_PORT = "COM3"
BAUD_RATE = 115200

MOTORS_ALL_ON  = bytes([1, 1, 1, 1])
MOTORS_ALL_OFF = bytes([0, 0, 0, 0])

# -----------------------------
# ZONES — paste generated block here
# Each zone is either a normalized rect or polygon.
# Wrist INSIDE a zone = in range. Outside all zones = out of range.
#
# Example: a single rectangle covering the middle third of the frame.
# Replace with the output from the Zone Designer tool.
# -----------------------------
# --- Paste into your arm_range_tracker.py ---

# Canvas was 640x360. Coords are normalized (0.0-1.0) so they
# scale to any resolution automatically.

ZONES = [
    {  # Zone 1 — rectangle
        "type": "rect",
        "x":  0.1781,  "y":  0.2722,
        "x2": 0.7250, "y2": 0.7333,
    },
    {  # Zone 2 — rectangle
        "type": "rect",
        "x":  0.5266,  "y":  0.4500,
        "x2": 0.8578, "y2": 0.9306,
    },
    {  # Zone 3 — rectangle
        "type": "rect",
        "x":  0.6500,  "y":  0.3639,
        "x2": 0.7969, "y2": 0.5167,
    },
    {  # Zone 4 — rectangle
        "type": "rect",
        "x":  0.6953,  "y":  0.1389,
        "x2": 0.8000, "y2": 0.2694,
    },
    {  # Zone 5 — rectangle
        "type": "rect",
        "x":  0.8547,  "y":  0.2306,
        "x2": 0.9063, "y2": 0.3111,
    },
]


def point_in_zone(nx, ny, zone):
    """Returns True if normalized point (nx, ny) is inside the zone."""
    if zone["type"] == "rect":
        return zone["x"] <= nx <= zone["x2"] and zone["y"] <= ny <= zone["y2"]
    # Polygon — ray-casting algorithm (works for any convex or concave polygon)
    pts = zone["pts"]
    inside = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if ((yi > ny) != (yj > ny)) and (nx < (xj - xi) * (ny - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def wrist_in_any_zone(wx_px, wy_px, frame_w, frame_h):
    nx, ny = wx_px / frame_w, wy_px / frame_h
    return any(point_in_zone(nx, ny, z) for z in ZONES)


def draw_zones(frame, frame_w, frame_h):
    """Draw all zones onto the frame."""
    for zone in ZONES:
        if zone["type"] == "rect":
            x1 = int(zone["x"]  * frame_w)
            y1 = int(zone["y"]  * frame_h)
            x2 = int(zone["x2"] * frame_w)
            y2 = int(zone["y2"] * frame_h)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 200), 2)
        else:
            pts_px = [(int(x * frame_w), int(y * frame_h)) for x, y in zone["pts"]]
            pts_arr = np.array(pts_px, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(frame, [pts_arr], isClosed=True, color=(0, 200, 200), thickness=2)


# -----------------------------
# Serial helpers
# -----------------------------
def open_serial():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0)
        print(f"[Serial] Connected on {SERIAL_PORT}.")
        return ser
    except serial.SerialException as e:
        print(f"[Serial] WARNING — {e}. Running without haptics.")
        return None


def set_vibration(ser, active):
    if ser is None:
        return
    try:
        ser.write(MOTORS_ALL_ON if active else MOTORS_ALL_OFF)
    except serial.SerialException as e:
        print(f"[Serial] Write error: {e}")


# -----------------------------
# MoveNet
# -----------------------------
module = hub.load(MODEL_URL)
model = module.signatures["serving_default"]


def run_movenet(frame_bgr):
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    image = tf.expand_dims(frame_rgb, axis=0)
    image = tf.image.resize_with_pad(image, INPUT_SIZE, INPUT_SIZE)
    image = tf.cast(image, dtype=tf.int32)
    return model(image)["output_0"].numpy()


def get_keypoint(keypoints, w, h, index):
    y_norm, x_norm, score = keypoints[0, 0, index]
    return int(x_norm * w), int(y_norm * h), float(score)


# -----------------------------
# Main loop
# -----------------------------
def main():
    ser = open_serial()
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        if ser: ser.close()
        return

    vibrating = False

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            h, w, _ = frame.shape
            keypoints = run_movenet(frame)

            lw = get_keypoint(keypoints, w, h, LEFT_WRIST)
            rw = get_keypoint(keypoints, w, h, RIGHT_WRIST)

            # Pick the wrist with higher confidence
            wx, wy, wconf = lw if lw[2] >= rw[2] else rw
            side = "Left" if lw[2] >= rw[2] else "Right"

            # Draw zone boundaries
            draw_zones(frame, w, h)

            # Determine in/out of range
            if wconf >= CONF_THRESHOLD:
                in_range = wrist_in_any_zone(wx, wy, w, h)
                out_of_range = not in_range

                # Draw wrist dot — red if out of range, green if in
                dot_color = (0, 255, 0) if in_range else (0, 0, 255)
                cv2.circle(frame, (wx, wy), 8, dot_color, -1)

                # Haptic — only send on state change
                if out_of_range and not vibrating:
                    set_vibration(ser, True)
                    vibrating = True
                    print(f"[Haptic] ON  — {side} wrist outside zone ({wx}, {wy})")
                elif not out_of_range and vibrating:
                    set_vibration(ser, False)
                    vibrating = False
                    print(f"[Haptic] OFF — {side} wrist back in zone ({wx}, {wy})")

                status_text = "IN RANGE" if in_range else "OUT OF RANGE"
                status_color = (0, 200, 0) if in_range else (0, 0, 255)
            else:
                # Lost tracking — treat as out of range
                if not vibrating:
                    set_vibration(ser, True)
                    vibrating = True
                    print("[Haptic] ON  — wrist lost (low confidence)")
                status_text = "WRIST NOT DETECTED"
                status_color = (0, 140, 255)

            # Draw other joints for reference
            for idx in [LEFT_SHOULDER, LEFT_ELBOW, RIGHT_SHOULDER, RIGHT_ELBOW]:
                pt = get_keypoint(keypoints, w, h, idx)
                if pt[2] > CONF_THRESHOLD:
                    cv2.circle(frame, (pt[0], pt[1]), 5, (180, 180, 180), -1)

            cv2.putText(frame, status_text, (10, 38),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.1, status_color, 3)

            cv2.imshow("Wrist Zone Tracker", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        set_vibration(ser, False)
        cap.release()
        cv2.destroyAllWindows()
        if ser:
            ser.close()
            print("[Serial] Port closed.")


if __name__ == "__main__":
    main()
