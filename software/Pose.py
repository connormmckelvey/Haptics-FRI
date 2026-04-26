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

STRAIGHT_ARM_THRESHOLD = 160

SERIAL_PORT = "COM5"
BAUD_RATE = 115200

# Motor packet: [top, right, bottom, left]
MOTORS_OFF = bytes([0, 0, 0, 0])

# -----------------------------
# ZONES — paste the output from the Zone Designer here.
# Supports both "rect" and "polygon" types.
# Coords are normalized 0.0–1.0 so they scale to any resolution.
# -----------------------------
ZONES = [
    {  # Zone 1 — polygon
        "type": "polygon",
        "pts": [(0.4070, 0.2399), (0.5000, 0.1541), (0.5676, 0.1402), (0.6190, 0.1624), (0.7578, 0.3672), (0.7703, 0.5000), (0.7547, 0.5000), (0.7375, 0.5637), (0.6377, 0.6439), (0.5000, 0.6605), (0.5000, 0.6827), (0.4366, 0.7076), (0.3820, 0.6965), (0.3243, 0.6024), (0.3025, 0.4446), (0.3368, 0.3284), (0.3649, 0.2758), (0.4007, 0.2675), (0.4194, 0.2177)],
    },
]

# Set to True to use zone-based detection, False for original angle mode
USE_ZONE_MODE = True

# -----------------------------
# Zone geometry helpers
# -----------------------------
def _point_in_zone(nx, ny, zone):
    """Returns True if normalized point (nx, ny) is inside a single zone."""
    if zone["type"] == "rect":
        return zone["x"] <= nx <= zone["x2"] and zone["y"] <= ny <= zone["y2"]
    # Polygon — ray-casting algorithm
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

def _zone_bounding_box(zone):
    """Returns (x, y, x2, y2) normalized bounding box for any zone type."""
    if zone["type"] == "rect":
        return zone["x"], zone["y"], zone["x2"], zone["y2"]
    xs = [p[0] for p in zone["pts"]]
    ys = [p[1] for p in zone["pts"]]
    return min(xs), min(ys), max(xs), max(ys)

# -----------------------------
# Directional exit detection
# -----------------------------
def get_exit_directions(wx_px, wy_px, frame_w, frame_h):
    """
    Returns a list of directions the wrist has exited relative to the combined
    bounding box of all zones. Returns empty list if inside any zone.
    Supports both rect and polygon zones.
    """
    nx = wx_px / frame_w
    ny = wy_px / frame_h

    # If the wrist is inside ANY zone, it is in range — no haptic needed
    if any(_point_in_zone(nx, ny, z) for z in ZONES):
        return []

    # Wrist is outside all zones — determine exit direction from combined bbox
    all_x1 = min(_zone_bounding_box(z)[0] for z in ZONES)
    all_y1 = min(_zone_bounding_box(z)[1] for z in ZONES)
    all_x2 = max(_zone_bounding_box(z)[2] for z in ZONES)
    all_y2 = max(_zone_bounding_box(z)[3] for z in ZONES)

    directions = []
    if ny < all_y1: directions.append("top")
    if ny > all_y2: directions.append("bottom")
    if nx < all_x1: directions.append("left")
    if nx > all_x2: directions.append("right")
    return directions

def directions_to_motor_packet(directions):
    """Builds a 4-byte packet [top, right, bottom, left] from a list of directions."""
    top    = 1 if "top"    in directions else 0
    right  = 1 if "right"  in directions else 0
    bottom = 1 if "bottom" in directions else 0
    left   = 1 if "left"   in directions else 0
    return bytes([top, right, bottom, left])

def draw_zone(frame, frame_w, frame_h, directions):
    """Draw all zones onto the frame, highlighting exit edges on rects."""
    for zone in ZONES:
        if zone["type"] == "rect":
            x1 = int(zone["x"]  * frame_w)
            y1 = int(zone["y"]  * frame_h)
            x2 = int(zone["x2"] * frame_w)
            y2 = int(zone["y2"] * frame_h)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 200), 1)
            t = 3
            if "top"    in directions: cv2.line(frame, (x1, y1), (x2, y1), (0, 0, 255), t)
            if "bottom" in directions: cv2.line(frame, (x1, y2), (x2, y2), (0, 0, 255), t)
            if "left"   in directions: cv2.line(frame, (x1, y1), (x1, y2), (0, 0, 255), t)
            if "right"  in directions: cv2.line(frame, (x2, y1), (x2, y2), (0, 0, 255), t)
        else:
            # Polygon zone
            pts_px = np.array(
                [(int(p[0] * frame_w), int(p[1] * frame_h)) for p in zone["pts"]],
                dtype=np.int32
            )
            color = (0, 0, 255) if directions else (0, 200, 200)
            cv2.polylines(frame, [pts_px], isClosed=True, color=color, thickness=2)

# -----------------------------
# Serial helpers
# -----------------------------
def open_serial():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0)
        print(f"[Serial] Connected on {SERIAL_PORT} @ {BAUD_RATE} baud.")
        return ser
    except serial.SerialException as e:
        print(f"[Serial] WARNING — {e}. Running without haptics.")
        return None

def send_motor_packet(ser, packet):
    if ser is None:
        return
    try:
        ser.write(packet)
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

def calculate_arm_angle(shoulder, elbow, wrist):
    if shoulder[2] < CONF_THRESHOLD or elbow[2] < CONF_THRESHOLD or wrist[2] < CONF_THRESHOLD:
        return None
    ba = (shoulder[0] - elbow[0], shoulder[1] - elbow[1])
    bc = (wrist[0] - elbow[0], wrist[1] - elbow[1])
    dot = ba[0]*bc[0] + ba[1]*bc[1]
    mag_ba = math.sqrt(ba[0]**2 + ba[1]**2)
    mag_bc = math.sqrt(bc[0]**2 + bc[1]**2)
    if mag_ba == 0 or mag_bc == 0:
        return None
    return math.degrees(math.acos(max(-1, min(1, dot / (mag_ba * mag_bc)))))

# -----------------------------
# Main loop
# -----------------------------
def main():
    ser = open_serial()
    # ser = None  # Uncomment to disable haptics while testing

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        if ser: ser.close()
        return

    last_direction = []  # tracks last sent directions to avoid redundant writes

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            h, w, _ = frame.shape
            keypoints = run_movenet(frame)

            ls = get_keypoint(keypoints, w, h, LEFT_SHOULDER)
            le = get_keypoint(keypoints, w, h, LEFT_ELBOW)
            lw = get_keypoint(keypoints, w, h, LEFT_WRIST)
            rs = get_keypoint(keypoints, w, h, RIGHT_SHOULDER)
            re = get_keypoint(keypoints, w, h, RIGHT_ELBOW)
            rw = get_keypoint(keypoints, w, h, RIGHT_WRIST)

            # Pick wrist with higher confidence
            #if lw[2] >= rw[2]:
            #    wx, wy, wconf = lw
            #    current_elbow, side_label = le, "Left"
            #    current_angle = calculate_arm_angle(ls, le, lw)
            #else:
            wx, wy, wconf = rw
            current_elbow, side_label = re, "Right"
            current_angle = calculate_arm_angle(rs, re, rw)

            # ------------------------------------------
            # Directional exit detection (zone mode)
            # ------------------------------------------
            if USE_ZONE_MODE:
                if wconf >= CONF_THRESHOLD:
                    directions = get_exit_directions(wx, wy, w, h)
                else:
                    directions = []  # lost tracking — all motors off

                # Only send a packet when the active direction set changes
                if directions != last_direction:
                    packet = directions_to_motor_packet(directions) if directions else MOTORS_OFF
                    send_motor_packet(ser, packet)
                    last_direction = directions
                    if directions:
                        label = " + ".join(d.upper() for d in directions)
                        print(f"[Haptic] {label} motor(s) ON — {side_label} wrist exited {label}")
                    else:
                        print(f"[Haptic] OFF — {side_label} wrist back in zone")

                draw_zone(frame, w, h, directions)

                # Wrist dot colour
                dot_color = (0, 0, 255) if directions else (0, 255, 0)
                if wconf >= CONF_THRESHOLD:
                    cv2.circle(frame, (wx, wy), 8, dot_color, -1)

                # Status text
                status_text  = "EXIT: " + " + ".join(d.upper() for d in directions) if directions else "IN RANGE"
                status_color = (0, 0, 255) if directions else (0, 200, 0)

            else:
                # Original angle mode
                out_of_range = (current_angle is not None and
                                current_angle > STRAIGHT_ARM_THRESHOLD)
                if out_of_range and last_direction != ["angle"]:
                    send_motor_packet(ser, bytes([1, 1, 1, 1]))
                    last_direction = ["angle"]
                    print(f"[Haptic] ON — {side_label} angle {current_angle:.1f}°")
                elif not out_of_range and last_direction == ["angle"]:
                    send_motor_packet(ser, MOTORS_OFF)
                    last_direction = []
                    print(f"[Haptic] OFF — {side_label} back in range")

                for pt in [ls, le, lw, rs, re, rw]:
                    if pt[2] > CONF_THRESHOLD:
                        cv2.circle(frame, (pt[0], pt[1]), 6, (0, 255, 0), -1)

                if current_angle is not None:
                    angle_color = (0, 0, 255) if out_of_range else (0, 255, 0)
                    cv2.putText(frame,
                                f"{side_label} Angle: {int(current_angle)} deg",
                                (current_elbow[0] + 15, current_elbow[1]),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, angle_color, 2)

                status_text  = "OUT OF RANGE" if out_of_range else "IN RANGE"
                status_color = (0, 0, 255) if out_of_range else (0, 200, 0)

            # Draw other joints
            for pt in [ls, le, rs, re]:
                if pt[2] > CONF_THRESHOLD:
                    cv2.circle(frame, (pt[0], pt[1]), 5, (180, 180, 180), -1)

            mode_label = "ZONE" if USE_ZONE_MODE else "ANGLE"
            cv2.putText(frame, f"[{mode_label}] {status_text}", (10, 38),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, status_color, 3)

            cv2.imshow("Pose Tracker", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        send_motor_packet(ser, MOTORS_OFF)
        cap.release()
        cv2.destroyAllWindows()
        if ser:
            ser.close()
            print("[Serial] Port closed.")

if __name__ == "__main__":
    main()