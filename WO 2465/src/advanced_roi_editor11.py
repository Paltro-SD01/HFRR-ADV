#PROPER WORKING CODE WITH PROPER RECTANGLE RESIZE

import sys, json, math, struct, traceback
import cv2
import numpy as np
import ctypes
ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtNetwork import QTcpServer, QTcpSocket, QHostAddress
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QTimer

TCP_PORT = 5005
STREAM_INTERVAL_MS = 500
HANDLE_SIZE = 8   # px hit area

# ================= DEBUG HELPERS =================
def hex_dump(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)

def log(msg):
    print(msg, flush=True)

# ================= ROI =================
class ROI:
    def __init__(self, roi_type, p1, p2, color=(0, 255, 0)):
        self.type = roi_type  # rectangle | line
        self.p1 = list(p1)
        self.p2 = list(p2)
        self.color = color

    def normalize(self):
        if self.type == "rectangle":
            self.p1[0], self.p2[0] = sorted([self.p1[0], self.p2[0]])
            self.p1[1], self.p2[1] = sorted([self.p1[1], self.p2[1]])

    def rect(self):
        self.normalize()
        return self.p1[0], self.p1[1], self.p2[0], self.p2[1]

    def handles(self):
        if self.type == "line":
            # Line handles: two endpoints + center
            cx, cy = (self.p1[0] + self.p2[0]) // 2, (self.p1[1] + self.p2[1]) // 2
            return {
                "p1": tuple(self.p1),
                "p2": tuple(self.p2),
                "c": (cx, cy)   # center handle for resizing/stretching
            }
        else:
            # Rectangle handles (existing logic)
            x1, y1, x2, y2 = self.rect()
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            return {
                "tl": (x1, y1), "tr": (x2, y1),
                "bl": (x1, y2), "br": (x2, y2),
                "l":  (x1, cy), "r":  (x2, cy),
                "t":  (cx, y1), "b":  (cx, y2)
            }


    def hit_test(self, pt):
        x, y = pt
        for name, (hx, hy) in self.handles().items():
            if abs(x - hx) <= HANDLE_SIZE and abs(y - hy) <= HANDLE_SIZE:
                return name
        return None

    def contains(self, pt):
        if self.type == "line":
            # distance from point to line segment
            px, py = pt
            x1, y1 = self.p1
            x2, y2 = self.p2
            if (x1, y1) == (x2, y2):
                return False
            num = abs((y2 - y1)*px - (x2 - x1)*py + x2*y1 - y2*x1)
            den = math.hypot(y2 - y1, x2 - x1)
            dist = num / den
            return dist <= HANDLE_SIZE*1.5
        # rectangle contains
        x, y = pt
        x1, y1, x2, y2 = self.rect()
        return x1 <= x <= x2 and y1 <= y <= y2

# ================= CANVAS =================
class ImageCanvas(QLabel):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setMouseTracking(True)
        self.start_pt = None
        self.temp_pt = None
        self.drawing = False
        self.pan_start = None
        self.resizing = False
        self.resize_handle = None
        self.last_move_pt = None  # <-- Smooth line resize helper

    def force_exit_pan(self):
        self.pan_start = None

    def mousePressEvent(self, event):
        img_pt = self.parent.screen_to_image(event.pos())

        # 🔥 HARD STOP PAN IF TOOL CHANGED
        if self.parent.draw_type != "pan":
            self.pan_start = None


        if event.button() == Qt.LeftButton:
            # ---- RESIZE MODE ----
            if self.parent.draw_type == "resize":
                for i, roi in enumerate(self.parent.rois):
                    handle = roi.hit_test(img_pt)
                    if handle:
                        # Endpoint resize
                        self.parent.selected = i
                        self.resizing = True
                        self.resize_handle = handle
                        self.last_move_pt = img_pt.copy()
                        log(f"[UI] Resize start handle={handle}")
                        self.parent.redraw()
                        return
                    elif roi.type == "line" and roi.contains(img_pt):
                        # Entire line move
                        self.parent.selected = i
                        self.resizing = True
                        self.resize_handle = "move"
                        self.last_move_pt = img_pt.copy()
                        log("[UI] Move entire line")
                        self.parent.redraw()
                        return


            # ---- DRAW MODE ----
            elif self.parent.draw_type in ("rectangle", "line"):
                self.start_pt = img_pt
                self.temp_pt = img_pt.copy()
                self.drawing = True
            # ---- PAN MODE ----
                        # ---- PAN MODE ----
            elif self.parent.draw_type == "pan":
                self.pan_start = QPoint(event.pos())


    def mouseMoveEvent(self, event):
        img_pt = self.parent.screen_to_image(event.pos())

        # ---- ACTIVE RESIZING ----
        if self.resizing and self.parent.selected is not None:
            roi = self.parent.rois[self.parent.selected]
            h = self.resize_handle
            if roi.type == "line":
                #if not hasattr(self, "last_move_pt"):
                    #self.last_move_pt = img_pt.copy()
                dx, dy = img_pt[0] - self.last_move_pt[0], img_pt[1] - self.last_move_pt[1]
                self.last_move_pt = img_pt.copy()

                if h == "p1":
                    roi.p1[0] += dx
                    roi.p1[1] += dy
                elif h == "p2":
                    roi.p2[0] += dx
                    roi.p2[1] += dy
                elif h == "c" or h == "move":
                    # move both endpoints together
                    roi.p1[0] += dx
                    roi.p1[1] += dy
                    roi.p2[0] += dx
                    roi.p2[1] += dy

                self.parent.redraw()   # ✅ THIS WAS MISSING

            else:
                # Rectangle handle resize (same as before)
                # Rectangle resizing by handle
                if h == "tl":
                    roi.p1[0] = img_pt[0]
                    roi.p1[1] = img_pt[1]
                elif h == "tr":
                    roi.p2[0] = img_pt[0]
                    roi.p1[1] = img_pt[1]
                elif h == "bl":
                    roi.p1[0] = img_pt[0]
                    roi.p2[1] = img_pt[1]
                elif h == "br":
                    roi.p2[0] = img_pt[0]
                    roi.p2[1] = img_pt[1]
                elif h == "l":
                    roi.p1[0] = img_pt[0]
                elif h == "r":
                    roi.p2[0] = img_pt[0]
                elif h == "t":
                    roi.p1[1] = img_pt[1]
                elif h == "b":
                    roi.p2[1] = img_pt[1]

                self.parent.redraw()   # ✅ THIS WAS MISSING

        # ---- RESIZE MODE HOVER ----
        if self.parent.draw_type == "resize" and self.parent.selected is not None:
            roi = self.parent.rois[self.parent.selected]
            handle = roi.hit_test(img_pt)
            if handle:
                if roi.type == "line":
                    if handle in ("p1", "p2"):
                        self.setCursor(Qt.CrossCursor)
                    else:
                        self.setCursor(Qt.SizeAllCursor)
                elif handle in ("l","r"):
                    self.setCursor(Qt.SizeHorCursor)
                elif handle in ("t","b"):
                    self.setCursor(Qt.SizeVerCursor)
                elif handle in ("tl","br"):
                    self.setCursor(Qt.SizeFDiagCursor)
                elif handle in ("tr","bl"):
                    self.setCursor(Qt.SizeBDiagCursor)
                else:
                    self.setCursor(Qt.SizeAllCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
        else:
            self.setCursor(Qt.ArrowCursor)   # <<< ADD THIS


        # ---- DRAWING ----
        if self.drawing:
            self.temp_pt = img_pt
            self.parent.redraw()
            return

        # ---- PAN ----
        if self.parent.draw_type == "pan" and self.pan_start:
            dx = self.pan_start.x() - event.pos().x()
            dy = self.pan_start.y() - event.pos().y()
            self.parent.scroll.horizontalScrollBar().setValue(
                self.parent.scroll.horizontalScrollBar().value() + dx)
            self.parent.scroll.verticalScrollBar().setValue(
                self.parent.scroll.verticalScrollBar().value() + dy)
            self.pan_start = QPoint(event.pos())

    def leaveEvent(self, event):
        if self.resizing:
            self.resizing = False
            self.resize_handle = None
            self.move_offset = None
            self.parent.mode = "draw"     # <<< ADD THIS
            self.parent.redraw()
        self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        self.pan_start = None

        if self.resizing:
            log("[UI] Resize end")
            roi = self.parent.rois[self.parent.selected]
            roi.normalize()
            self.pan_start = None
            self.resizing = False
            self.resize_handle = None
            self.move_offset = None
            self.parent.mode = "draw"   # <<< ADD THIS
            self.parent.redraw()        # <<< ENSURE canvas updates
            return

        if self.drawing and event.button() == Qt.LeftButton:
            roi = ROI(self.parent.draw_type, self.start_pt, self.temp_pt)
            roi.normalize()
            self.parent.rois.append(roi)
            self.parent.selected = len(self.parent.rois)-1
            self.drawing = False
            self.start_pt = None
            self.temp_pt = None
            self.parent.redraw()

       


# ================= MAIN =================
class ImagingSystem(QMainWindow):
    def __init__(self):
        super().__init__()

        # ================= WINDOW CONTROL =================
        WINDOW_WIDTH  = 1770
        WINDOW_HEIGHT = 1020
        WINDOW_X = 24
        WINDOW_Y = 270

        # Borderless + Always on Top
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )

        # Exact fixed size (pixel perfect)
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)

        # Exact screen position
        self.move(WINDOW_X, WINDOW_Y)
        # ==================================================
        self.selected = None
        self.mode = "draw"
        self.draw_type = "rectangle"
        self.dragging = False
        self.drag_handle = None
        self.drag_offset = None
        self.start_pt = None
        self.temp_end = None
        self.pan_start = None
        self.image = None
        self.zoom = 1.0
        self.rois = []

        # TCP
        self.client = None
        self.buffer = b""
        self.stream_enabled = False
        self.loading_image = False   # ✅ ADD THIS

        self.build_ui()
        self.start_tcp()
        self.init_stream_timer()

    def reset_state_for_new_image(self):
        # Stop interactions
        self.canvas.drawing = False
        self.canvas.resizing = False
        self.canvas.resize_handle = None
        self.canvas.pan_start = None
        self.canvas.start_pt = None
        self.canvas.temp_pt = None

        # Reset ROI state
        self.rois.clear()
        self.selected = None

        # Reset modes
        self.mode = "draw"
        self.draw_type = "rectangle"

        # Stop streaming
        self.stream_enabled = False
        if self.timer.isActive():
            self.timer.stop()

        # Reset zoom
        self.zoom = 1.0

    def reset_mouse_state(self):
        self.canvas.force_exit_pan()   # <<< ADD THIS
        # 🔒 Hard stop all mouse interactions
        self.canvas.pan_start = None
        self.canvas.drawing = False
        self.canvas.resizing = False
        self.canvas.resize_handle = None
        self.canvas.start_pt = None
        self.canvas.temp_pt = None



    # ===== UI =====
    def build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        self.canvas = ImageCanvas(self)
        self.canvas.setStyleSheet("background:black;")
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.canvas)
        self.scroll.setWidgetResizable(False)
        layout.addWidget(self.scroll)

    # ===== TCP =====
    def start_tcp(self):
        self.server = QTcpServer(self)
        self.server.newConnection.connect(self.on_client)
        ok = self.server.listen(QHostAddress.Any, TCP_PORT)

        if not ok:
            log("[TCP][FATAL] Cannot bind TCP port")
            sys.exit(1)

        log(f"[TCP] Server listening on port {TCP_PORT}")

        # ✅ Write a ready flag file (optional but powerful)
        with open("roi_editor_ready.flag", "w") as f:
            f.write("READY")


    def on_client(self):
        self.client = self.server.nextPendingConnection()
        self.client.readyRead.connect(self.read_binary)
        self.client.disconnected.connect(self.on_disconnect)
        log("[TCP] Client connected")

    def on_disconnect(self):
        log("[TCP] Client disconnected")
        self.client = None
        self.buffer = b""

    def read_binary(self):
        data = self.client.readAll().data()
        log(f"[RX] Raw bytes: {hex_dump(data)}")
        self.buffer += data

        while True:
            if len(self.buffer) < 3: return
            cmd = self.buffer[0]
            if cmd > 0x7F:
                log(f"[RX][ERR] Invalid CMD byte: {cmd}")
                self.send_packet(0x81, b"Invalid CMD")
                self.buffer = self.buffer[1:]
                continue
            length = struct.unpack(">H", self.buffer[1:3])[0]
            if len(self.buffer) < 3 + length: return
            payload = self.buffer[3:3+length]
            self.buffer = self.buffer[3+length:]
            log(f"[RX] CMD=0x{cmd:02X}, LEN={length}")
            self.process_cmd(cmd, payload)

    def send_packet(self, cmd, payload=b""):
        pkt = struct.pack(">BH", cmd, len(payload)) + payload
        log(f"[TX] CMD=0x{cmd:02X}, LEN={len(payload)}")
        if self.client:
            self.client.write(pkt)
            self.client.flush()

    # ===== COMMANDS =====
    def process_cmd(self, cmd, payload):
        try:
            VALID_CMDS = {
                0x01,0x02,0x03,0x04,0x05,0x06,0x07,0x08,
                0x12,0x13,0x14,0x20,0x21,
                0x30,0x31,0x32,0x33,0x34,0x15,0X16,0x00,
            }

            #VALID_CMDS = {0x01,0x02,0x03,0x04,0x05,0x06,0x07,0x08,0x12,0x13,0x14,0x20,0x21}
            if cmd not in VALID_CMDS:
                log(f"[CMD][REJECT] 0x{cmd:02X}")
                self.send_packet(0x81, b"Unsupported CMD")
                return

            if cmd == 0x01:  # OPEN FILE
                if getattr(self, "loading_image", False):
                    self.send_packet(0x81, b"Busy loading image")
                    return

                self.loading_image = True
                try:
                    self.reset_state_for_new_image()

                    path = payload.decode().strip()   # ✅ FIX
                    log(f"[CMD] Open file: {path}")

                    img = cv2.imread(path)
                    if img is None:
                        raise ValueError("Image load failed")

                    self.image = img
                    self.fit()
                    self.send_packet(0x80)
                finally:
                    self.loading_image = False


            elif cmd == 0x02:  # FIT
                self.fit(); self.send_packet(0x80)

            elif cmd == 0x03:  # DRAW RECT
                self.reset_mouse_state()
                self.mode = "draw"
                self.draw_type = "rectangle"
                self.send_packet(0x80)

            elif cmd == 0x04:  # DRAW LINE
                self.reset_mouse_state()
                self.mode = "draw"
                self.draw_type = "line"
                self.send_packet(0x80)
             
            elif cmd == 0x05:  # PAN
                self.reset_mouse_state()   # <<< ADD THIS
                self.mode = "draw"
                self.draw_type = "pan"
                self.send_packet(0x80)


            elif cmd == 0x14:  # RESIZE MODE
                self.reset_mouse_state()

                # 🔥 FORCE COORDINATE REALIGN
                self.scroll.horizontalScrollBar().setValue(
                    self.scroll.horizontalScrollBar().value()
                )
                self.scroll.verticalScrollBar().setValue(
                    self.scroll.verticalScrollBar().value()
                )

                self.mode = "draw"
                self.draw_type = "resize"
                self.redraw()
                self.send_packet(0x80)

            elif cmd == 0x06:  # ZOOM IN
                self.zoom *= 1.2; self.redraw(); self.send_packet(0x80)

            elif cmd == 0x07:  # ZOOM OUT
                self.zoom /= 1.2; self.redraw(); self.send_packet(0x80)

            elif cmd == 0x08:  # SET ZOOM
                self.zoom = struct.unpack(">f", payload)[0]; self.redraw(); self.send_packet(0x80)

            elif cmd == 0x12:  # CLEAR ROI
                self.rois.clear(); self.selected=None; self.redraw(); self.send_packet(0x80)

            elif cmd == 0x13:  # GET MEASUREMENTS
                self.send_packet(0x80, json.dumps(self.get_measurements()).encode())

            elif cmd == 0x14:  # RESIZE MODE
                self.reset_mouse_state()   # <<< ADD THIS
                self.mode = "draw"
                self.draw_type = "resize"
                self.send_packet(0x80)


            elif cmd == 0x20:  # STREAM START
                self.stream_enabled = True; self.timer.start(STREAM_INTERVAL_MS); self.send_packet(0x80)

            elif cmd == 0x21:  # STREAM STOP
                self.stream_enabled = False; self.timer.stop(); self.send_packet(0x80)

            elif cmd == 0x30:  # SHOW UI (FORCE FRONT)
                self.showNormal()          # ensure not minimized
                self.show()

                # ---- Windows foreground workaround ----
                ctypes.windll.user32.AllowSetForegroundWindow(-1)

                QTimer.singleShot(50, self._force_foreground)

                self.send_packet(0x80)

            elif cmd == 0x31:  # MINIMIZE UI
                self.showMinimized()
                self.send_packet(0x80)

            elif cmd == 0x32:  # HIDE UI
                self.hide()
                self.send_packet(0x80)

            elif cmd == 0x33:  # CLOSE APP (graceful)
                self.send_packet(0x80)
                QTimer.singleShot(100, QApplication.quit)

            elif cmd == 0x00:  # PING / READY CHECK
                self.send_packet(0x80, b"READY")


            elif cmd == 0x34:  # CLOSE TCP CONNECTION ONLY
                if self.client:
                    self.client.disconnectFromHost()
                    self.client = None
                    self.buffer = b""
                self.send_packet(0x80)

            elif cmd == 0x16:  # SAVE IMAGE TO GIVEN PATH
                if self.image is None:
                    self.send_packet(0x81, b"No image loaded")
                    return

                save_path = payload.decode().strip()
                log(f"[CMD] Save image to: {save_path}")

                try:
                    import os
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)

                    # ---- render image WITH ROIs (important) ----
                    img = self.image.copy()

                    for r in self.rois:
                        if r.type == "rectangle":
                            x1, y1, x2, y2 = r.rect()
                            cv2.rectangle(img, (x1, y1), (x2, y2), r.color, 2)
                        elif r.type == "line":
                            cv2.line(img, tuple(r.p1), tuple(r.p2), r.color, 2)

                    cv2.imwrite(save_path, img)

                    self.send_packet(0x80)
                    log("[CMD] Image saved successfully")

                except Exception as e:
                    traceback.print_exc()
                    self.send_packet(0x81, str(e).encode())


            elif cmd == 0x15:  # SET ROI COLOR (Python color palette)
                if self.selected is None:
                    self.send_packet(0x81, b"No ROI selected")
                    return

                # Open Qt color dialog (blocks only Python UI thread)
                color = QColorDialog.getColor(
                    initial=QColor(0, 255, 0),
                    parent=self,
                    title="Select ROI Color"
                )

                if not color.isValid():
                    self.send_packet(0x80)   # user cancelled → OK
                    return

                # Apply color to selected ROI
                r = self.rois[self.selected]
                r.color = (color.blue(), color.green(), color.red())  # BGR for OpenCV


                self.redraw()
                self.send_packet(0x80)

        except Exception as e:
            traceback.print_exc()
            self.send_packet(0x81, str(e).encode())

    # ===== IMAGE HELPERS =====
    # ===== IMAGE HELPERS =====
    def screen_to_image(self, pos):
        # FIX IS HERE: Do not add scroll offsets.
        # Since self.canvas (QLabel) is resized to fit the zoomed image,
        # event.pos() is already the correct pixel on the image surface.
        return [
            int(pos.x() / self.zoom),
            int(pos.y() / self.zoom)
        ]


    def fit(self):
        if self.image is None: return
        h,w = self.image.shape[:2]
        vw,vh = self.scroll.viewport().width(), self.scroll.viewport().height()
        self.zoom = min(vw/w, vh/h)
        self.redraw()

    def _force_foreground(self):
        self.setWindowState(
            self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive
        )
        self.raise_()
        self.activateWindow()

    def redraw(self):
        if self.image is None: return
        img = cv2.resize(self.image, None, fx=self.zoom, fy=self.zoom)

        # Draw all existing ROIs
        for i,r in enumerate(self.rois):
            x1,y1,x2,y2 = r.rect()
            p1,p2 = (int(x1*self.zoom), int(y1*self.zoom)), (int(x2*self.zoom), int(y2*self.zoom))
            c = r.color
            if r.type=="rectangle": cv2.rectangle(img,p1,p2,c,2)
            elif r.type=="line": cv2.line(img,p1,p2,c,2)

            # Draw handles for selected ROI
            if i == self.selected:
                if r.type == "rectangle":
                    for h in r.handles().values():
                        hx,hy = int(h[0]*self.zoom), int(h[1]*self.zoom)
                        cv2.rectangle(
                            img,
                            (hx-HANDLE_SIZE,hy-HANDLE_SIZE),
                            (hx+HANDLE_SIZE,hy+HANDLE_SIZE),
                            (255,0,0), -1
                        )
                elif r.type == "line":
                    for pt in (r.p1, r.p2):
                        hx,hy = int(pt[0]*self.zoom), int(pt[1]*self.zoom)
                        cv2.rectangle(img,(hx-HANDLE_SIZE,hy-HANDLE_SIZE),(hx+HANDLE_SIZE,hy+HANDLE_SIZE),(255,0,0),-1)
                    # Draw center handle
                    cx,cy = int((r.p1[0]+r.p2[0])*self.zoom/2), int((r.p1[1]+r.p2[1])*self.zoom/2)
                    cv2.rectangle(img,(cx-HANDLE_SIZE,cy-HANDLE_SIZE),(cx+HANDLE_SIZE,cy+HANDLE_SIZE),(0,0,255),-1)

        # ==== LIVE PREVIEW ====
        # 1️⃣ New ROI being drawn
        if self.mode=="draw" and self.canvas.drawing and self.canvas.start_pt and self.canvas.temp_pt:
            p1,p2 = (int(self.canvas.start_pt[0]*self.zoom), int(self.canvas.start_pt[1]*self.zoom)), \
                    (int(self.canvas.temp_pt[0]*self.zoom), int(self.canvas.temp_pt[1]*self.zoom))
            if self.draw_type=="rectangle": cv2.rectangle(img,p1,p2,(0,255,255),1)
            elif self.draw_type=="line": cv2.line(img,p1,p2,(0,255,255),1)

        # 2️⃣ Active resizing/moving existing ROI
        if self.canvas.resizing and self.selected is not None:
            r = self.rois[self.selected]
            if r.type=="rectangle":
                x1, y1, x2, y2 = r.rect()
                p1, p2 = (int(x1*self.zoom), int(y1*self.zoom)), (int(x2*self.zoom), int(y2*self.zoom))
                cv2.rectangle(img, p1, p2, (0,255,255), 1)
            elif r.type=="line":
                p1, p2 = (int(r.p1[0]*self.zoom), int(r.p1[1]*self.zoom)), \
                        (int(r.p2[0]*self.zoom), int(r.p2[1]*self.zoom))
                cv2.line(img, p1, p2, (0,255,255), 1)  # <<< Live line while dragging

        q = QImage(img.data, img.shape[1], img.shape[0], img.strides[0], QImage.Format_BGR888)
        self.canvas.setPixmap(QPixmap.fromImage(q))
        self.canvas.resize(q.size())


    # ===== STREAM =====
    def init_stream_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.stream_measurement)

    def stream_measurement(self):
        if not self.stream_enabled: return
        data = json.dumps(self.get_measurements()).encode()
        log(f"[STREAM] {data}")
        self.send_packet(0x82, data)

    
    # ===== MEASUREMENTS =====
    def get_measurements(self):
        if self.selected is None: 
            return {}
        
        r = self.rois[self.selected]
        if r.type == "rectangle":
            x1, y1, x2, y2 = r.rect()
            width = x2 - x1
            height = y2 - y1
            area = width * height
            return {"type": "rectangle", "width_px": width, "height_px": height, "area_px": area}
        elif r.type == "line":
            x1, y1 = r.p1
            x2, y2 = r.p2
            length = math.hypot(x2 - x1, y2 - y1)
            return {"type": "line", "length_px": length}
        else:
            return {}


# ================= RUN =================
if __name__ == "__main__":
    #QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    #QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    w = ImagingSystem()
    #w.show()
    sys.exit(app.exec_())

