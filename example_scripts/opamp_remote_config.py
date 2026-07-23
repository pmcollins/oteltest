import os

from opentelemetry._opamp.client import OpAMPClient
from opentelemetry._opamp.proto import opamp_pb2


class OpAMPSmokeOtelTest:
    def __init__(self):
        self.effective_config_seen = False
        self.remote_config_applied = False

    def environment_variables(self):
        return dict(os.environ)

    def requirements(self):
        return ["opentelemetry-opamp-client", "requests"]

    def wrapper_command(self):
        return ""

    def is_http(self):
        return False

    def on_start(self):
        return None

    def on_opamp(
        self,
        effective_config,
        remote_config_status,
        remote_config_error,
    ):
        if effective_config is None:
            return {"demo": "from-server"}

        assert effective_config == {"demo": "from-server"}
        assert remote_config_status == "applied", remote_config_error
        self.effective_config_seen = True
        self.remote_config_applied = True
        return None

    def on_stop(self, telemetry, stdout, stderr, returncode):
        assert returncode == 0, stderr
        assert self.effective_config_seen
        assert self.remote_config_applied
        assert "remote config: {'demo': 'from-server'}" in stdout


if __name__ == "__main__":
    client = OpAMPClient(
        endpoint="http://127.0.0.1:4320/v1/opamp",
        agent_identifying_attributes={"service.name": "opamp-smoke"},
    )

    response = client.send(client.build_full_state_message())
    _, decoded_config = next(client.decode_remote_config(response.remote_config))
    demo_value = decoded_config["demo"]
    assert isinstance(demo_value, str)
    remote_config: dict[str, str] = {"demo": demo_value}
    print("remote config:", remote_config)

    client.update_remote_config_status(
        response.remote_config.config_hash,
        opamp_pb2.RemoteConfigStatuses_APPLIED,
    )
    client.update_effective_config(
        {"": remote_config},
        "application/json",
    )
    client.send(client.build_full_state_message())
