import logging


def get_logger(name: str):
    # Create a custom logger
    logger = logging.getLogger(f"Director[{name}]")
    logger.setLevel(logging.DEBUG)


    # Create a console handler (optional)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Create a formatter and add it to handlers
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(formatter)

    # Add handlers to the logger
    logger.addHandler(console_handler)

    return logger