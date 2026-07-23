from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING, Any, cast

from google.protobuf.message import DecodeError
from opentelemetry._opamp.proto import opamp_pb2

if TYPE_CHECKING:
    import logging

    RemoteConfigCallback = Callable[[dict | None, str | None, str | None], dict | None]
else:
    RemoteConfigCallback = Callable

_CONTENT_TYPE = "application/x-protobuf"
_CONFIG_CONTENT_TYPES = {"application/json", "text/json"}
_PROPERTIES_CONTENT_TYPE = "text/plain"
_DEFAULT_PATH = "/v1/opamp"
_SERVER_CAPABILITIES = (
    opamp_pb2.ServerCapabilities_AcceptsStatus
    | opamp_pb2.ServerCapabilities_OffersRemoteConfig
    | opamp_pb2.ServerCapabilities_AcceptsEffectiveConfig
)
_REMOTE_CONFIG_STATUSES = {
    opamp_pb2.RemoteConfigStatuses_UNSET: None,
    opamp_pb2.RemoteConfigStatuses_APPLIED: "applied",
    opamp_pb2.RemoteConfigStatuses_APPLYING: "applying",
    opamp_pb2.RemoteConfigStatuses_FAILED: "failed",
}


class OpAMPConfigError(ValueError):
    """Raised when an agent reports an unsupported effective config."""


def _encode_remote_config(config: dict) -> opamp_pb2.AgentRemoteConfig:
    try:
        body = json.dumps(
            config,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        message = "on_opamp() must return a JSON-serializable dictionary"
        raise OpAMPConfigError(message) from error

    config_map = opamp_pb2.AgentConfigMap()
    config_file = config_map.config_map[""]
    config_file.body = body
    config_file.content_type = "application/json"
    return opamp_pb2.AgentRemoteConfig(
        config=config_map,
        config_hash=hashlib.sha256(body).digest(),
    )


def _decode_effective_config(effective_config: opamp_pb2.EffectiveConfig) -> dict:
    config_files = effective_config.config_map.config_map
    if len(config_files) != 1:
        message = "effective config must contain exactly one config file"
        raise OpAMPConfigError(message)

    _, config_file = next(iter(config_files.items()))
    content_type, parameters = _parse_content_type(config_file.content_type)
    if content_type == _PROPERTIES_CONTENT_TYPE and parameters.get("format") == "properties":
        return _decode_properties(config_file.body)
    if content_type not in _CONFIG_CONTENT_TYPES:
        message = (
            "effective config must use application/json or "
            "text/plain; format=properties"
        )
        raise OpAMPConfigError(message)

    try:
        config = json.loads(config_file.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        message = "effective config must contain valid UTF-8 JSON"
        raise OpAMPConfigError(message) from error

    if not isinstance(config, dict):
        message = "effective config JSON must contain a dictionary"
        raise OpAMPConfigError(message)
    return config


def _parse_content_type(content_type: str) -> tuple[str, dict[str, str]]:
    media_type, *raw_parameters = content_type.split(";")
    parameters = {}
    for raw_parameter in raw_parameters:
        name, separator, value = raw_parameter.partition("=")
        if separator:
            parameters[name.strip().lower()] = value.strip().strip('"').lower()
    return media_type.strip().lower(), parameters


def _decode_properties(body: bytes) -> dict[str, str]:
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as error:
        message = "properties effective config must contain valid UTF-8"
        raise OpAMPConfigError(message) from error

    config = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith(("#", "!")):
            continue
        key, separator, value = line.partition("=")
        if not separator or not key.strip():
            message = f"invalid property on line {line_number}"
            raise OpAMPConfigError(message)
        config[key.strip()] = value.strip()
    return config


def _require_remote_config(config) -> dict:
    if not isinstance(config, dict):
        message = "on_opamp() must return a dictionary or None"
        raise OpAMPConfigError(message)
    return config


def _decode_remote_config_status(
    status: opamp_pb2.RemoteConfigStatus,
) -> tuple[str | None, str | None]:
    try:
        status_name = _REMOTE_CONFIG_STATUSES[status.status]
    except KeyError as error:
        message = f"unsupported remote config status: {status.status}"
        raise OpAMPConfigError(message) from error
    return status_name, status.error_message or None


class _OpAMPRequestProcessor:
    def __init__(self, remote_config: RemoteConfigCallback):
        self._remote_config_callback = remote_config
        self._received_first_request = False
        self._effective_config: dict | None = None
        self._remote_config_status: str | None = None
        self._remote_config_error: str | None = None
        self._agent_remote_config_hash: bytes | None = None
        self._current_remote_config: opamp_pb2.AgentRemoteConfig | None = None
        self.callback_error: Exception | None = None

    def process(self, request: opamp_pb2.AgentToServer) -> opamp_pb2.ServerToAgent:
        response = opamp_pb2.ServerToAgent(
            instance_uid=request.instance_uid,
            capabilities=_SERVER_CAPABILITIES,
        )
        if self.callback_error is not None:
            return response

        has_effective_config = request.HasField("effective_config")
        has_remote_config_status = request.HasField("remote_config_status")
        should_call = (
            not self._received_first_request
            or has_effective_config
            or has_remote_config_status
        )
        self._received_first_request = True

        try:
            if should_call:
                if has_effective_config:
                    self._effective_config = _decode_effective_config(
                        request.effective_config
                    )
                if has_remote_config_status:
                    self._agent_remote_config_hash = bytes(
                        request.remote_config_status.last_remote_config_hash
                    )
                    (
                        self._remote_config_status,
                        self._remote_config_error,
                    ) = _decode_remote_config_status(request.remote_config_status)
                new_remote_config = self._remote_config_callback(
                    deepcopy(self._effective_config),
                    self._remote_config_status,
                    self._remote_config_error,
                )
                if new_remote_config is not None:
                    self._current_remote_config = _encode_remote_config(
                        _require_remote_config(new_remote_config)
                    )

            current_remote_config = self._current_remote_config
            if current_remote_config is not None and self._should_send_remote_config(
                request
            ):
                response.remote_config.CopyFrom(current_remote_config)
        except Exception as error:  # noqa: BLE001
            self.callback_error = error

        return response

    def _should_send_remote_config(self, request: opamp_pb2.AgentToServer) -> bool:
        if self._current_remote_config is None:
            return False
        if not (request.capabilities & opamp_pb2.AgentCapabilities_AcceptsRemoteConfig):
            return False
        return self._agent_remote_config_hash != self._current_remote_config.config_hash


class _OpAMPRequestHandler(BaseHTTPRequestHandler):
    def __init__(
        self,
        request: Any,
        client_address: Any,
        server: HTTPServer,
    ) -> None:
        super().__init__(request, client_address, server)

    def do_POST(self) -> None:  # noqa: N802
        server = cast("_OpAMPHTTPServer", self.server)
        if self.path != _DEFAULT_PATH:
            self.send_error(404, "OpAMP endpoint not found")
            return

        content_type = self.headers.get("Content-Type", "")
        if content_type.partition(";")[0].strip().lower() != _CONTENT_TYPE:
            self.send_error(415, f"Content-Type must be {_CONTENT_TYPE}")
            return

        try:
            content_length = int(self.headers["Content-Length"])
            request_body = self.rfile.read(content_length)
            request = opamp_pb2.AgentToServer()
            request.ParseFromString(request_body)
        except (KeyError, TypeError, ValueError, DecodeError):
            self.send_error(400, "Request body must be an AgentToServer protobuf")
            return

        response_body = server.processor.process(request).SerializeToString()
        self.send_response(200)
        self.send_header("Content-Type", _CONTENT_TYPE)
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def log_message(self, message, *args) -> None:
        server = cast("_OpAMPHTTPServer", self.server)
        server.logger.debug("OpAMP server: %s", message % args)


class _OpAMPHTTPServer(HTTPServer):
    def __init__(
        self,
        address: tuple[str, int],
        processor: _OpAMPRequestProcessor,
        logger: logging.Logger,
    ):
        self.processor = processor
        self.logger = logger
        super().__init__(address, _OpAMPRequestHandler)


class OpAMPServer:
    def __init__(
        self,
        remote_config: RemoteConfigCallback,
        logger: logging.Logger,
        host: str = "127.0.0.1",
        port: int = 4320,
    ):
        self._processor = _OpAMPRequestProcessor(remote_config)
        self._started = False
        self._httpd = _OpAMPHTTPServer(
            (host, port),
            self._processor,
            logger,
        )
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return self._httpd.server_port

    def start(self) -> None:
        self._thread.start()
        self._started = True

    def stop(self) -> None:
        if self._started:
            self._httpd.shutdown()
            self._thread.join()
            self._started = False
        self._httpd.server_close()

    def raise_callback_error(self) -> None:
        if self._processor.callback_error is not None:
            raise self._processor.callback_error
