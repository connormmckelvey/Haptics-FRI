import cv2
import numpy as np
import tensorflow as tf
import tensorflow_hub as hub

# -----------------------------
# Configuration
# -----------------------------
MODEL_URL = "https://tfhub.dev/google/movenet/singlepose/lightning/4"
INPUT_SIZE = 192
CONF_THRESHOLD = 0.3

# COCO keypoint indices used by MoveNet
LEFT_WRIST = 9
RIGHT_WRIST = 10

# -----------------------------
# Load MoveNet
# -----------------------------
module = hub.load(MODEL_URL)
model = module.signatures["serving_default"]


def run_movenet(frame_bgr: np.ndarray) -> np.ndarray:
    """
    Runs MoveNet on a BGR OpenCV frame.

    Returns:
        keypoints_with_scores: numpy array of shape [1, 1, 17, 3]
        Each keypoint is [y, x, score] in normalized image coordinates.
    """
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    image = tf.expand_dims(frame_rgb, axis=0)
    image = tf.image.resize_with_pad(image, INPUT_SIZE, INPUT_SIZE)
    image = tf.cast(image, dtype=tf.int32)

    outputs = model(image)
    keypoints_with_scores = outputs["output_0"].numpy()
    return keypoints_with_scores


def get_keypoint_pixel_coords(
    keypoints_with_scores: np.ndarray,
    frame_width: int,
    frame_height: int,
    keypoint_index: int
):
    """
    Converts a normalized MoveNet keypoint into pixel coordinates.

    Returns:
        (x_px, y_px, score)
    """
    y_norm, x_norm, score = keypoints_with_scores[0, 0, keypoint_index]
    x_px = int(x_norm * frame_width)
    y_px = int(y_norm * frame_height)
    return x_px, y_px, float(score)


def draw_wrist(frame: np.ndarray, x: int, y: int, score: float, label: str):
    """
    Draws wrist point and label on frame.
    """
    cv2.circle(frame, (x, y), 8, (0, 255, 0), -1)
    cv2.putText(
        frame,
        f"{label}: ({x}, {y}) s={score:.2f}",
        (x + 10, y - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (0, 255, 0),
        2
    )


def choose_wrist(left_wrist, right_wrist):
    """
    Choose whichever wrist has higher confidence.
    Each wrist is (x, y, score).
    """
    if left_wrist[2] >= right_wrist[2]:
        return "left", left_wrist
    return "right", right_wrist


def handle_haptic_feedback(wrist_name: str, wrist_x: int, wrist_y: int, score: float,
                           frame_width: int, frame_height: int):
    """
    Placeholder for your haptic logic.

    Example idea:
    - Define a target zone in the center of the screen.
    - If wrist is outside that zone, trigger armband.
    - If wrist is inside, stop vibration.

    Replace this with serial/bluetooth code to your armband.
    """
    target_x = frame_width // 2
    target_y = frame_height // 2
    tolerance = 60

    error_x = wrist_x - target_x
    error_y = wrist_y - target_y

    if score < CONF_THRESHOLD:
        print("Low confidence wrist detection -> no feedback")
        return

    if abs(error_x) <= tolerance and abs(error_y) <= tolerance:
        print(f"{wrist_name} wrist in target zone -> vibration OFF")
    else:
        print(
            f"{wrist_name} wrist outside zone -> vibration ON | "
            f"error_x={error_x}, error_y={error_y}"
        )


def main():
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        raise RuntimeError("Could not open webcam.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_height, frame_width, _ = frame.shape

        keypoints_with_scores = run_movenet(frame)

        left_wrist = get_keypoint_pixel_coords(
            keypoints_with_scores, frame_width, frame_height, LEFT_WRIST
        )
        right_wrist = get_keypoint_pixel_coords(
            keypoints_with_scores, frame_width, frame_height, RIGHT_WRIST
        )

        # Draw wrists if confident enough
        if left_wrist[2] > CONF_THRESHOLD:
            draw_wrist(frame, left_wrist[0], left_wrist[1], left_wrist[2], "L wrist")

        if right_wrist[2] > CONF_THRESHOLD:
            draw_wrist(frame, right_wrist[0], right_wrist[1], right_wrist[2], "R wrist")

        # Choose one wrist to drive the haptic feedback
        wrist_name, chosen_wrist = choose_wrist(left_wrist, right_wrist)
        handle_haptic_feedback(
            wrist_name,
            chosen_wrist[0],
            chosen_wrist[1],
            chosen_wrist[2],
            frame_width,
            frame_height
        )

        # Draw center target box
        target_x = frame_width // 2
        target_y = frame_height // 2
        tolerance = 60
        cv2.rectangle(
            frame,
            (target_x - tolerance, target_y - tolerance),
            (target_x + tolerance, target_y + tolerance),
            (255, 0, 0),
            2
        )

        cv2.imshow("MoveNet Wrist Tracking", frame)

        # Press q to quit
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()