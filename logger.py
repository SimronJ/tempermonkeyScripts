import logging
import sys

def setup_console_logging(level: int = logging.DEBUG) -> None:
    logging.basicConfig(
        level=level,
        format='%(asctime)s %(levelname)s: %(message)s',
        stream=sys.stdout
    )


