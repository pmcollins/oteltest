import logging
import time

from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs._internal.export import BatchLogRecordProcessor

NUM_LOGS = 16


def main():
    lp = LoggerProvider()
    exporter = OTLPLogExporter(insecure=True)
    processor = BatchLogRecordProcessor(exporter)
    lp.add_log_record_processor(processor)

    logger = logging.getLogger()
    logger.addHandler(LoggingHandler(logger_provider=lp))

    for i in range(NUM_LOGS):
        time.sleep(1)
        logger.warning("Log record %d", i)


if __name__ == "__main__":
    main()


class MyOtelTest:

    def environment_variables(self):
        return {}

    def requirements(self):
        return ("opentelemetry-distro[otlp]",)

    def wrapper_command(self):
        return None

    def on_start(self):
        pass

    def on_stop(self, tel, stdout: str, stderr: str, returncode: int):
        from oteltest.telemetry import count_logs

        assert count_logs(tel) == NUM_LOGS

    def is_http(self):
        return False
