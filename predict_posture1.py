# ของจริงรันตัวนี้ 

import json
import pandas as pd
import joblib
import time
from datetime import datetime, timedelta
from azure.eventhub import EventHubConsumerClient
import threading
import pymysql
import pytz

# ✅ กำหนด timezone เป็นเวลาประเทศไทย
tz = pytz.timezone('Asia/Bangkok')

# โหลดโมเดล
model = joblib.load("xgboost_posture_model.pkl")
le = joblib.load("label_encoder.pkl")
columns = ['L1', 'L3', 'L4', 'L2', 'SL', 'SR', 'WL', 'WR']

# Azure Event Hub
connection_str = "Endpoint=sb://ihsuprodsgres009dednamespace.servicebus.windows.net/;SharedAccessKeyName=iothubowner;SharedAccessKey=3YhCwP8RZBp19lkiLQ1l8TYxrKE/i8LHwAIoTIYhXRY=;EntityPath=iothub-ehub-esp32chair-57141806-440a13ea34"
eventhub_name = "iothub-ehub-esp32chair-57141806-440a13ea34"

# MySQL (Hostinger)
mysql_conn = pymysql.connect(
    host='healthchairproject.online',
    user='u497837279_Posturedb42',
    password='Posturedb42',
    database='u497837279_posturedb',
    port=3306,
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)

# สถานะ
last_received_time = datetime.now(tz)
last_offline_insert_time = None
offline_interval = timedelta(seconds=15)
lock = threading.Lock()


def insert_to_db(timestamp, sensor_data, predicted_label, confidence_val, user_id):
    try:
        mysql_conn.ping(reconnect=True)
        input_json = json.dumps(sensor_data)
        with mysql_conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO posture_data (user_id, timestamp, input_json, predicted_posture, confidence)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, timestamp, input_json, predicted_label, confidence_val))
        mysql_conn.commit()
        print(f"✅ บันทึกลง MySQL: {predicted_label} (user_id={user_id}) เวลา: {timestamp}")
    except Exception as e:
        print(f"❌ บันทึกผิดพลาด MySQL: {e}")


def get_current_user_id():
    try:
        with open("user_session.json", "r") as f:
            data = json.load(f)
            return data.get("user_id")
    except:
        return None


def on_event(partition_context, event):
    global last_received_time

    try:
        user_id = get_current_user_id()
        if not user_id:
            print("⚠️ ยังไม่มี user_id → รอผู้ใช้กดเริ่มนั่งจากแอป")
            return

        payload = json.loads(event.body_as_str())
        sensor_data = payload.get("sensor")

        if not sensor_data or len(sensor_data) != 8:
            print("⚠️ ข้อมูลไม่ถูกต้อง:", sensor_data)
            return

        # ✅ ใช้เวลาไทย
        with lock:
            last_received_time = datetime.now(tz)

        df = pd.DataFrame([sensor_data], columns=columns)
        prediction = model.predict(df)[0]
        predicted_label = le.inverse_transform([prediction])[0]
        confidence = max(model.predict_proba(df)[0])
        confidence_val = round(float(confidence), 2)

        insert_to_db(datetime.now(tz), sensor_data, predicted_label, confidence_val, user_id)

    except Exception as e:
        print(f"❌ ผิดพลาดใน on_event: {e}")

    partition_context.update_checkpoint(event)


def offline_checker():
    global last_received_time, last_offline_insert_time

    while True:
        now = datetime.now(tz)
        with lock:
            time_since_last = now - last_received_time
            if time_since_last > offline_interval:
                if not last_offline_insert_time or (now - last_offline_insert_time >= offline_interval):
                    user_id = get_current_user_id()
                    if user_id:
                        insert_to_db(
                            now,
                            [0, 0, 0, 0, 0, 0, 0, 0],
                            "device_offline",
                            1.0,
                            user_id
                        )
                        print(f"📴 บันทึก device_offline สำหรับ user_id={user_id}")
                        last_offline_insert_time = now
                    else:
                        print("⚠️ ยังไม่มี user_id → ข้ามการบันทึก device_offline")
        time.sleep(5)


# เริ่มตรวจ offline
threading.Thread(target=offline_checker, daemon=True).start()

# เริ่มฟังข้อมูลจาก ESP32
client = EventHubConsumerClient.from_connection_string(
    conn_str=connection_str,
    consumer_group="$Default",
    eventhub_name=eventhub_name
)

print("📡 เริ่มรอฟังข้อมูลจาก ESP32...")
with client:
    client.receive(
        on_event=on_event,
        starting_position="-1"
    )
