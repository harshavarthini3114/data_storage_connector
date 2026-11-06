import csv
import os
import sqlite3
import urllib.request

from src.logger import get_production_logger


DB_PATH = "data/warehouse.db"
CSV_PATH = "data/telco_churn.csv"
CSV_URL = (
    "https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/"
    "master/data/Telco-Customer-Churn.csv"
)

# Original dataset column order. The joined stream returns columns in this order,
# so downstream code (the ML trainer) does not need to change.
COLUMNS = [
    "customerID", "gender", "SeniorCitizen", "Partner", "Dependents",
    "tenure", "PhoneService", "MultipleLines", "InternetService",
    "OnlineSecurity", "OnlineBackup", "DeviceProtection", "TechSupport",
    "StreamingTV", "StreamingMovies", "Contract", "PaperlessBilling",
    "PaymentMethod", "MonthlyCharges", "TotalCharges", "Churn",
]

PROFILE_TABLE = "customer_profiles"
PROFILE_COLUMNS = [
    "customerID", "gender", "SeniorCitizen", "Partner", "Dependents",
    "tenure", "Contract", "PaperlessBilling", "PaymentMethod",
    "MonthlyCharges", "TotalCharges", "Churn",
]

SERVICE_TABLE = "customer_services"
SERVICE_COLUMNS = [
    "customerID", "PhoneService", "MultipleLines", "InternetService",
    "OnlineSecurity", "OnlineBackup", "DeviceProtection", "TechSupport",
    "StreamingTV", "StreamingMovies",
]

COLUMN_TYPES = {
    "SeniorCitizen": "INTEGER",
    "tenure": "INTEGER",
    "MonthlyCharges": "REAL",
    "TotalCharges": "REAL",
}

# ORDER BY p.rowid keeps the CSV order, so the train/test split stays identical.
JOINED_SELECT = f"""
    SELECT
        p.customerID, p.gender, p.SeniorCitizen, p.Partner, p.Dependents,
        p.tenure, s.PhoneService, s.MultipleLines, s.InternetService,
        s.OnlineSecurity, s.OnlineBackup, s.DeviceProtection, s.TechSupport,
        s.StreamingTV, s.StreamingMovies, p.Contract, p.PaperlessBilling,
        p.PaymentMethod, p.MonthlyCharges, p.TotalCharges, p.Churn
    FROM {PROFILE_TABLE} AS p
    INNER JOIN {SERVICE_TABLE} AS s
        ON p.customerID = s.customerID
    ORDER BY p.rowid
"""


def _create_table_sql(table, columns):
    definitions = []
    for column in columns:
        column_type = COLUMN_TYPES.get(column, "TEXT")
        primary = " PRIMARY KEY" if column == "customerID" else ""
        definitions.append(f"{column} {column_type}{primary}")
    return f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(definitions)})"


def _insert_sql(table, columns):
    placeholders = ", ".join("?" for _ in columns)
    return f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"


def _ensure_csv(logger):
    """Download the CSV only if it is not already on disk."""
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)

    if os.path.exists(CSV_PATH):
        logger.info("CSV already present, skipping download.")
        return

    logger.info("Downloading Telco Customer Churn dataset...")
    urllib.request.urlretrieve(CSV_URL, CSV_PATH)
    logger.info("Dataset downloaded successfully.")


def _parse_row(raw):
    """Convert one CSV row (dict of strings) into typed values keyed by column name."""
    parsed = {}
    for column in COLUMNS:
        value = raw[column].strip()

        if column == "TotalCharges" and value == "":
            # Blank for tenure-0 customers. Stored as 0.0 on purpose.
            parsed[column] = 0.0
        elif column in COLUMN_TYPES:
            converter = float if COLUMN_TYPES[column] == "REAL" else int
            parsed[column] = converter(value)
        else:
            parsed[column] = value

    return parsed


def initialize_data_warehouse():
    """Load the Telco CSV into two related tables. Safe to run repeatedly."""
    logger = get_production_logger()
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    connection = sqlite3.connect(DB_PATH)

    try:
        _ensure_csv(logger)

        with open(CSV_PATH, "r", encoding="utf-8", newline="") as f:
            rows = [_parse_row(raw) for raw in csv.DictReader(f)]

        profile_rows = [tuple(r[c] for c in PROFILE_COLUMNS) for r in rows]
        service_rows = [tuple(r[c] for c in SERVICE_COLUMNS) for r in rows]

        connection.execute(_create_table_sql(PROFILE_TABLE, PROFILE_COLUMNS))
        connection.execute(_create_table_sql(SERVICE_TABLE, SERVICE_COLUMNS))

        # One transaction: both tables are fully reloaded, or neither is.
        # The context manager commits on success and rolls back on any exception.
        with connection:
            connection.execute(f"DELETE FROM {PROFILE_TABLE}")
            connection.execute(f"DELETE FROM {SERVICE_TABLE}")
            connection.executemany(_insert_sql(PROFILE_TABLE, PROFILE_COLUMNS), profile_rows)
            connection.executemany(_insert_sql(SERVICE_TABLE, SERVICE_COLUMNS), service_rows)

        logger.info(f"Loaded {len(rows)} customers into {PROFILE_TABLE} and {SERVICE_TABLE}.")

    except Exception as error:
        logger.critical(f"Warehouse load failed: {error}")
        raise

    finally:
        connection.close()


def stream_joined_records(chunk_size=32):
    """Yield joined customer rows, fetched in batches of chunk_size, one row at a time."""
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")

    logger = get_production_logger()
    connection = sqlite3.connect(DB_PATH)

    try:
        cursor = connection.execute(JOINED_SELECT)
        logger.info("Joined customer stream initialized.")

        while True:
            batch = cursor.fetchmany(chunk_size)
            if not batch:
                break

            for row in batch:
                yield row

        logger.info("Joined customer stream complete.")

    except sqlite3.Error as error:
        logger.critical(f"Database streaming error: {error}")
        raise

    finally:
        connection.close()


def get_column_names():
    """Return column names in the same order as the joined stream."""
    return list(COLUMNS)