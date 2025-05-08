# ของจริงรันตัวนี้ 

import json
import pandas as pd
import joblib
import pyodbc
import time
from datetime import datetime, timedelta
from azure.eventhub import EventHubConsumerClient
import threading

# โหลดโมเดล
model = joblib.load("xgboost_posture_model.pkl")
le = joblib.load("label_encoder.pkl")
columns = ['L1', 'L3', 'L4', 'L2', 'SL', 'SR', 'WL', 'WR']

# Connection
# ตัวดึงข้อมูลจาก Azure IoT Hub
connection_str = "Endpoint=sb://ihsuprodsgres009dednamespace.servicebus.windows.net/;SharedAccessKeyName=iothubowner;SharedAccessKey=3YhCwP8RZBp19lkiLQ1l8TYxrKE/i8LHwAIoTIYhXRY=;EntityPath=iothub-ehub-esp32chair-57141806-440a13ea34"
eventhub_name = "iothub-ehub-esp32chair-57141806-440a13ea34"  # ดูจาก Azure Portal

sql_conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=postureserver42.database.windows.net;"
    "DATABASE=posturedb;"
    "UID=adminuser42;"
    "PWD=Fuckingpassword!;"
)

# ตัวแปรสถานะ
last_received_time = datetime.utcnow()
last_offline_insert_time = None
offline_interval = timedelta(seconds=15)
lock = threading.Lock()


def insert_to_db(timestamp, sensor_data, predicted_label, confidence_val):
    try:
        input_json = json.dumps(sensor_data)
        conn = pyodbc.connect(sql_conn_str)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO posture_predictions (timestamp, input_json, predicted_posture, confidence)
            VALUES (?, ?, ?, ?)
        """, timestamp, input_json, predicted_label, confidence_val)
        conn.commit()
        conn.close()
        print(f"บันทึก: {predicted_label} เวลา: {timestamp} ความถูกต้อง: {confidence_val}")
    except Exception as e:
        print(f"บันทึกผิดพลาด: {e}")


def on_event(partition_context, event):
    global last_received_time

    try:
        payload = json.loads(event.body_as_str())
        sensor_data = payload.get("sensor")

        if not sensor_data or len(sensor_data) != 8:
            print("ข้อมูลไม่ถูกต้อง:", sensor_data)
            return

        # อัปเดตเวลาล่าสุด
        with lock:
            last_received_time = datetime.utcnow()

        df = pd.DataFrame([sensor_data], columns=columns)
        prediction = model.predict(df)[0]
        predicted_label = le.inverse_transform([prediction])[0]
        confidence = max(model.predict_proba(df)[0])
        confidence_val = round(float(confidence), 2)

        insert_to_db(datetime.utcnow(), sensor_data, predicted_label, confidence_val)

    except Exception as e:
        print(f"ผิดพลาดใน on_event: {e}")

    partition_context.update_checkpoint(event)


def offline_checker():
    global last_received_time, last_offline_insert_time

    while True:
        now = datetime.utcnow()
        with lock:
            time_since_last = now - last_received_time
            if time_since_last > offline_interval:
                if not last_offline_insert_time or (now - last_offline_insert_time >= offline_interval):
                    insert_to_db(
                        now,
                        [0, 0, 0, 0, 0, 0, 0, 0],
                        "device_offline",
                        1.0
                    )
                    last_offline_insert_time = now
        time.sleep(5)


# เริ่ม thread สำหรับตรวจ offline
threading.Thread(target=offline_checker, daemon=True).start()

# เริ่มรอข้อมูลจาก ESP32
client = EventHubConsumerClient.from_connection_string(
    conn_str=connection_str,
    consumer_group="$Default",
    eventhub_name=eventhub_name
)

print("เริ่มรอฟังข้อมูลจาก ESP32...")
with client:
    client.receive(
        on_event=on_event,
        starting_position="-1"
    )
