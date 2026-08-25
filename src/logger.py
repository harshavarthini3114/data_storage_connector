import logging


def get_production_logger():

    log = logging.getLogger("data_connector")
    log.setLevel(logging.INFO)

    if not log.handlers:

        log_handler = logging.FileHandler("app.log")
        log_handler.setLevel(logging.INFO)

        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] (%(filename)s:%(lineno)d) - %(message)s'
        )

        log_handler.setFormatter(formatter)

        log.addHandler(log_handler)

    return log