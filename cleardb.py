import sqlite3

def clear_database():
    conn = sqlite3.connect('vehicle_data.db')
    cursor = conn.cursor()

    # Delete all rows from tables
    cursor.executescript("""
        DELETE FROM vehicles;
        DELETE FROM speed_results;
        DELETE FROM config;
    """)

    conn.commit()
    conn.close()
    print("Database cleared successfully.")

clear_database()
