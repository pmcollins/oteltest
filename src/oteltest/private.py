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
from pathlib import Path

from oteltest import OtelTest
from oteltest.sink import GrpcSink, HttpSink
from oteltest.sink.handler import AccumulatingHandler
from oteltest.version import __version__


def run(script_paths: [str], venv_parent_dir: str, json_dir: str):
    print(f"oteltest version {__version__}")

    temp_dir = venv_parent_dir or tempfile.mkdtemp()
    print(f"- Using temp dir for venvs: {temp_dir}")

    for script_path in script_paths:
        if os.path.isdir(script_path):
            handle_dir(script_path, temp_dir, json_dir)
        elif os.path.isfile(script_path):
            handle_file(script_path, temp_dir, json_dir)
        else:
            print(f"- argument {script_path} does not exist")


def handle_dir(dir_path, temp_dir, json_dir):
    sys.path.append(dir_path)
    for script in ls_scripts(dir_path):
        print(f"- Setting up environment for script {script}")
        setup_script_environment(temp_dir, dir_path, script, json_dir)


def handle_file(file_path, temp_dir, json_dir):
    print(f"- Setting up environment for file {file_path}")
    script_dir = os.path.dirname(file_path)
    sys.path.append(script_dir)
    setup_script_environment(
        temp_dir, script_dir, os.path.basename(file_path), json_dir
    )


def ls_scripts(script_dir):
    original_dir = os.getcwd()
    os.chdir(script_dir)
    scripts = glob.glob("*.py")
    os.chdir(original_dir)
    return scripts


def setup_script_environment(
    venv_parent: str, script_dir: str, script: str, json_dir_base: str
):
    module_name = script[:-3]
    module_path = os.path.join(script_dir, script)
    oteltest_class = load_oteltest_class_for_script(module_name, module_path)
    if oteltest_class is None:
        print(f"- No oteltest class present in '{module_name}'")
        return
    oteltest_instance = oteltest_class()

    handler = AccumulatingHandler()
    if hasattr(oteltest_instance, "is_http") and oteltest_instance.is_http():
        sink = HttpSink(handler)
    else:
        sink = GrpcSink(handler)
    sink.start()

    script_venv = Venv(str(Path(venv_parent) / module_name))
    script_venv.create()

    pip_path = script_venv.path_to_executable("pip")

    for req in oteltest_instance.requirements():
        print(f"- Will install requirement: '{req}'")
        run_subprocess([pip_path, "install", req])

    stdout, stderr, returncode = run_python_script(
        start_subprocess, script_dir, script, oteltest_instance, script_venv
    )
    print_subprocess_result(stdout, stderr, returncode)

    json_dir = os.path.join(script_dir, json_dir_base)
    filename = get_next_json_file(json_dir, module_name)
    print(f"- Will save telemetry to {filename}")
    save_telemetry_json(json_dir, filename, handler.telemetry_to_json())

    oteltest_instance.on_stop(handler.telemetry, stdout, stderr, returncode)
    print(f"- PASSED: {script}")


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
    start_subprocess_func, script_dir: str, script: str, oteltest_instance, script_venv
) -> typing.Tuple[str, str, int]:
    print(f"- Running python script: {script}")
    python_script_cmd = [
        script_venv.path_to_executable("python"),
        str(Path(script_dir) / script),
    ]

    wrapper_script = oteltest_instance.wrapper_command()
    if wrapper_script:
        python_script_cmd.insert(0, script_venv.path_to_executable(wrapper_script))

    # typically python_script_cmd will be ["opentelemetry-instrument", "python", "foo.py"] but with full paths
    print(f"- Start subprocess: {python_script_cmd}")
    proc = start_subprocess_func(
        python_script_cmd, oteltest_instance.environment_variables()
    )
    timeout = oteltest_instance.on_start()
    if timeout is None:
        print(f"- Will wait for {script} to finish by itself")
    else:
        print(f"- Will wait for {timeout} seconds for {script} to finish")
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return stdout, stderr, proc.returncode
    except subprocess.TimeoutExpired as ex:
        proc.kill()
        print(f"- Script {script} terminated")
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


def run_subprocess(args):
    print(f"- Subprocess: {args}")
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=True,
    )
    print_subprocess_result(result.stdout, result.stderr, result.returncode)


def print_subprocess_result(stdout: str, stderr: str, returncode: int):
    print(f"- Return Code: {returncode}")
    print("- Standard Output:")
    if stdout:
        print(stdout)
    print("- Standard Error:")
    if stderr:
        print(stderr)
    print("- End Subprocess -\n")


def load_oteltest_class_for_script(module_name, module_path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for attr_name in dir(module):
        value = getattr(module, attr_name)
        if is_test_class(value):
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
    def __init__(self, venv_dir):
        self.venv_dir = venv_dir

    def create(self):
        if os.path.exists(self.venv_dir):
            print(
                f"- Path to virtual env [{self.venv_dir}] already exists, skipping creation"
            )
        else:
            venv.create(self.venv_dir, with_pip=True)

    def path_to_executable(self, executable_name: str):
        return f"{self.venv_dir}/bin/{executable_name}"

    def rm(self):
        shutil.rmtree(self.venv_dir)
