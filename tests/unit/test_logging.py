import logging
from io import StringIO

from numa.utils import configure_logging, get_logger


def test_configure_logging_writes_to_console_stream() -> None:
    stream = StringIO()
    configure_logging(level="DEBUG", log_format="%(levelname)s:%(message)s", stream=stream)

    logger = get_logger("numa.test")
    logger.debug("Agent started")

    assert stream.getvalue() == "DEBUG:Agent started\n"
    assert logger.isEnabledFor(logging.DEBUG)
