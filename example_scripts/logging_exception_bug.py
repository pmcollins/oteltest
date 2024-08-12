import logging
import time

from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor


def main():
    logging.basicConfig(level=logging.NOTSET)
    logging.getLogger().addHandler(create_logging_handler())

    logger = logging.getLogger(__name__)

    try:
        raise ValueError("Err")
    except ValueError as e:
        logger.error(e)  # Logging of the raw exception object

    for _ in range(12):
        time.sleep(1)
        print("x")


def create_logging_handler():
    logger_provider = LoggerProvider()
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter(insecure=True))
    )
    return LoggingHandler(logger_provider=logger_provider)


if __name__ == "__main__":
    main()


class MyOtelTest:

    def environment_variables(self):
        return {}

    def requirements(self):
        return ("opentelemetry-exporter-otlp==1.26.0",)

    def wrapper_command(self):
        return ""

    def on_start(self):
        pass

    def on_stop(self, tel, stdout: str, stderr: str, returncode: int) -> None:
        pass

    def is_http(self) -> bool:
        return False
