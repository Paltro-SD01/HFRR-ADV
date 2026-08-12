import sys
import os
import re
import time
import datetime
import serial
import json
import asyncio
import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from threading import Thread

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------
# Global System Configurations & Registers
# ------------------------------------------------------------------
UNO_PORT, DUE_PORT, HUMID_PORT = 'COM4', 'COM5', 'COM3'
UNO_BAUD, DUE_BAUD, HUMID_BAUD = 250000, 250000, 115200

TARGET_HEATER_TEMP = 60.0  
TARGET_HUMIDITY = 53.0     
HEATER_TOLERANCE = 1.5     
TARGET_STROKE = 1.0        

MIN_AMPLITUDE_CMD = 0
MAX_AMPLITUDE_CMD = 1000   
STARTUP_CMD = 400.0        
MAX_STEP_CHANGE = 150.0    

Kp, Ki, Kd = 2000.0, 1300.0, 140.0    
EMA_ALPHA = 0.2            

CONNECTED_CLIENTS = set()
SYSTEM_STATE = {
    "running": True,
    "system_active": False,
    "data_only_mode": False,
    "auto_sequence_step": 0,
    "target_heater_temp": TARGET_HEATER_TEMP,
    "target_humidity": TARGET_HUMIDITY,
    "target_stroke": TARGET_STROKE,
    "custom_log_filename": "",
    "tare_min": 0.0, "tare_max": 0.0, "tare_p2p": 0.0, "tare_min_stroke_val": 0.0,
    "trigger_tare_capture": False, "trigger_tare_min_stroke": False,
    "cal_matrix": [(0.1935, 0.1), (0.3340, 0.2), (0.4578, 0.3), (0.5828, 0.4), (0.7062, 0.5)]
}

def format_elapsed_time(elapsed_seconds):
    mins = int(elapsed_seconds // 60)
    secs = int(elapsed_seconds % 60)
    mils = int((elapsed_seconds % 1) * 1000)
    return f"{mins:02d}:{secs:02d}:{mils:03d}"

def parse_due_data(status_string, cur_t, cur_tgt, cur_amb, cur_vpp):
    try:
        t_m = re.search(r"Temp:\s*([-\d\.]+)", status_string)
        tgt_m = re.search(r"Target:\s*([-\d\.]+)", status_string)
        a_m = re.search(r"AmbTemp:\s*([-\d\.]+)", status_string)
        v_m = re.search(r"Vpp:\s*(\d+)", status_string)
        return (t_m.group(1) if t_m else cur_t, tgt_m.group(1) if tgt_m else cur_tgt,
                a_m.group(1) if a_m else cur_amb, v_m.group(1) if v_m else cur_vpp)
    except: 
        return cur_t, cur_tgt, cur_amb, cur_vpp

def evaluate_piecewise_calibration(raw_value):
    extended_matrix = [(0.0, 0.0)] + list(SYSTEM_STATE["cal_matrix"])
    if raw_value <= extended_matrix[0][0]:
        x0, y0 = extended_matrix[0]; x1, y1 = extended_matrix[1]
        val = y0 + (raw_value - x0) * (y1 - y0) / (x1 - x0) if x1 != x0 else y0
    elif raw_value >= extended_matrix[-1][0]:
        x0, y0 = extended_matrix[-2]; x1, y1 = extended_matrix[-1]
        val = y0 + (raw_value - x0) * (y1 - y0) / (x1 - x0) if x1 != x0 else y1
    else:
        val = raw_value
        for i in range(len(extended_matrix) - 1):
            x0, y0 = extended_matrix[i]; x1, y1 = extended_matrix[i+1]
            if x0 <= raw_value <= x1:
                val = y0 + (raw_value - x0) * (y1 - y0) / (x1 - x0) if x0 != x1 else y0
                break
    
    if val <= 0.0: offset = 0.0
    elif val < 0.1: offset = 0.05 * (val / 0.1)
    elif val <= 0.3: offset = 0.05
    elif val < 0.4: offset = 0.05 * ((0.4 - val) / 0.1)
    else: offset = 0.0
    return val + offset

def dispatch_log_to_frontend(msg):
    broadcast_packet("log", msg)

def broadcast_packet(event_name, payload_data):
    if CONNECTED_CLIENTS:
        out_msg = json.dumps({"event": event_name, "data": payload_data})
        asyncio.run_coroutine_threadsafe(async_broadcast(out_msg), background_async_loop)

async def async_broadcast(msg_str):
    for client in list(CONNECTED_CLIENTS):
        try:
            await client.send_text(msg_str)
        except:
            CONNECTED_CLIENTS.remove(client)

# ------------------------------------------------------------------
# High-Frequency Hardware Worker Processing Pipeline
# ------------------------------------------------------------------
def hardware_pipeline_worker():
    global SYSTEM_STATE
    try:
        uno = serial.Serial(UNO_PORT, UNO_BAUD, timeout=0.05)
        due = serial.Serial(DUE_PORT, DUE_BAUD, timeout=0.05)
        humid = serial.Serial(HUMID_PORT, HUMID_BAUD, timeout=0.05)
        time.sleep(2)
        dispatch_log_to_frontend("All instrumentation ports linked securely on target lines.")
    except Exception as e:
        dispatch_log_to_frontend(f"PORT ALLOCATION TIMEOUT EXCEPTION: {e}")
        return

    data_start_time = time.time()
    d_temp, d_target, d_amb, d_vpp = "0.00", "0.0", "0.00", "0"
    h_state, h_rh, h_set = "OFF", "0.0", "0.0"
    ema_f_force, ema_cof = None, None

    while SYSTEM_STATE["running"]:
        while uno.in_waiting > 0:
            try:
                line = uno.readline().decode('utf-8', errors='ignore').strip()
                parts = [p.strip() for p in line.split(';') if p.strip()]
                if len(parts) >= 6:
                    raw_min, raw_max, raw_p2p = float(parts[0]), float(parts[1]), float(parts[2])

                    if SYSTEM_STATE["trigger_tare_capture"]:
                        SYSTEM_STATE["tare_min"] = raw_min
                        SYSTEM_STATE["tare_max"] = raw_max
                        SYSTEM_STATE["tare_p2p"] = raw_p2p
                        SYSTEM_STATE["trigger_tare_capture"] = False
                        dispatch_log_to_frontend("Matrix baseline references tared successfully.")

                    tared_min = raw_min - SYSTEM_STATE["tare_min"]
                    tared_max = raw_max - SYSTEM_STATE["tare_max"]
                    calibrated_p2p = evaluate_piecewise_calibration(raw_p2p - SYSTEM_STATE["tare_p2p"])
                    stroke_val = abs(calibrated_p2p)

                    ts = format_elapsed_time(time.time() - data_start_time)
                    raw_f_force = float(parts[4]) if parts[4] else 0.0
                    raw_cof = float(parts[5]) if parts[5] else 0.0
                    
                    ema_f_force = raw_f_force if ema_f_force is None else EMA_ALPHA * raw_f_force + (1.0 - EMA_ALPHA) * ema_f_force
                    ema_cof = raw_cof if ema_cof is None else EMA_ALPHA * raw_cof + (1.0 - EMA_ALPHA) * ema_cof

                    payload = {
                        "Timestamp": ts, "LVDT_Min": f"{tared_min:.4f}", "LVDT_Max": f"{tared_max:.4f}",
                        "LVDT_P2P": f"{calibrated_p2p:.4f}", "ch1_Piezo_Raw": parts[3], "Friction_Force_N": f"{ema_f_force:.4f}",
                        "Cof": f"{ema_cof:.4f}", "Stemp_Temp": d_temp, "Stemp_Target": d_target, "AmbTemp": d_amb,
                        "DUE_Vpp": d_vpp, "VC_Cmd": "0", "VC_Err": "0.0000", "HUMID_Status": h_state,
                        "HUMID_RH": h_rh, "HUMID_Set": h_set, "LVDT_Stroke": f"{stroke_val:.4f}", "LVDT_Min_Stroke": "0.00"
                    }
                    broadcast_packet("telemetry", payload)
            except Exception:
                pass

        while due.in_waiting > 0:
            try:
                line = due.readline().decode('utf-8', errors='ignore').strip()
                d_temp, d_target, d_amb, d_vpp = parse_due_data(line, d_temp, d_target, d_amb, d_vpp)
            except Exception:
                pass

        while humid.in_waiting > 0:
            try:
                line = humid.readline().decode('utf-8', errors='ignore').strip()
                if "RH:" in line: h_rh = line.split("RH:")[1].split("%")[0].strip()
                if "Set:" in line: h_set = line.split("Set:")[1].strip()
                h_state = "RUNNING" if "ON" in line else "IDLE"
            except Exception:
                pass

        time.sleep(0.005)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    CONNECTED_CLIENTS.add(websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            cmd = json.loads(msg)
            action = cmd.get("action")
            
            if action == "tare":
                SYSTEM_STATE["trigger_tare_capture"] = True
                
            elif action == "set_heater":
                val = float(cmd.get("value", TARGET_HEATER_TEMP))
                SYSTEM_STATE["target_heater_temp"] = val
                dispatch_log_to_frontend(f"Target core temperature variable updated: {val} °C")
                
            elif action == "stop":
                SYSTEM_STATE["system_active"] = False
                dispatch_log_to_frontend("CRITICAL ABORT EVENT INITIATED.")
                
            # === ADD THE METADATA INITIALIZATION ENGINE HERE ===
            elif action == "initialize_metadata":
                # Extracted data from client configuration page
                SYSTEM_STATE["custom_log_filename"] = cmd.get("file_name", "default_log")
                
                # Capture the rest of the form parameters from the frontend payload
                SYSTEM_STATE["batch_ref_no"] = cmd.get("batch_ref", "")
                SYSTEM_STATE["tested_by"] = cmd.get("tested_by", "")
                SYSTEM_STATE["fluid_description"] = cmd.get("fluid_desc", "")
                SYSTEM_STATE["remarks"] = cmd.get("remarks", "")
                SYSTEM_STATE["operator_id"] = cmd.get("operator_id", "0000")
                
                op_id = cmd.get("operator_id", "0000")
                dispatch_log_to_frontend(f"Metadata Registered. File: {SYSTEM_STATE['custom_log_filename']} | Op: {op_id}")
                
    except Exception:
        pass
    finally:
        CONNECTED_CLIENTS.remove(websocket)

if __name__ == "__main__":
    background_async_loop = asyncio.get_event_loop()
    t = Thread(target=hardware_pipeline_worker, daemon=True)
    t.start()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")