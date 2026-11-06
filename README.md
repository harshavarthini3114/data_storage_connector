# MemStream-DB

### Memory-Conscious Relational Data Streamer with Fault-Tolerant Loading

**Tech stack:** Python · SQLite · SQL INNER JOIN · Generators · Logging · Git

---

## Overview

MemStream-DB loads a relational customer dataset into SQLite, joins two related tables, and streams the joined rows back one at a time. Rows are fetched in fixed-size batches with `fetchmany()`, so the reader never pulls the full result set into memory in one call.

It is the data layer of a three-project series:

- **MemStream-DB** (this repository): safe loading and memory-conscious streaming from SQLite.
- **Automated ML Trainer**: consumes the joined stream, trains and selects models, saves a champion.
- **FastAPI Serving** (in progress): serves predictions from the saved champion.

Sample dataset: IBM Telco Customer Churn, 7,043 customers.

---

## What It Does

1. **Downloads the dataset once.** If `data/telco_churn.csv` already exists, the download is skipped.
2. **Splits the data into two related tables.**
   - `customer_profiles`: demographics, account details, contract, charges, and the `Churn` label.
   - `customer_services`: phone, internet, and streaming services.
   Both tables share `customerID` as the key.
3. **Reloads both tables in one transaction.** Either both tables are fully reloaded, or neither is. Running the loader again does not fail with duplicate-key errors.
4. **Streams the joined result.** An `INNER JOIN` on `customerID` runs in SQLite, and rows are fetched with `fetchmany(chunk_size)` and yielded one at a time.
5. **Logs every step** to `app.log` with timestamp, level, file name, and line number.

---

## Design Decisions

### Chunked streaming instead of `fetchall()`
`fetchall()` returns every row in one list. `fetchmany(chunk_size)` returns a fixed-size batch, and the generator yields rows from it. The Python side holds one batch at a time.

### Two tables, one stream
The join is kept in the database engine, so the consumer receives already-stitched rows and does not have to merge the tables itself. The output column order matches the original single-table layout, so downstream code does not change.

### Deterministic row order
The join is ordered by the profile table's `rowid`, which is the CSV order. This keeps the order stable across runs, so any downstream train/test split stays reproducible.

### Transaction-safe reload
Both tables are cleared and reloaded inside one transaction. Any error rolls back both tables and logs a `CRITICAL` entry before the exception is re-raised. The connection is always closed in a `finally` block.

### Explicit handling of blank values
`TotalCharges` is blank for customers with tenure 0. These are stored as `0.0` on purpose.

---

## Project Structure

```text
data_storage_connector/
├── data/                       # generated at runtime, not committed
│   ├── telco_churn.csv
│   └── warehouse.db
├── docs/
│   └── screenshots/
│       ├── terminal-output.png
│       └── app-log-output.png
├── src/
│   ├── __init__.py
│   ├── logger.py               # shared logger (file handler, no duplicate handlers)
│   └── db_loader.py            # download, two-table load, joined streaming
├── main.py                     # entry point: load, then stream and count
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Schema

**`customer_profiles`** (one row per customer, primary key `customerID`)

| Column group | Columns |
|---|---|
| Identity | `customerID` |
| Demographics | `gender`, `SeniorCitizen`, `Partner`, `Dependents` |
| Account | `tenure`, `Contract`, `PaperlessBilling`, `PaymentMethod` |
| Charges | `MonthlyCharges`, `TotalCharges` |
| Label | `Churn` |

**`customer_services`** (one row per customer, same `customerID`)

| Column group | Columns |
|---|---|
| Phone | `PhoneService`, `MultipleLines` |
| Internet | `InternetService`, `OnlineSecurity`, `OnlineBackup`, `DeviceProtection`, `TechSupport` |
| Streaming | `StreamingTV`, `StreamingMovies` |

The joined stream returns 21 columns in the original dataset order.

---

## Setup

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

## Usage

Run from the project root (the folder containing `main.py`):

```powershell
python main.py
```

`main.py` loads the warehouse, then streams every joined record and counts them.

To use the stream in another project:

```python
from src.db_loader import stream_joined_records, get_column_names

columns = get_column_names()
for row in stream_joined_records(chunk_size=32):
    record = dict(zip(columns, row))
    # process one customer at a time
```

---

## Output

### Expected log lines (`app.log`)

```text
CSV already present, skipping download.
Successfully loaded 7043 customers into customer_profiles and customer_services.
Joined customer stream initialized.
Joined customer stream complete.
Streamed 7043 joined records.
```

On a first run without a local CSV, the download lines appear before the load line.

### Terminal output

![Terminal output](docs/screenshots/terminal-output.png)

### Application log

![Application log output](docs/screenshots/app-log-output.png)

Running `python main.py` a second time should produce the same count (7043) and no errors.

---

## Limitations

- **Streaming ends at the loader.** Downstream consumers that need the full matrix (for example, scikit-learn training) collect the rows into memory. Memory is bounded at the database-reading layer.
- **Single-writer SQLite.** Fine for this project, not for concurrent writers.
- **Fixed download URL.** If the upstream file moves, the download step must be updated.
- **Full reload each run.** The loader clears and reloads both tables on every call. Fine for 7,043 rows; incremental loading would be needed for larger, changing data.

---

## Roadmap

- Add a row-count check after load, and fail loudly if the count is wrong.
- Move hard-coded paths and the download URL into a config file.
- Add incremental loading for updated records.