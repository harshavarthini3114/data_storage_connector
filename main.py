from src.db_loader import initialize_data_warehouse, stream_joined_records
from src.logger import get_production_logger


def main():
    logger = get_production_logger()

    initialize_data_warehouse()

    count = 0
    for record in stream_joined_records(chunk_size=32):
        count += 1
        if count <= 3:
            print(record)

    logger.info(f"Streamed {count} joined records.")
    print(f"Streamed {count} joined records.")


if __name__ == "__main__":
    main()