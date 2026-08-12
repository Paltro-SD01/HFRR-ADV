import torch
import cv2
import os
import time
import win32gui
import win32con
import win32api
import win32process
import socket
import threading
from pathlib import Path

pixel_to_mm_value = 0.0042525  # Conversion factor: pixel to mm

# --- Shared variables ---
command = None
running = True
client_conn = None
client_connected_event = threading.Event()
server_ready = threading.Event()
gain_value = 1.0   # <--- NEW: Modifiable gain
color_mode = "RGB"   # <--- NEW: RGB or GRAY mode

# --- Load YOLOv5 model ---
print("Loading YOLOv5 model...")
model = torch.hub.load('ultralytics/yolov5', 'custom',
                       path=r"C:\LAB-IQ 150\lib\best.pt")
print("YOLOv5 model loaded.")

# --- Window Settings ---
WINDOW_NAME = "frameless_bg"
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 850
WINDOW_X = 25
WINDOW_Y = 705

# --- Helper Functions ---
def bring_window_to_front():
    hwnd = win32gui.FindWindow(None, WINDOW_NAME)
    if hwnd:
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            fg_hwnd = win32gui.GetForegroundWindow()
            current_thread_id = win32api.GetCurrentThreadId()
            fg_thread_id, _ = win32process.GetWindowThreadProcessId(fg_hwnd)
            win32process.AttachThreadInput(fg_thread_id, current_thread_id, True)
            win32gui.SetForegroundWindow(hwnd)
            win32process.AttachThreadInput(fg_thread_id, current_thread_id, False)
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

def minimize_window():
    hwnd = win32gui.FindWindow(None, WINDOW_NAME)
    if hwnd:
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)

def close_window():
    global running
    running = False
    hwnd = win32gui.FindWindow(None, WINDOW_NAME)
    if hwnd:
        win32gui.ShowWindow(hwnd, win32con.SW_HIDE)

def resize_to_screen(img, max_width=WINDOW_WIDTH, max_height=WINDOW_HEIGHT):
    h, w = img.shape[:2]
    scale = min(max_width / w, max_height / h)
    if scale < 1:
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
    return img

def send_feedback(message):
    global client_conn
    try:
        if client_conn:
            client_conn.sendall(message.encode("utf-8"))
    except Exception:
        pass

# --- Heartbeat Thread ---
#def heartbeat_thread(interval=1.0):
    #client_connected_event.wait()
   # while running:
        #send_feedback("CAMERA_RUNNING")
        #time.sleep(interval)

# --- Socket Server ---
def socket_server(host="127.0.0.1", port=65432):
    global client_conn, running, command, gain_value, pixel_to_mm_value, color_mode
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen(1)
    print(f"[Socket Server] Listening on {host}:{port}")

    # Accept client
    def accept_loop():
        global client_conn
        while running and client_conn is None:
            try:
                server_sock.settimeout(1.0)
                client_conn, addr = server_sock.accept()
                print(f"[Socket Server] Connected by {addr}")
                client_connected_event.set()
            except socket.timeout:
                continue

    threading.Thread(target=accept_loop, daemon=True).start()

    # Receive commands
    while running:
        if client_conn:
            try:
                data = client_conn.recv(1024)
                if not data:
                    break
                cmd = data.decode("utf-8").strip().upper()

                # --- NEW: SET_GAIN Command ---
                if cmd.startswith("SET_GAIN"):
                    try:
                        parts = cmd.replace(",", " ").split()
                        if len(parts) >= 2:
                            gain_value = float(parts[1])
                            print("Updated Gain:", gain_value)
                            send_feedback(f"GAIN_OK {gain_value}")
                        else:
                            send_feedback("GAIN_ERROR")
                    except Exception as e:
                        print("GAIN ERROR:", e)
                        send_feedback("GAIN_ERROR")
                    continue

                # --- NEW: SET_PX2MM command ---
                elif cmd.startswith("SET_PX2MM"):
                    try:
                        parts = cmd.replace(",", " ").split()
                        if len(parts) >= 2:
                            pixel_to_mm_value = float(parts[1])
                            print("Updated Pixel-to-mm:", pixel_to_mm_value)
                            send_feedback(f"PX2MM_OK {pixel_to_mm_value}")
                        else:
                            send_feedback("PX2MM_ERROR")
                    except Exception as e:
                        print("PX2MM ERROR:", e)
                        send_feedback("PX2MM_ERROR")
                    continue

                # --- NEW SET_COLOR COMMAND ---
                elif cmd.startswith("SET_COLOR"):
                    try:
                        parts = cmd.replace(",", " ").split()
                        if len(parts) >= 2:
                            mode = parts[1].upper()
                            if mode in ["RGB", "GRAY"]:
                                color_mode = mode
                                print("Color Mode Updated:", color_mode)
                                send_feedback(f"COLOR_OK {color_mode}")
                            else:
                                send_feedback("COLOR_ERROR")
                        else:
                            send_feedback("COLOR_ERROR")
                    except:
                        send_feedback("COLOR_ERROR")
                    continue

                # --- NEW: SAVE IMAGE Command ---
                elif cmd == "SAVE_IMAGE":
                    command = "SAVE_IMAGE"
                    continue

                # Existing Commands
                elif cmd in ["SHOW", "MINIMIZE", "CLOSE"]:
                    command = cmd
                    continue

            except Exception:
                break
        else:
            time.sleep(0.1)

    if server_sock:
        server_sock.close()

# --- Main Camera + YOLO Server ---
def run_server():
    global command, running, gain_value, pixel_to_mm_value,color_mode

    # Output folder
    output_dir = Path(r"C:\LAB-IQ 150\images")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output folder: {output_dir}")

    # Start Camera
    print("Initializing webcam...")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        send_feedback("CAMERA_FAILED")
        print("Error: Could not open webcam.")
        return
    print("Webcam initialized.")

    # Start TCP Server
    threading.Thread(target=socket_server, daemon=True).start()

    # Signal ready
    server_ready.set()
    print("SERVER_READY")

    print("Waiting for LabVIEW TCP client...")
    client_connected_event.wait()
    #send_feedback("CAMERA_OK")

    # Start Heartbeat
    #threading.Thread(target=heartbeat_thread, daemon=True).start()

    # OpenCV Window
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, WINDOW_WIDTH, WINDOW_HEIGHT)

    hwnd = None
    while hwnd is None:
        hwnd = win32gui.FindWindow(None, WINDOW_NAME)
        time.sleep(0.05)

    # Remove title bar
    style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
    win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE,
                           style & ~(win32con.WS_CAPTION | win32con.WS_SYSMENU | win32con.WS_THICKFRAME))

    # Make window always on top
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST,
                          WINDOW_X, WINDOW_Y, WINDOW_WIDTH, WINDOW_HEIGHT,
                          win32con.SWP_SHOWWINDOW)

    # --- MAIN LOOP ---
    while running:
        ret, frame = cap.read()
        if not ret:
            print("Frame grab failed")
            break

        # Apply color mode
        if color_mode == "GRAY":
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            frame = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        # --- NEW: Apply Gain ---
        frame = cv2.convertScaleAbs(frame, alpha=gain_value)

        results = model(frame)
        df = results.pandas().xyxy[0]

        if len(df) > 0:
            row = df.iloc[0]

            major_x = row['xmax'] - row['xmin']
            minor_y = row['ymax'] - row['ymin']
            avg_scar = (major_x + minor_y) / 2

            major_mm = major_x * pixel_to_mm_value
            minor_mm = minor_y * pixel_to_mm_value
            avg_scar_mm = avg_scar * pixel_to_mm_value

            # ---- CONTINUOUS SINGLE-LINE UPDATE ----
            send_feedback(f"SCAR {major_mm:.3f}:{minor_mm:.3f}:{avg_scar_mm:.3f};")


            x1, y1 = int(row['xmin']), int(row['ymin'])
            x2, y2 = int(row['xmax']), int(row['ymax'])

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 1)
            txt_x, txt_y = x1, y2 + 30

            cv2.putText(frame, f"Major X: {major_mm:.3f} mm", (txt_x, txt_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
            cv2.putText(frame, f"Minor Y: {minor_mm:.3f} mm", (txt_x, txt_y + 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 1)
            cv2.putText(frame, f"Avg Scar: {avg_scar_mm:.3f} mm", (txt_x, txt_y + 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 1)

        resized_frame = resize_to_screen(frame)
        cv2.imshow(WINDOW_NAME, resized_frame)

        # --- Execute TCP Commands ---
        if command:
            if command == "SHOW":
                bring_window_to_front()

            elif command == "MINIMIZE":
                minimize_window()

            elif command == "CLOSE":
                close_window()

            elif command == "SAVE_IMAGE":
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                save_path = output_dir / f"image.png"
                cv2.imwrite(str(save_path), frame)
                print("Saved:", save_path)
                send_feedback(f"SAVED {save_path}")

            command = None

        if cv2.waitKey(1) & 0xFF == ord('q'):
            running = False
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Server stopped.")

# --- LabVIEW Entry ---
def start_server():
    t = threading.Thread(target=run_server)
    t.daemon = False
    t.start()
    server_ready.wait()
    return "SERVER_READY"


# Manual run
if __name__ == "__main__":
    run_server()
