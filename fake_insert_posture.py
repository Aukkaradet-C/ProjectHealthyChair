## Fake ข้อมูลเพื่อใช้ทดลองการแสดงผลบนแอป (By GPT)

import random
from datetime import datetime, timedelta
import pyodbc
import json

# SQL Azure Connection
sql_conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=postureserver42.database.windows.net;"
    "DATABASE=posturedb;"
    "UID=adminuser42;"
    "PWD=Fuckingpassword!;"
)

conn = pyodbc.connect(sql_conn_str)
cursor = conn.cursor()

# วันที่ปลอมข้อมูล
start_date = datetime(2025, 4, 21)  # เปลี่ยนตามที่ต้องการ
end_date = datetime(2025, 4, 21)

# ช่วงเวลาทำงาน (online)
online_start = timedelta(hours=12)
online_end = timedelta(hours=18)
interval = timedelta(seconds=10)

# สัดส่วน label (random ต่อวัน)
posture_ranges = {
    "correct_posture": (40, 70),
    "hunch_slight": (20, 40),
    "hunch_deep": (10, 30),
    "no_person": (0, 5),
    "partial_sit": (0, 5),
    "lean_left": (0, 5),
    "lean_right": (0, 5)
}

# สร้าง sensor ตาม label
def generate_sensor_data(label):
    if label == "device_offline":
        return [0] * 8
    elif label == "correct_posture":
        return [random.randint(250, 550) for _ in range(8)]
    elif label == "hunch_slight":
        return [random.randint(250, 500) for _ in range(4)] + [random.randint(0, 50) for _ in range(2)] + [random.randint(300, 650) for _ in range(2)]
    elif label == "hunch_deep":
        return [random.randint(200, 450) for _ in range(4)] + [0, 0, random.randint(400, 600), random.randint(400, 600)]
    elif label == "no_person":
        return [random.randint(0, 30) for _ in range(8)]
    elif label == "partial_sit":
        return [random.choice([random.randint(150, 400), 0]) for _ in range(8)]
    elif label == "lean_left":
        return [random.randint(250, 500), random.randint(250, 500), random.randint(100, 300), random.randint(200, 300), random.randint(0, 100), random.randint(0, 50), random.randint(400, 600), random.randint(100, 300)]
    elif label == "lean_right":
        return [random.randint(250, 500), random.randint(250, 500), random.randint(100, 300), random.randint(200, 300), random.randint(0, 50), random.randint(0, 100), random.randint(100, 300), random.randint(400, 600)]
    return [0] * 8

# เตรียม batch insert
batch_data = []
current_date = start_date
total_inserted = 0

while current_date <= end_date:
    proportions = {}
    remaining = 100
    for key, (low, high) in posture_ranges.items():
        max_val = min(high, remaining)
        min_val = min(low, max_val)
        value = random.randint(min_val, max_val)
        proportions[key] = value
        remaining -= value
    proportions["correct_posture"] += remaining

    label_counts = {k: round(8640 * v / 100) for k, v in proportions.items()}
    label_list = [label for label, count in label_counts.items() for _ in range(count)]
    random.shuffle(label_list)

    time_cursor = datetime.combine(current_date.date(), datetime.min.time())
    end_of_day = time_cursor + timedelta(days=1)

    while time_cursor < end_of_day:
        time_only = time_cursor - time_cursor.replace(hour=0, minute=0, second=0)
        if online_start <= time_only < online_end:
            label = label_list.pop() if label_list else "correct_posture"
            sensor_data = generate_sensor_data(label)
            confidence = round(random.uniform(0.85, 0.99), 2)
        else:
            label = "device_offline"
            sensor_data = [0] * 8
            confidence = 1.0

        batch_data.append((
            time_cursor.isoformat(),
            json.dumps(sensor_data),
            label,
            confidence
        ))

        time_cursor += interval

    print(f"เตรียมข้อมูลวันที่ {current_date.strftime('%Y-%m-%d')} แล้ว")
    current_date += timedelta(days=1)

# แบ่ง batch insert
batch_size = 5000
for i in range(0, len(batch_data), batch_size):
    chunk = batch_data[i:i + batch_size]
    cursor.executemany("""
        INSERT INTO posture_predictions (timestamp, input_json, predicted_posture, confidence)
        VALUES (?, ?, ?, ?)
    """, chunk)
    conn.commit()
    total_inserted += len(chunk)
    print(f"INSERT แล้ว {total_inserted} / {len(batch_data)} แถว")

conn.close()
print("INSERT ข้อมูลทั้งหมดเรียบร้อยแล้ว (batch insert)!")
