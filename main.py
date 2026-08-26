from src.logger import get_production_logger
from src.db_loader import initialize_data_warehouse, stream_joined_records

if __name__ == "__main__":
  logger = get_production_logger()

  initialize_data_warehouse()

  for record in stream_joined_records():
        logger.info(f"Processing memory-safe record: {record}")
        print(record)

