import cv2
import easyocr
import numpy as np
from ultralytics import YOLO
import os
import sys
from datetime import datetime, timedelta
import sqlite3
import re

sys.path.append('/home/haris/PROJECT LABORATORY/thuus/sort')  # Ensure Python can find sort module
from sort import Sort

# Initialize EasyOCR reader
ocr_reader = easyocr.Reader(['en'])

# Initialize SORT tracker
mot_tracker = Sort()

# Load YOLO models
vehicle_model = YOLO('yolov8x.pt')
license_plate_model = YOLO('best.pt')

# Vehicle classes
vehicle_classes = [2, 3, 5, 7]
class_names = {2: 'car', 3: 'motorcycle', 5: 'bus', 7: 'truck'}

# Database setup
DATABASE_FILE = 'vehicle_data.db'

def create_database():
    print("Entering create_database()")
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        print("Database connection successful")
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vehicles (
                license_plate TEXT PRIMARY KEY,
                vehicle_type TEXT,
                entry_time TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS speed_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_plate TEXT,
                vehicle_type TEXT,
                entry_time TEXT,
                exit_time TEXT,
                speed_kmh REAL,
                FOREIGN KEY (license_plate) REFERENCES vehicles(license_plate)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config (
                setting TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        conn.commit()
        print("Database commit successful")
        conn.close()
        print("Database closed")
        print("Tables created (or checked)")
    except Exception as e:
        print(f"Error creating database: {e}")

def get_config_from_db():
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT setting, value FROM config")
    rows = cursor.fetchall()
    conn.close()

    config = {}
    for row in rows:
        try:
            config[row[0]] = int(row[1])  # Or float, or other type conversion
        except ValueError:
            config[row[0]] = row[1]  # If conversion fails, keep as string

    return config

def process_file(input_path, point, vehicles_at_point=None): # vehicles_at_point added
    config = get_config_from_db()
    distance = config.get('distance', 1000)  # Get distance from config, default 1000
    time_diff = config.get('time_difference', 10) # Get time_difference from config, default 10

    if vehicles_at_point is None: # Initialize only if it's None
        vehicles_at_point = {}

    if point == 'B':
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT license_plate, vehicle_type, entry_time FROM vehicles")
        rows = cursor.fetchall()
        conn.close()
        for row in rows:
            vehicles_at_point[row[0]] = {"vehicle_type": row[1], "entry_time": datetime.strptime(row[2], "%Y-%m-%d %H:%M:%S")}

    if input_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
        frame = cv2.imread(input_path)
        if frame is None:
            print(f"Error: Unable to load image at {input_path}")
            return
        print(f"Image shape: {frame.shape}") # Check if the image is loaded and print its shape
        process_frame(frame, point, vehicles_at_point, distance, time_diff)
    elif input_path.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            print(f"Error: Unable to open video at {input_path}")
            return
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            print(f"Frame shape: {frame.shape}") # Check if the frame is loaded and print its shape
            process_frame(frame, point, vehicles_at_point, distance, time_diff)
        cap.release()
    else:
        print("Error: Unsupported file format. Please provide an image or video.")

def write_to_db(vehicle_type, license_plate_text, entry_time, exit_time, speed_kmh):
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO speed_results (license_plate, vehicle_type, entry_time, exit_time, speed_kmh) VALUES (?, ?, ?, ?, ?)",
                       (license_plate_text, vehicle_type, entry_time.strftime("%Y-%m-%d %H:%M:%S"), exit_time.strftime("%Y-%m-%d %H:%M:%S"), speed_kmh))
        conn.commit()
        conn.close()
        print(f"Data written to speed_results: {license_plate_text}, {speed_kmh}") # Check if data is written
    except Exception as e:
        print(f"Database Error in write_to_db: {e}")

def clean_license_plate(text):
    if not isinstance(text, str):
        return ""
    text = text.strip().replace(" ", "").replace("-", "").upper()
    text = re.sub(r'[^A-Z0-9]', '', text)
    return text

def process_frame(frame, point, vehicles_at_point, distance, time_diff): # vehicles_at_point added
    detections = vehicle_model(frame)[0]
    detections_ = []
    for detection in detections.boxes.data.tolist():
        x1, y1, x2, y2, score, class_id = detection
        if int(class_id) in vehicle_classes and score >= 0.1:
            detections_.append([x1, y1, x2, y2, score, int(class_id)])

    tracked_vehicles = mot_tracker.update(np.asarray([d[:5] for d in detections_]))

    license_plates = license_plate_model(frame)[0]
    for license_plate in license_plates.boxes.data.tolist():
        x1, y1, x2, y2, score, class_id = license_plate
        if score >= 0.5:
            for i, vehicle in enumerate(tracked_vehicles):
                vehicle_x1, vehicle_y1, vehicle_x2, vehicle_y2, car_id = vehicle
                if (x1 >= vehicle_x1 and x2 <= vehicle_x2 and
                        y1 >= vehicle_y1 and y2 <= vehicle_y2):
                    vehicle_class_id = detections_[i][5]
                    if vehicle_class_id in vehicle_classes:
                        license_plate_crop = frame[int(y1):int(y2), int(x1):int(x2)]

                        # Image Cropping Check
                        print(f"Shape of license plate crop: {license_plate_crop.shape}")

                        # Visualize Cropped Image
                        if point == 'A':
                            cv2.imwrite("license_plate_crop_A.jpg", license_plate_crop)
                        elif point == 'B':
                            cv2.imwrite("license_plate_crop_B.jpg", license_plate_crop)

                        ocr_results = ocr_reader.readtext(license_plate_crop)

                        # Raw OCR Results (CRUCIAL)
                        print(f"Raw OCR results at Point {point}: {ocr_results}")

                        license_plate_text = ""
                        for res in ocr_results:
                            if len(res) > 1:
                                license_plate_text += res[1] + " "
                        license_plate_text = license_plate_text.strip()

                       # ... (Previous code in utils.py)

                        # Input to clean_license_plate
                        print(f"Input to clean_license_plate (Point {point}): {license_plate_text}")
                        license_plate_text = clean_license_plate(license_plate_text)
                        print(f"Cleaned license plate at Point {point}): {license_plate_text}")

                        vehicle_type = class_names.get(vehicle_class_id, 'unknown')

                        if point == "A":
                            entry_time = datetime.now()
                            conn = sqlite3.connect(DATABASE_FILE)
                            cursor = conn.cursor()
                            cursor.execute("INSERT OR REPLACE INTO vehicles (license_plate, vehicle_type, entry_time) VALUES (?, ?, ?)",
                                           (license_plate_text, vehicle_type, entry_time.strftime("%Y-%m-%d %H:%M:%S")))
                            conn.commit()
                            conn.close()
                            print(f"Vehicle data stored at Point A: {license_plate_text}, {vehicle_type}, {entry_time}") # Check if data is stored

                        elif point == "B":
                            print(f"vehicles_at_point: {vehicles_at_point}")  # Print the whole dictionary
                            if license_plate_text in vehicles_at_point:
                                current_time = datetime.now()
                                entry_time = vehicles_at_point[license_plate_text]["entry_time"]
                                exit_time = current_time + timedelta(seconds=time_diff)

                                time_difference = time_diff
                                speed = distance / time_difference
                                speed_kmh = speed * 3.6

                                write_to_db(vehicle_type, license_plate_text, entry_time, exit_time, speed_kmh)
                                print(f"Speed calculated and written at Point B: {license_plate_text}, {speed_kmh}") # Check if speed is calculated and written
                            else:
                                print(f"License plate {license_plate_text} not found in vehicles_at_point at Point B. Keys: {vehicles_at_point.keys()}") # Check for license plate mismatch. Print keys for debugging.

                    break  # Exit inner loop after finding a match