from __future__ import annotations

import hashlib
import http.client
import json
import logging
import socket

import pytest

from opentelemetry._opamp.proto import opamp_pb2
from oteltest.opamp import OpAMPConfigError, OpAMPServer


def agent_message(
    *,
    effective_config=None,
    remote_config_hash=None,
    remote_config_status=None,
    remote_config_error=None,
):
    message = opamp_pb2.AgentToServer(
        instance_uid=b"0123456789abcdef",
        capabilities=opamp_pb2.AgentCapabilities_AcceptsRemoteConfig,
    )
    if effective_config is not None:
        config_file = message.effective_config.config_map.config_map[""]
        config_file.body = json.dumps(effective_config).encode("utf-8")
        config_file.content_type = "application/json"
    if (
        remote_config_hash is not None
        or remote_config_status is not None
        or remote_config_error is not None
    ):
        if remote_config_hash is not None:
            message.remote_config_status.last_remote_config_hash = remote_config_hash
        if remote_config_status is not None:
            message.remote_config_status.status = remote_config_status
        if remote_config_error is not None:
            message.remote_config_status.error_message = remote_config_error
    return message


def post(server, message, *, path="/v1/opamp", content_type="application/x-protobuf"):
    connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=2)
    connection.request(
        "POST",
        path,
        body=message.SerializeToString(),
        headers={"Content-Type": content_type},
    )
    response = connection.getresponse()
    body = response.read()
    status = response.status
    headers = dict(response.getheaders())
    connection.close()
    return status, headers, body


def start_server(callback):
    server = OpAMPServer(callback, logging.getLogger("test-opamp"), port=0)
    server.start()
    return server


def decode_response(body):
    response = opamp_pb2.ServerToAgent()
    response.ParseFromString(body)
    return response


def test_first_request_calls_callback_and_returns_remote_config():
    received = []

    def remote_config(effective_config, remote_config_status, remote_config_error):
        received.append((effective_config, remote_config_status, remote_config_error))
        return {"service": {"name": "checkout"}, "enabled": True}

    server = start_server(remote_config)
    try:
        status, headers, body = post(server, agent_message())
    finally:
        server.stop()

    assert status == 200
    assert headers["Content-Type"] == "application/x-protobuf"
    assert received == [(None, None, None)]

    response = decode_response(body)
    expected_body = b'{"enabled":true,"service":{"name":"checkout"}}'
    assert response.instance_uid == b"0123456789abcdef"
    assert response.capabilities == 7
    assert response.remote_config.config.config_map[""].body == expected_body
    assert (
        response.remote_config.config.config_map[""].content_type == "application/json"
    )
    assert response.remote_config.config_hash == hashlib.sha256(expected_body).digest()


def test_effective_config_is_passed_as_a_fresh_dictionary():
    source = {"service": {"name": "catalog"}}
    received = []

    def remote_config(effective_config, remote_config_status, remote_config_error):
        received.append((effective_config, remote_config_status, remote_config_error))
        effective_config["changed"] = True
        return None

    server = start_server(remote_config)
    try:
        status, _, body = post(
            server,
            agent_message(effective_config=source),
        )
    finally:
        server.stop()

    assert status == 200
    assert decode_response(body).instance_uid == b"0123456789abcdef"
    assert received == [({"service": {"name": "catalog"}, "changed": True}, None, None)]
    assert source == {"service": {"name": "catalog"}}


def test_properties_effective_config_is_passed_as_a_dictionary():
    received = []

    def remote_config(effective_config, remote_config_status, remote_config_error):
        received.append((effective_config, remote_config_status, remote_config_error))
        return None

    request = agent_message()
    config_file = request.effective_config.config_map.config_map["environment"]
    config_file.content_type = (
        "text/plain; format=properties; vendor=splunk; v=1.0.0"
    )
    config_file.body = (
        b"# effective environment\n"
        b"OTEL_SERVICE_NAME=checkout\n"
        b"OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318\n"
    )

    server = start_server(remote_config)
    try:
        status, _, _ = post(server, request)
    finally:
        server.stop()

    assert status == 200
    assert received == [
        (
            {
                "OTEL_SERVICE_NAME": "checkout",
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://127.0.0.1:4318",
            },
            None,
            None,
        )
    ]


@pytest.mark.parametrize(
    ("wire_status", "status", "error"),
    [
        (opamp_pb2.RemoteConfigStatuses_APPLYING, "applying", None),
        (opamp_pb2.RemoteConfigStatuses_APPLIED, "applied", None),
        (opamp_pb2.RemoteConfigStatuses_FAILED, "failed", "invalid config"),
    ],
)
def test_remote_config_status_is_passed_without_protocol_details(
    wire_status, status, error
):
    received = []

    def remote_config(effective_config, remote_config_status, remote_config_error):
        received.append((effective_config, remote_config_status, remote_config_error))
        return None

    server = start_server(remote_config)
    try:
        post(
            server,
            agent_message(
                remote_config_status=wire_status,
                remote_config_error=error,
            ),
        )
    finally:
        server.stop()

    assert received == [(None, status, error)]


def test_callback_receives_latest_state_when_agent_omits_unchanged_fields():
    received = []

    def remote_config(effective_config, remote_config_status, remote_config_error):
        received.append((effective_config, remote_config_status, remote_config_error))
        return None

    server = start_server(remote_config)
    try:
        post(
            server,
            agent_message(effective_config={"demo": "effective"}),
        )
        post(
            server,
            agent_message(
                remote_config_status=opamp_pb2.RemoteConfigStatuses_FAILED,
                remote_config_error="invalid config",
            ),
        )
        post(
            server,
            agent_message(effective_config={"demo": "recovered"}),
        )
    finally:
        server.stop()

    assert received == [
        ({"demo": "effective"}, None, None),
        ({"demo": "effective"}, "failed", "invalid config"),
        ({"demo": "recovered"}, "failed", "invalid config"),
    ]


def test_status_calls_callback_and_hash_controls_resend():
    calls = []

    def remote_config(effective_config, remote_config_status, remote_config_error):
        calls.append((effective_config, remote_config_status, remote_config_error))
        return {"enabled": True}

    server = start_server(remote_config)
    try:
        _, _, first_body = post(server, agent_message())
        first_response = decode_response(first_body)
        config_hash = first_response.remote_config.config_hash

        _, _, matching_body = post(
            server,
            agent_message(
                remote_config_hash=config_hash,
                remote_config_status=opamp_pb2.RemoteConfigStatuses_APPLIED,
            ),
        )
        _, _, compressed_body = post(server, agent_message())
        _, _, mismatching_body = post(
            server,
            agent_message(
                remote_config_hash=b"different",
                remote_config_status=opamp_pb2.RemoteConfigStatuses_APPLIED,
            ),
        )
    finally:
        server.stop()

    assert calls == [
        (None, None, None),
        (None, "applied", None),
        (None, "applied", None),
    ]
    assert not decode_response(matching_body).HasField("remote_config")
    assert not decode_response(compressed_body).HasField("remote_config")
    assert decode_response(mismatching_body).remote_config.config_hash == config_hash


@pytest.mark.parametrize(
    ("content_type", "body", "message"),
    [
        ("text/plain", b"{}", "application/json or text/plain"),
        ("application/json", b"not json", "valid UTF-8 JSON"),
        ("application/json", b"[]", "must contain a dictionary"),
    ],
)
def test_invalid_effective_config_is_reported_after_shutdown(
    content_type, body, message
):
    callback_called = False

    def remote_config(effective_config, remote_config_status, remote_config_error):
        nonlocal callback_called
        callback_called = True
        return None

    request = agent_message()
    config_file = request.effective_config.config_map.config_map[""]
    config_file.content_type = content_type
    config_file.body = body

    server = start_server(remote_config)
    status, _, response_body = post(server, request)
    server.stop()

    assert status == 200
    assert decode_response(response_body).instance_uid == request.instance_uid
    assert not callback_called
    with pytest.raises(OpAMPConfigError, match=message):
        server.raise_callback_error()


def test_multiple_effective_config_files_are_rejected():
    request = agent_message()
    for name in ("one.json", "two.json"):
        config_file = request.effective_config.config_map.config_map[name]
        config_file.content_type = "application/json"
        config_file.body = b"{}"

    server = start_server(
        lambda effective_config, remote_config_status, remote_config_error: None
    )
    status, _, _ = post(server, request)
    server.stop()

    assert status == 200
    with pytest.raises(OpAMPConfigError, match="exactly one"):
        server.raise_callback_error()


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (b"\xff", "valid UTF-8"),
        (b"missing-separator", "invalid property on line 1"),
        (b"=missing-key", "invalid property on line 1"),
    ],
)
def test_invalid_properties_effective_config_is_rejected(body, message):
    request = agent_message()
    config_file = request.effective_config.config_map.config_map["environment"]
    config_file.content_type = "text/plain; format=properties"
    config_file.body = body

    server = start_server(
        lambda effective_config, remote_config_status, remote_config_error: None
    )
    status, _, _ = post(server, request)
    server.stop()

    assert status == 200
    with pytest.raises(OpAMPConfigError, match=message):
        server.raise_callback_error()


def test_callback_assertion_is_returned_to_the_runner_without_http_retry():
    expected_error = AssertionError("effective config was wrong")

    def remote_config(effective_config, remote_config_status, remote_config_error):
        raise expected_error

    server = start_server(remote_config)
    status, _, body = post(server, agent_message())
    server.stop()

    assert status == 200
    assert decode_response(body).instance_uid == b"0123456789abcdef"
    with pytest.raises(AssertionError, match="effective config was wrong") as raised:
        server.raise_callback_error()
    assert raised.value is expected_error


def test_wrong_path_and_content_type_are_rejected():
    server = start_server(
        lambda effective_config, remote_config_status, remote_config_error: None
    )
    try:
        wrong_path_status, _, _ = post(
            server,
            agent_message(),
            path="/wrong",
        )
        wrong_type_status, _, _ = post(
            server,
            agent_message(),
            content_type="application/json",
        )
    finally:
        server.stop()

    assert wrong_path_status == 404
    assert wrong_type_status == 415


def test_stop_releases_server_port():
    server = start_server(
        lambda effective_config, remote_config_status, remote_config_error: None
    )
    port = server.port
    server.stop()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", port))
