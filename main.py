from src.logger import get_production_logger

if __name__ == "__main__":
  logger = get_production_logger()

  logger.info("System core infrastructure initialized successfully.")
  logger.warning("Testing system exception layer alerts.")
