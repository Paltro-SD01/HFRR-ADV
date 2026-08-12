import multiprocessing
multiprocessing.freeze_support()

import sys
import cv2
import ctypes
import socket
import threading
import time
import os

from PyQt5.QtWidgets import QApplication, QLabel, QWidget
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import QTimer, Qt, pyqtSignal, QThread

# ================= DPI AWARE =================
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception as e:
    print("⚠ DPI awareness not set:", e)

# ================= CONFIGURATION =================
WINDOW_WIDTH, WINDOW_HEIGHT = 1820, 1020
WINDOW_X, WINDOW_Y = 36, 275
TCP_IP, TCP_PORT = "0.0.0.0", 5006

# TCP Commands
CMD_CONNECT, CMD_START, CMD_STOP = 0x01, 0x02, 0x03
CMD_GRAY, CMD_RGB = 0x04, 0x05
CMD_MINIMIZE, CMD_CLOSE = 0x07, 0x08
CMD_LIST_MODES, CMD_SET_MODE_INDEX, CMD_RESTORE = 0x12, 0x13, 0x14
CMD_SAVE_IMAGE = 0x15

CMD_NAMES = {
    CMD_CONNECT: "CONNECT_CAMERA",
    CMD_START: "START_STREAM",
    CMD_STOP: "STOP_STREAM",
    CMD_GRAY: "GRAY_MODE",
    CMD_RGB: "RGB_MODE",
    CMD_MINIMIZE: "MINIMIZE",
    CMD_RESTORE: "RESTORE",
    CMD_CLOSE: "CLOSE_APP",
    CMD_LIST_MODES: "LIST_MODES",
    CMD_SET_MODE_INDEX: "SET_MODE_INDEX",
    CMD_SAVE_IMAGE: "SAVE_IMAGE"
}

# ================= NI-STYLE PROBE LOGIC =================

# ================= OPTIMIZED PROBE =================

def scan_available_cameras():
    results = []
    # Using MSMF or DSHOW; DSHOW is generally better for industrial USB
    for i in range(4): # Reduced range to 4 for faster startup unless you have 5+ cameras
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            results.append(f"INDEX {i}: {int(w)}x{int(h)}")
            cap.release()
        time.sleep(0.05) 
    return "\n".join(results) if results else "No Cameras Found"

def probe_camera_resolutions(index):
    """
    Safely probes for camera resolutions without forcing MJPG on industrial hardware.
    """
    print(f"📡 Probing Camera {index} (Industrial Safe Mode)...")
    
    # 1. Open with DSHOW
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        return []

    # Basic setup
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    
    # Check what the camera defaults to naturally
    default_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    default_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Try to grab one frame to verify the default works
    ret, frame = cap.read()
    if not ret or frame is None:
        print("❌ Camera opened but failed to provide a frame.")
        cap.release()
        return []

    # If the default is already high-res (like 4K), it's likely a microscope
    print(f"🔍 Default resolution detected: {default_w}x{default_h}")
    
    webcam_modes = []
    
    # Only attempt resolution switching if the camera isn't already 
    # at a high-end industrial resolution.
    if default_w < 2000:
        print("💡 Standard res detected, checking for webcam profiles...")
        # We check these WITHOUT forcing MJPG first
        targets = [(1920, 1080), (1280, 720), (640, 480)]
        for w, h in targets:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            time.sleep(0.2) # Give driver time to sync
            
            check_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            check_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            
            if check_w == w and check_h == h:
                webcam_modes.append((int(w), int(h), 30))

    cap.release()
    
    # MANDATORY: Industrial drivers need time to 'close' before being 'opened' again
    print("⏳ Probing finished. Cooling down driver...")
    time.sleep(1.5) 

    # If we found nothing or only one mode, return the microscope default
    if not webcam_modes:
        return [(default_w, default_h, 30)]
    
    return webcam_modes

class CameraWorker(QThread):
    frame_ready = pyqtSignal(object)
    camera_error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.cap = None
        self.gray_mode = False
        self.freeze_counter = 0
        self.running = False
        self.mode = None
        self.is_webcam = False
        self.cam_index = 0 # Add this to store the index

      
    def open_camera(self, index):
        self.cam_index = index

        if self.cap:
            self.cap.release()
            time.sleep(0.2) # Reduced for snappier restore

        self.cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            self.camera_error.emit("Camera open failed")
            return False

        # 🔑 IMPORTANT: disable buffering
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        return True



    def set_mode(self, mode):
        self.mode = mode
        if not self.cap or not mode:
            return

        w, h, fps = mode
        
        # Give the driver a moment to breathe before slamming it with 4K settings
        time.sleep(0.2) 

        if self.is_webcam:
            # Only webcams get MJPG; industrial cameras stay in RAW/YUY2
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        
        # Set resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        
        # Final sync sleep
        time.sleep(0.2)

    def run(self):
        self.running = True
        while self.running:
            if not self.cap or not self.cap.isOpened():
                self.msleep(100)
                continue

            ret, frame = self.cap.read()
            
            if not ret or frame is None:
                self.freeze_counter += 1
                if self.freeze_counter > 15:
                    print("🚨 Camera Timeout - Reconnecting...")
                    self.restart_camera()
                continue

            self.freeze_counter = 0

            # --- INSERTED GRAYSCALE LOGIC HERE ---
            if self.gray_mode:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                # Convert back to 3-channel BGR so UI/Save logic remains consistent
                frame = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            # -------------------------------------
            
            if self.running:
                # We emit the frame. Inside on_frame, we check if window is visible.
                # If you have high-res 4K frames, consider adding a small sleep here
                # to prevent the CPU from hitting 100% while minimized.
                self.frame_ready.emit(frame)
                
            # Adaptive sleep: If minimized, slow down to 10 FPS to save resources
            # If visible, run at full speed.
            # (Note: Requires a way to check visibility inside worker, or just msleep(10))
            self.msleep(10)

    def restart_camera(self):
        self.camera_error.emit("Restarting camera")
        if self.cap:
            self.cap.release()
            time.sleep(1)

        self.cap = cv2.VideoCapture(self.cam_index, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if self.mode:
            self.set_mode(self.mode)   # ⭐ REAPPLY MODE

        self.freeze_counter = 0

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()
            self.cap = None
        self.wait()

# ================= MAIN APPLICATION =================

class LiveStreamWindow(QWidget):
    sig_connect_camera = pyqtSignal(int)
    sig_start_stream   = pyqtSignal()
    sig_stop_stream    = pyqtSignal()
    sig_minimize       = pyqtSignal()
    sig_restore        = pyqtSignal()
    sig_close_app      = pyqtSignal()
    sig_set_mode       = pyqtSignal(int)
    sig_save_req       = pyqtSignal(str) 

    def recv_exact(self, conn, size):
        data = b''
        while len(data) < size:
            chunk = conn.recv(size - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def __init__(self):
        super().__init__()
        # Starts hidden (Tool flag prevents taskbar icon if desired)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setGeometry(WINDOW_X, WINDOW_Y, WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet("background-color:black;")

        self.video_label = QLabel(self)
        self.video_label.setGeometry(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
        self.video_label.setAlignment(Qt.AlignCenter)

        self.connected = False
        self.available_modes = []
        self.allow_remote_close = False   # 🔒 safety lock

        self.last_frame = None  # Clean BGR frame storage

        self.worker = CameraWorker()
        self.worker.frame_ready.connect(self.on_frame)
        self.worker.camera_error.connect(lambda e: print("⚠", e))

        # --- PLACE THE TRACKERS HERE ---
        self.current_cam_index = 0  
        self.current_mode = None    
        # -------------------------------

        # Signal Connections
        self.sig_connect_camera.connect(self.connect_camera)
        self.sig_start_stream.connect(self.start_stream)
        self.sig_stop_stream.connect(self.stop_stream)
        self.sig_minimize.connect(self.handle_minimize) 
        self.sig_restore.connect(self.restore_window)
        #self.sig_close_app.connect(QApplication.quit)
        self.sig_close_app.connect(self.cleanup_and_exit)
        self.sig_set_mode.connect(self.set_mode_by_index)
        self.sig_save_req.connect(self.save_image_logic)

        threading.Thread(target=self.tcp_server, daemon=True).start()
        print(f"✅ App ready (Hidden) — Listening on port {TCP_PORT}")

    def restore_window(self):
        """Re-opens camera hardware and shows UI."""
        if not self.isVisible():
            print("🔄 Restoring: Re-opening Camera Hardware...")
            
            if self.connected:
                # 1. Physically open the camera again
                if self.worker.open_camera(self.current_cam_index):
                    # 2. Re-apply the mode we saved earlier
                    if self.current_mode:
                        self.worker.set_mode(self.current_mode)
                    
                    # 3. Start the background thread
                    self.worker.running = True
                    self.worker.start()

            self.show()
            self.raise_()
            self.activateWindow()

    def handle_minimize(self):
        """Closes camera hardware and hides UI."""
        print("⏬ Minimizing: Releasing Camera Hardware...")
        if self.worker.isRunning():
            self.worker.stop() # This shuts down the thread and calls cap.release()
        
        self.video_label.clear() # Clear the last frame
        self.hide()

   # ================= UI LOGIC =================

    def on_frame(self, frame):
        # 1. Store the RAW frame immediately for background saves
        # This ensures CMD_SAVE_IMAGE works even if the window is minimized
        self.last_frame = frame.copy() 
        
        # 2. Performance Guard: If window is hidden, don't waste CPU on UI conversion
        if not self.isVisible(): 
            return 

        # 3. UI Processing (Only happens when window is visible)
        try:
            # Since worker always sends BGR (even if it looks gray), we just do one conversion
            display = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            h, w, ch = display.shape
            bytes_per_line = ch * w
            
            # Create QImage and FORCE a copy to stabilize memory for the UI thread
            img = QImage(display.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()

            pixmap = QPixmap.fromImage(img).scaled(
                WINDOW_WIDTH,
                WINDOW_HEIGHT,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.video_label.setPixmap(pixmap)

        # Explicit cleanup to assist garbage collection
            del img
            del pixmap
            
        except Exception as e:
            print(f"UI Render Error: {e}")

    def closeEvent(self, event):
        self.cleanup_and_exit()
        event.accept()

    def connect_camera(self, index):
        self.current_cam_index = index # Track the index
        # 1. Probe first
        self.available_modes = probe_camera_resolutions(index)
        
        # 2. CRITICAL: Wait for the driver to release the hardware
        time.sleep(1.0) 
        
        self.worker.is_webcam = len(self.available_modes) > 1

        # 3. Open the camera
        if self.worker.open_camera(index):
            self.connected = True
            
            # 4. Find the best mode
            target_mode = None
            for w, h, fps in self.available_modes:
                if w == 3840 and h == 2880:
                    target_mode = (w, h, fps)
                    break
            
            if not target_mode and self.available_modes:
                target_mode = self.available_modes[0]
                
            # 5. Set mode while the worker is NOT running
            if target_mode:
                self.current_mode = target_mode # Track the mode
                print(f"⚙ Mode Saved: {target_mode}")
                self.worker.set_mode(target_mode)

    def set_mode_by_index(self, idx):
        if 0 <= idx < len(self.available_modes):
            self.worker.set_mode(self.available_modes[idx])

    def start_stream(self):
        """Handles starting the camera logic."""
        if not self.connected:
            print("⚠ Cannot start: Camera not connected.")
            return

        # 1. If hidden, use restore logic to open hardware + show UI
        if not self.isVisible():
            self.restore_window()
        else:
            # 2. If already visible but worker is off, just start the hardware
            if not self.worker.isRunning():
                print("🚀 Starting Worker Thread (Already Visible)...")
                if self.worker.open_camera(self.current_cam_index):
                    if self.current_mode:
                        self.worker.set_mode(self.current_mode)
                    self.worker.running = True
                    self.worker.start()

    def stop_stream(self):
        if self.worker.isRunning():
            self.worker.stop()
        self.video_label.clear()
        self.hide()


    def save_image_logic(self, path):
        if self.last_frame is not None:
            try:
                # 1. Ensure the directory exists
                directory = os.path.dirname(path)
                if directory and not os.path.exists(directory):
                    os.makedirs(directory)

                # 2. Save the frame directly. 
                # self.last_frame is BGR (from OpenCV worker)
                # cv2.imwrite expects BGR. Perfect match.
                success = cv2.imwrite(path, self.last_frame)
                
                if success:
                    print(f"📸 Image Saved Successfully: {path}")
                else:
                    print(f"❌ OpenCV failed to write: {path}")
            except Exception as e:
                print(f"❌ Save Exception: {e}")

     
    def cleanup_and_exit(self):
        print("🧹 Cleaning up")
        self.allow_remote_close = True
        self.worker.stop()
        QApplication.instance().quit()


    def tcp_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((TCP_IP, TCP_PORT))
        server.listen(5)

        while True:
            conn, addr = server.accept()
            try:
                with conn:
                    while True:
                        header = conn.recv(3)
                        if not header or len(header) < 3: break
                        cmd, ln = header[0], int.from_bytes(header[1:3], "big")
                        
                        # Handle empty payload cases
                        payload_raw = self.recv_exact(conn, ln)
                        if payload_raw is None:
                            break

                        payload = payload_raw.decode() if payload_raw else ""

                        cmd_name = CMD_NAMES.get(cmd, "UNKNOWN")
                        print(f"[TCP] {cmd_name} (0x{cmd:02X}) | LEN={ln} | PAYLOAD='{payload}'")

                        if cmd == CMD_CONNECT: 
                            self.sig_connect_camera.emit(int(payload))

                        # ---> ADD THIS BLOCK HERE <---
                        elif cmd == 0x18: 
                            print("[TCP] Scanning all hardware ports...")
                            cam_list = scan_available_cameras()
                            # Send back response: ID 0x98 + Length + Data
                            conn.sendall(b'\x98' + len(cam_list).to_bytes(2, 'big') + cam_list.encode())
                        # ------------------------------
                        
                        elif cmd == CMD_START: 
                            self.sig_start_stream.emit()
                        elif cmd == CMD_STOP: 
                            self.sig_stop_stream.emit()
                        elif cmd == CMD_SET_MODE_INDEX: 
                            self.sig_set_mode.emit(int(payload))
                        elif cmd == CMD_SAVE_IMAGE: 
                            print(f"[TCP] SAVE REQUEST: '{payload}' len={len(payload)}")
                            self.sig_save_req.emit(payload)
                        elif cmd == CMD_LIST_MODES:
                            # Re-added the TCP response list
                            msg = "\n".join(f"{i}: {m[0]}x{m[1]}" for i, m in enumerate(self.available_modes))
                            #conn.send(b'\x90' + len(msg).to_bytes(2, 'big') + msg.encode())
                            conn.sendall(b'\x90' + len(msg).to_bytes(2, 'big') + msg.encode())

                        elif cmd == CMD_GRAY:
                            self.worker.gray_mode = True

                        elif cmd == CMD_RGB:
                            self.worker.gray_mode = False

                        elif cmd == CMD_RESTORE: self.sig_restore.emit()
                        elif cmd == CMD_MINIMIZE: self.sig_minimize.emit()
                        elif cmd == CMD_CLOSE:
                            if self.allow_remote_close:
                                self.sig_close_app.emit()
                            else:
                                print("🚫 TCP CLOSE ignored")

            except Exception as e:
                print("❌ TCP SERVER ERROR:", e)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = LiveStreamWindow()
    win.show()     # ensure Qt initializes
    win.hide()     # then hide
    # win.show() is omitted to start the process in the background
    sys.exit(app.exec_())