from __future__ import annotations

from typing import Mapping, Optional, Sequence


class MyOtelTest:
    def environment_variables(self) -> Mapping[str, str]:
        return {}

    def requirements(self) -> Sequence[str]:
        return ("opentelemetry-distro",)

    def wrapper_command(self) -> str:
        return ""

    def on_start(self) -> Optional[float]:
        return None

    def on_stop(self, tel, stdout, stderr, returncode) -> None:
        pass
