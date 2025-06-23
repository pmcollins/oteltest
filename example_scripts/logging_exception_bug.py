from __future__ import annotations

"""
Causes a ValueError to be raised, caught, and logged. The exception arises because we are trying to log an object.
"""

def main():
    import logging
    import time


    logging.basicConfig(level=logging.NOTSET)
    logging.getLogger().addHandler(create_logging_handler())

    logger = logging.getLogger(__name__)

    try:
        error_message = "Err"
        raise ValueError(error_message)
    except ValueError as e:
        # Using logger.exception instead of logger.error for the exception
        logger.exception(e)
        # This properly logs the exception with traceback

    for _ in range(4):
        # demonstrate that the exception was handled and that we can still perform an operation
        time.sleep(1)
        logger.info("x")  # Replacing print with logger.info


def create_logging_handler():
    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

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
