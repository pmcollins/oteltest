"""
Causes an exception to be raised, caught, and logged. This is because there is a None value present in the dictionary
being logged. The other logs in the batch are lost.
"""


def main():
    import logging

    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
        OTLPLogExporter,
    )
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

    logger_provider = LoggerProvider()
    set_logger_provider(logger_provider)
    exporter = OTLPLogExporter(insecure=True)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
    handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
    logging.getLogger().addHandler(handler)

    # works, but is never exported
    logging.warning({"hello": "world"})
    # causes batch to be discarded
    logging.warning({"hello": None})
    # works, but is never exported
    logging.warning({"goodbye": "world"})

    handler.flush()
    # works since previous batch was flushed already
    logging.warning({"hello": "again"})
    logger_provider.shutdown()


if __name__ == "__main__":
    main()


class MyOtelTest:
    def environment_variables(self):
        return {}

    def requirements(self):
        return ("opentelemetry-distro[otlp]",)

    def wrapper_command(self):
        return ""

    def on_start(self):
        pass

    def on_stop(self, tel, stdout: str, stderr: str, returncode: int):
        return 12

    def is_http(self):
        return False
