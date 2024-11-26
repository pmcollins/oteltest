import glob
import importlib
import importlib.util
import inspect
import os
import shutil
import subprocess
import sys
import tempfile
import typing
import venv
from logging import Logger
from pathlib import Path

from oteltest import OtelTest
from oteltest.sink import GrpcSink, HttpSink, raise_if_port_in_use
from oteltest.sink.handler import AccumulatingHandler
from oteltest.version import __version__


def run(script_paths: [str], venv_parent_dir: str, json_dir: str, logger: Logger):
    logger.info("oteltest version %s", __version__)

    temp_dir = venv_parent_dir or tempfile.mkdtemp()
    logger.info("Using temp dir for venvs: %s", temp_dir)

    for script_path in script_paths:
        if os.path.isdir(script_path):
            handle_dir(script_path, temp_dir, json_dir, logger)
        elif os.path.isfile(script_path):
            handle_file(script_path, temp_dir, json_dir, logger)
        else:
            logger.warning("argument %s does not exist", script_path)


def handle_dir(dir_path, temp_dir, json_dir, logger):
    sys.path.append(dir_path)
    for script in ls_scripts(dir_path):
        logger.info("Setting up environment for script %s", script)
        setup_script_environment(temp_dir, dir_path, script, json_dir, logger)


def handle_file(file_path, temp_dir, json_dir, logger):
    logger.info("Setting up environment for file %s", file_path)
    script_dir = os.path.dirname(file_path)
    sys.path.append(script_dir)
    setup_script_environment(
        temp_dir, script_dir, os.path.basename(file_path), json_dir, logger
    )


def ls_scripts(script_dir):
    original_dir = os.getcwd()
    os.chdir(script_dir)
    scripts = glob.glob("*.py")
    os.chdir(original_dir)
    return scripts


def setup_script_environment(
    venv_parent: str, script_dir: str, script: str, json_dir_base: str, logger: Logger
):
    module_name = script[:-3]
    module_path = os.path.join(script_dir, script)
    oteltest_class = load_oteltest_class_for_script(module_name, module_path, logger)
    if oteltest_class is None:
        logger.info("No oteltest class present in [%s]", module_name)
        return
    oteltest_instance = oteltest_class()

    handler = AccumulatingHandler()
    if hasattr(oteltest_instance, "is_http") and oteltest_instance.is_http():
        raise_if_port_in_use(4318)
        sink = HttpSink(handler, logger)
    else:
        raise_if_port_in_use(4317)
        sink = GrpcSink(handler, logger)
    sink.start()

    script_venv = Venv(str(Path(venv_parent) / module_name), logger)
    script_venv.create()

    pip_path = script_venv.path_to_executable("pip")

    for req in oteltest_instance.requirements():
        logger.info("Will install requirement: '%s'", req)
        run_subprocess([pip_path, "install", req], logger)

    stdout, stderr, returncode = run_python_script(
        start_subprocess, script_dir, script, oteltest_instance, script_venv, logger
    )
    print_subprocess_result(stdout, stderr, returncode, logger)

    json_dir = os.path.join(script_dir, json_dir_base)
    filename = get_next_json_file(json_dir, module_name)
    logger.info("Will save telemetry to %s", filename)
    save_telemetry_json(json_dir, filename, handler.telemetry_to_json())

    try:
        oteltest_instance.on_stop(handler.telemetry, stdout, stderr, returncode)
        logger.info("PASSED: %s", script)
    except AssertionError as ae:
        logger.info("AssertionError: %s %s", script, ae)
    sink.stop()


def get_next_json_file(path_str: str, module_name: str):
    path = Path(path_str)
    path.mkdir(exist_ok=True)
    max_index = -1
    for file in path.glob(f"{module_name}.*.json"):
        last_part = file.stem.split(".")[-1]
        if last_part.isdigit():
            index = int(last_part)
            if index > max_index:
                max_index = index
    return f"{module_name}.{max_index + 1}.json"


def save_telemetry_json(script_dir: str, file_name: str, json_str: str):
    path = Path(script_dir) / file_name
    with open(str(path), "w", encoding="utf-8") as file:
        file.write(json_str)


def run_python_script(
    start_subprocess_func,
    script_dir: str,
    script: str,
    oteltest_instance,
    script_venv,
    logger: Logger,
) -> typing.Tuple[str, str, int]:
    logger.info("Running python script: %s", script)
    python_script_cmd = [
        script_venv.path_to_executable("python"),
        str(Path(script_dir) / script),
    ]

    wrapper_script = oteltest_instance.wrapper_command()
    if wrapper_script:
        python_script_cmd.insert(0, script_venv.path_to_executable(wrapper_script))

    # typically python_script_cmd will be ["opentelemetry-instrument", "python", "foo.py"] but with full paths
    logger.info(f"Start subprocess: %s", python_script_cmd)
    proc = start_subprocess_func(
        python_script_cmd, oteltest_instance.environment_variables()
    )
    timeout_seconds = oteltest_instance.on_start()
    if timeout_seconds is None:
        logger.info("Will wait for %s to finish by itself", script)
    else:
        logger.info(
            "Will wait for %d seconds for %s to finish", timeout_seconds, script
        )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
        return stdout, stderr, proc.returncode
    except subprocess.TimeoutExpired as ex:
        proc.kill()
        logger.info("Script %s terminated", script)
        return decode(ex.stdout), decode(ex.stderr), proc.returncode


def start_subprocess(python_script_cmd, env):
    return subprocess.Popen(
        python_script_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )


def decode(b: typing.Optional[bytes]) -> str:
    return b.decode("utf-8") if b else ""


def run_subprocess(args, logger: Logger):
    logger.info("Subprocess: %s", args)
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=True,
    )
    print_subprocess_result(result.stdout, result.stderr, result.returncode, logger)


def print_subprocess_result(stdout: str, stderr: str, returncode: int, logger: Logger):
    logger.info("Return Code: [%s]", returncode)  # %s because can be None
    logger.info("Standard Output:")
    if stdout:
        print(stdout)
    logger.info("Standard Error:")
    if stderr:
        print(stderr)
    logger.info("End Subprocess")


def load_oteltest_class_for_script(module_name, module_path, logger: Logger):
    logger.debug(
        "loading spec from file: module_name [%s] module_path [%s]",
        module_name,
        module_path,
    )
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    logger.debug("spec loaded: [%s]", spec)
    module = importlib.util.module_from_spec(spec)
    logger.debug("module loaded: [%s]", module)
    spec.loader.exec_module(module)
    for attr_name in dir(module):
        value = getattr(module, attr_name)
        if is_test_class(value):
            logger.debug("found test class: [%s]", value)
            return value
    return None


def is_test_class(value):
    return inspect.isclass(value) and (
        is_strict_subclass(value) or "OtelTest" in value.__name__
    )


def is_strict_subclass(value):
    return (
        issubclass(value, OtelTest)
        and value is not OtelTest
        and not inspect.isabstract(value)
    )


class Venv:
    def __init__(self, venv_dir, logger: Logger):
        self.venv_dir = venv_dir
        self.logger = logger

    def create(self):
        if os.path.exists(self.venv_dir):
            self.logger.info(
                "Path to virtual env [%s] already exists, skipping creation",
                self.venv_dir,
            )
        else:
            venv.create(self.venv_dir, with_pip=True)

    def path_to_executable(self, executable_name: str):
        return f"{self.venv_dir}/bin/{executable_name}"

    def rm(self):
        shutil.rmtree(self.venv_dir)
