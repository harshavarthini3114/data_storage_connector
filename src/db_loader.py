import sqlite3
from src.logger import get_production_logger


def initialize_data_warehouse():
    logger = get_production_logger()
    connection = sqlite3.connect("data/warehouse.db")
    

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS customer_profiles (
                customer_id INTEGER PRIMARY KEY,
                age INTEGER,
                income REAL
            )
        """)

        customer_data = [
            (1001, 24, 42000.0),
            (1002, 31, 68000.0),
            (1003, 27, 51000.0),
            (1004, 45, 92000.0),
            (1005, 38, 75000.0),
            (1006, 52, 110000.0),
            (1007, 29, 47000.0)
        ]

        connection.executemany("""
            INSERT INTO customer_profiles
            (customer_id, age, income)
            VALUES (?, ?, ?)
        """, customer_data)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS customer_behavior (
                customer_id INTEGER,
                churn_risk REAL
            )
        """)

        customer_behavior_data = [
            (1001, 0.12),
            (1002, 0.68),
            (1003, 0.35),
            (1004, 0.08),
            (1005, 0.57),
            (1006, 0.22),
            (1007, 0.81)
        ]

        connection.executemany("""
            INSERT INTO customer_behavior
            (customer_id, churn_risk)
            VALUES (?, ?)
        """, customer_behavior_data)

        connection.commit()

        logger.info("Database tables generated and mock profiles registered safely.")

    except sqlite3.Error as error:
        connection.rollback()
        logger.critical(f"Database error: {error}")

    finally:
        connection.close()


def stream_joined_records(chunk_size=2):
    connection = sqlite3.connect("data/warehouse.db")
    logger = get_production_logger()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT
                customer_profiles.customer_id,
                customer_profiles.age,
                customer_profiles.income,
                customer_behavior.churn_risk
            FROM customer_profiles
            INNER JOIN customer_behavior
            ON customer_profiles.customer_id = customer_behavior.customer_id
        """)

        logger.info("Joined record streaming initialized.")

        while True:
            rows = cursor.fetchmany(chunk_size)

            if not rows:
                break

            for row in rows:
                yield row

    finally:
        connection.close()