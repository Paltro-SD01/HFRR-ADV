import torch
import cv2
import os
import numpy as np

# Load YOLOv5 model globally (only once)
model = torch.hub.load(
    r"C:\LAB-IQ\yolov5",   # LOCAL PATH
    'custom',
    path=r"C:\LAB-IQ\lib\best.pt",
    source='local'
)


def create_ellipse_mask(height, width, center, axes, angle=0):
    """Create a black image with a white ellipse."""
    mask = np.zeros((height, width, 3), dtype=np.uint8)  # Black canvas
    axes = (int(axes[0] / 2), int(axes[1] / 2))  # cv2.ellipse uses half axes
    cv2.ellipse(mask, center, axes, angle, 0, 360, (255, 255, 255), -1)
    return mask

def save_comparison(folder, name, original_img, masked_img, predicted_img):
    """Save side-by-side comparison of original, masked and predicted images."""
    comparison_img = np.hstack((original_img, masked_img, predicted_img))
    comparison_path = os.path.join(folder, f"{name}_comparison.jpg")
    cv2.imwrite(comparison_path, comparison_img)
    return comparison_path

def analyze_image(image_path, scar_gain):
    # Run inference
    results = model(image_path)
    df = results.pandas().xyxy[0]

    # Read image
    original_img = cv2.imread(image_path)
    img = original_img.copy()
    height, width = img.shape[:2]

    # Default values (Python-native floats)
    minor_mm = 0.0
    major_mm = 0.0
    scar_value_mm = 0.0

    # Black canvas for masked ellipse only
    masked_img = np.zeros_like(img)

    if len(df) > 0:
        row = df.iloc[0]

        # Pixel measurements
        major_x = float(row['xmax'] - row['xmin'])
        minor_y = float(row['ymax'] - row['ymin'])
        avg_scar = (major_x + minor_y) / 2.0

        # Convert to mm (force Python float)
        major_mm = float(major_x * scar_gain)
        minor_mm = float(minor_y * scar_gain)
        scar_value_mm = float(avg_scar * scar_gain)

        # Bounding box
        x1, y1, x2, y2 = int(row['xmin']), int(row['ymin']), int(row['xmax']), int(row['ymax'])

        # Calculate bounding box center
        bbox_cx = (x1 + x2) // 2
        bbox_cy = (y1 + y2) // 2

        # Desired center of image
        center_x, center_y = width // 2, height // 2

        # Calculate shifts
        shift_x = center_x - bbox_cx
        shift_y = center_y - bbox_cy

        # Translate image
        M = np.float32([[1, 0, shift_x], [0, 1, shift_y]])
        img = cv2.warpAffine(img, M, (width, height), borderMode=cv2.BORDER_REPLICATE)

        # Update bounding box coordinates after shift
        x1 += shift_x
        x2 += shift_x
        y1 += shift_y
        y2 += shift_y

        # Draw bold bounding box
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 255), 8)

        # Draw reference lines along bounding box edges
        cv2.line(img, (0, y1), (width, y1), (255, 0, 0), 3)
        cv2.line(img, (0, y2), (width, y2), (255, 0, 0), 3)
        cv2.line(img, (x1, 0), (x1, height), (255, 0, 0), 3)
        cv2.line(img, (x2, 0), (x2, height), (255, 0, 0), 3)

        # Draw scar text
        text_x, text_y = x1, y2 + 50
        cv2.putText(img, f"Scar: {scar_value_mm:.3f} mm", (text_x, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 4)

        # --- Create white ellipse only inside bounding box ---
        bbox_width = x2 - x1
        bbox_height = y2 - y1
        bbox_center = (x1 + bbox_width//2, y1 + bbox_height//2)
        masked_img = create_ellipse_mask(height, width, bbox_center, (bbox_width, bbox_height), angle=0)

    # Save predicted image separately
    folder, filename = os.path.split(image_path)
    name, ext = os.path.splitext(filename)

    predicted_path = os.path.join(folder, f"{name}_{scar_value_mm:.3f}mm_predicted.jpg")
    cv2.imwrite(predicted_path, img)

    # Save comparison image (original | masked | predicted)
    comparison_path = save_comparison(folder, f"{name}_{scar_value_mm:.3f}mm", original_img, masked_img, img)

    # Final cast to pure Python types (safe for LabVIEW)
    return (
        str(comparison_path),
        str(predicted_path),
        float(minor_mm),
        float(major_mm),
        float(scar_value_mm)
    )

if __name__ == "__main__":
    image_path = r"C:\LAB-IQ\images\dfvfd.png"
    scar_gain = 0.0005

    comparison_path, predicted_path, minor, major, avg = analyze_image(image_path, scar_gain)
    print("\n--- Test Run ---")
    print("Comparison Image:", comparison_path)
    print("Predicted Image:", predicted_path)
    print(f"Major Axis: {major:.3f} mm")
    print(f"Minor Axis: {minor:.3f} mm")
    print(f"Average Scar: {avg:.3f} mm")
