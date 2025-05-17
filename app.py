Here's the **cleaned version of your `app.py`** with **all comments and documentation removed**, leaving only the core code:

```python
from flask import Flask, render_template, request, redirect, url_for, send_file
import os
import csv
import pickle
from werkzeug.utils import secure_filename
from utils import process_file, create_database, get_config_from_db
from datetime import datetime, timedelta
import pandas as pd
import sqlite3
import requests

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['CONFIG_FILE'] = 'config.pkl'
app.secret_key = 'your-secret-key-here'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
create_database()

TELEGRAM_BOT_TOKEN = '8027734841:AAE-7CNezqqstzIaqF8M1tVU10tvE5LkFgI'
TELEGRAM_CHAT_ID = '7565137984'

def send_telegram_notification(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("Notification sent successfully!")
        else:
            print(f"Failed to send notification: {response.text}")
    except Exception as e:
        print(f"Error sending Telegram notification: {e}")

@app.route('/', methods=['GET', 'POST'])
def camera1():
    config = get_config_from_db()
    vehicles_on_highway = []
    vehicles_at_point = {}
    try:
        conn = sqlite3.connect('vehicle_data.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM vehicles")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error clearing vehicles table: {str(e)}")
    try:
        conn = sqlite3.connect('vehicle_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT license_plate, vehicle_type, entry_time FROM vehicles")
        rows = cursor.fetchall()
        conn.close()
        for row in rows:
            vehicles_on_highway.append({
                'license_plate': row[0],
                'vehicle_type': row[1],
                'entry_time': datetime.strptime(row[2], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
            })
    except Exception as e:
        print(f"Error loading vehicle data: {str(e)}")
    if request.method == 'POST':
        file = request.files.get('camera_file')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'camera1_' + filename)
            file.save(filepath)
            process_file(filepath, 'A', vehicles_at_point)
        speed_limits = {
            'car': int(request.form.get('car_speed', 60)),
            'motorcycle': int(request.form.get('motorcycle_speed', 80)),
            'bus': int(request.form.get('bus_speed', 50)),
            'truck': int(request.form.get('truck_speed', 55))
        }
        conn = sqlite3.connect('vehicle_data.db')
        cursor = conn.cursor()
        for setting, value in speed_limits.items():
            cursor.execute("INSERT OR REPLACE INTO config (setting, value) VALUES (?, ?)", (f"speed_{setting}", str(value)))
        conn.commit()
        conn.close()
        return redirect(url_for('time_settings'))
    return render_template('camera1.html', speed_limits=config.get('speed_car',60), vehicles_on_highway=vehicles_on_highway)

@app.route('/time-settings', methods=['GET', 'POST'])
def time_settings():
    config = get_config_from_db()
    vehicles_on_highway = []
    try:
        conn = sqlite3.connect('vehicle_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT license_plate, vehicle_type, entry_time FROM vehicles")
        rows = cursor.fetchall()
        conn.close()
        for row in rows:
            vehicles_on_highway.append({
                'license_plate': row[0],
                'vehicle_type': row[1],
                'entry_time': datetime.strptime(row[2], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
            })
    except Exception as e:
        print(f"Error loading vehicle data: {str(e)}")
    if request.method == 'POST':
        distance = int(request.form.get('distance', 1000))
        time_difference = int(request.form.get('time_difference', 10))
        conn = sqlite3.connect('vehicle_data.db')
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO config (setting, value) VALUES (?, ?)", ("distance", str(distance)))
        cursor.execute("INSERT OR REPLACE INTO config (setting, value) VALUES (?, ?)", ("time_difference", str(time_difference)))
        conn.commit()
        conn.close()
        return redirect(url_for('camera2'))
    return render_template('time_settings.html', config=config, vehicles_on_highway=vehicles_on_highway)

@app.route('/camera2', methods=['GET', 'POST'])
def camera2():
    vehicles_at_point = {}
    try:
        conn = sqlite3.connect('vehicle_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT license_plate, vehicle_type, entry_time FROM vehicles")
        rows = cursor.fetchall()
        conn.close()
        for row in rows:
            vehicles_at_point[row[0]] = {"vehicle_type": row[1], "entry_time": datetime.strptime(row[2], "%Y-%m-%d %H:%M:%S")}
    except Exception as e:
        print(f"Error populating vehicles_at_point: {e}")
    if request.method == 'POST':
        file = request.files.get('camera_file')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'camera2_' + filename)
            file.save(filepath)
            process_file(filepath, 'B', vehicles_at_point)
        return redirect(url_for('results'))
    return render_template('camera2.html')

@app.route('/results')
def results():
    results = []
    config = get_config_from_db()
    try:
        conn = sqlite3.connect('vehicle_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM speed_results")
        rows = cursor.fetchall()
        conn.close()
        print(f"Number of rows retrieved from speed_results: {len(rows)}")
        for row in rows:
            print(f"Row from speed_results: {row}")
            try:
                row_dict = {
                    'vehicle_type': row[2],
                    'license_plate_text': row[1],
                    'entry_time': datetime.strptime(row[3], "%Y-%m-%d %H:%M:%S"),
                    'exit_time': datetime.strptime(row[4], "%Y-%m-%d %H:%M:%S"),
                    'speed_kmh': float(row[5])
                }
                row_dict['speed_kmh'] = float(row[5])
                duration = row_dict['exit_time'] - row_dict['entry_time']
                row_dict['duration'] = str(duration)
                vehicle_type = row_dict['vehicle_type'].lower()
                speed_limit = config.get(f"speed_{vehicle_type}", 0)
                row_dict['speed_limit'] = speed_limit
                row_dict['over_speed'] = row_dict['speed_kmh'] > speed_limit
                if row_dict['over_speed']:
                    message = f"""
🚨 SPEEDING ALERT 🚨

License Number: {row_dict['license_plate_text']}
Vehicle Type: {row_dict['vehicle_type']}
Entry Time: {row_dict['entry_time'].strftime('%Y-%m-%d %H:%M:%S')}
Exit Time: {row_dict['exit_time'].strftime('%Y-%m-%d %H:%M:%S')}
Speed: {row_dict['speed_kmh']} km/h
Speed Limit: {speed_limit} km/h

This vehicle has exceeded the speed limit!
"""
                    send_telegram_notification(message)
                results.append(row_dict)
            except Exception as e:
                print(f"Error processing row: {e}")
                continue
    except Exception as e:
        print(f"Error loading speed results: {str(e)}")
    print(f"Results list: {results}")
    return render_template('results.html', results=results)

@app.route('/download-report')
def download_report():
    try:
        conn = sqlite3.connect('vehicle_data.db')
        df = pd.read_sql_query("SELECT * FROM speed_results", conn)
        conn.close()
        excel_file = 'speed_detection_report.xlsx'
        df.to_excel(excel_file, index=False)
        return send_file(excel_file, as_attachment=True)
    except Exception as e:
        print(f"Error generating report: {str(e)}")
        return "Error generating report", 500

@app.route('/reset')
def reset_data():
    try:
        conn = sqlite3.connect('vehicle_data.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM vehicles")
        cursor.execute("DELETE FROM speed_results")
        conn.commit()
        conn.close()
        return redirect(url_for('camera1'))
    except Exception as e:
        print(f"Error clearing data: {e}")
        return "Error clearing data", 500

if __name__ == '__main__':
    app.run(debug=True)
```
