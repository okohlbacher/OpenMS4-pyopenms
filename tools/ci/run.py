#!/usr/bin/env python3
"""Build, test and package pyOpenMS against installed, pinned dependencies.

pyOpenMS consumes Core directly and the ProSE and FLASH backends as separate
installed packages, and those two build their executables against CLI, so this
driver installs that whole chain before configuring the bindings. It packages the
installed module tree and then builds the same bindings as a wheel, repairs it to
carry every library it links, and runs the test suite against that wheel from a
fresh virtual environment with no build prefix on any library path.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import time


def package_name(source: Path) -> str:
    """Archive name prefix: the repository this package is published from."""
    url = subprocess.check_output(
        ["git", "-C", str(source), "remote", "get-url", "origin"], text=True).strip()
    return url.rstrip("/").removesuffix(".git").rsplit("/", 1)[-1]


def check_install(prefix: Path, python: str) -> None:
    """Fail unless the installed module imports and reports its own version."""
    module = prefix / "pyopenms"
    if not (module / "__init__.py").is_file():
        raise ValueError(f"{module} was not installed")
    if not sorted(module.glob("*.pyi")):
        raise ValueError("no stub files were installed")


def archive_install(prefix: Path, output: Path, name: str) -> Path:
    """Create a checksummed archive while preserving library symlinks."""
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"{name}.tar.gz"
    with tarfile.open(archive, "w:gz") as stream:
        stream.add(prefix, arcname=name)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".gz.sha256").write_text(
        f"{digest}  {archive.name}\n", encoding="utf-8")
    return archive


def test_environment(build: Path, configuration: str) -> dict[str, str]:
    """The fixture variables CTest passes to the Python tests, read from CTest itself."""
    tests = json.loads(subprocess.check_output(
        ["ctest", "--test-dir", str(build), "-C", configuration, "--show-only=json-v1"], text=True))
    for test in tests["tests"]:
        if test["name"] == "pyopenms_unittests":
            variables = dict(arg.split("=", 1) for arg in test["command"]
                             if "=" in arg and not arg.startswith("-"))
            # The wheel must find its own bundled runtime data, so OPENMS_DATA_PATH stays out.
            return {k: v for k, v in variables.items() if k not in ("PYTHONPATH", "OPENMS_DATA_PATH")}
    raise ValueError("pyopenms_unittests is not registered")


def repair_command(wheel: Path, output: Path, library_dirs: list[str]) -> list[str]:
    """The platform's wheel repair tool, bundling the pinned libraries into the wheel."""
    if sys.platform == "linux":
        return ["auditwheel", "repair", "-w", str(output), str(wheel)]
    if sys.platform == "darwin":
        import platform
        return ["delocate-wheel", "--require-archs", platform.machine(), "-w", str(output),
                "-v", str(wheel)]
    command = ["delvewheel", "repair", "-w", str(output)]
    for directory in library_dirs:
        command += ["--add-path", directory]
    return command + [str(wheel)]


def link_rpath_dependencies(prefixes: list[Path], search: list[Path]) -> list[str]:
    """Resolve every @rpath dependency of the installed libraries inside our prefixes.

    The SDKs link their dependencies as @rpath/NAME and find them through the
    environment. On the Intel runner /usr/local/lib (Homebrew) is searched before the
    pinned conda prefix, so delocate planned two libraries with the same basename
    (libzstd, via Homebrew's libzip) and refused to repair the wheel. Linking the
    pinned copy next to the library that asks for it makes the resolution ours.
    """
    linked = []
    for prefix in prefixes:
        libraries = sorted(prefix.glob("*.dylib"))
        for library in libraries:
            text = subprocess.check_output(["otool", "-L", str(library)], text=True)
            for name in re.findall(r"@rpath/(\S+\.dylib)", text):
                target = prefix / name
                if target.exists():
                    continue
                source = next((directory / name for directory in search
                               if (directory / name).exists()), None)
                if source is None:
                    continue   # delocate reports what it cannot resolve
                target.symlink_to(source)
                linked.append(f"{target} -> {source}")
    return linked


def core_prefix(extracted: Path) -> Path:
    """Find the single Core SDK root extracted by the workflow."""
    candidates = [path for path in extracted.iterdir()
                  if path.is_dir() and (path / "source-revision.txt").is_file()]
    if len(candidates) != 1:
        raise ValueError(f"Expected one extracted Core SDK, found {len(candidates)}")
    return candidates[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--core-dir", required=True, type=Path)
    parser.add_argument("--cli-source", required=True, type=Path)
    parser.add_argument("--prose-source", required=True, type=Path)
    parser.add_argument("--flash-source", required=True, type=Path)
    parser.add_argument("--test-data-source", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[2]
    work = args.work_dir.resolve()
    if args.jobs < 1 or (work.exists() and any(work.iterdir())):
        parser.error("--jobs must be positive and --work-dir must be empty")
    results = work / "results"
    results.mkdir(parents=True)
    core = core_prefix(args.core_dir.resolve())
    cli_build, cli_install = work / "cli-build", work / "cli"
    data_build, data_install = work / "test-data-build", work / "test-data"
    providers = work / "providers"
    build, install = work / "pyopenms-build", work / "pyopenms"
    dependencies = Path(os.environ["CONDA_PREFIX"]).resolve()
    windows = sys.platform == "win32"
    dependency_prefix = dependencies / "Library" if windows else dependencies
    generator = "Visual Studio 17 2022" if windows else "Ninja"
    configuration = "Release"
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join(
        [str(dependency_prefix / "bin"), str(core / "bin"), str(cli_install / "bin"),
         str(providers / "bin")]) + os.pathsep + env["PATH"]
    library_dirs = os.pathsep.join(
        [str(dependency_prefix / "lib"), str(core / "lib"), str(cli_install / "lib"),
         str(providers / "lib")])
    if sys.platform == "linux":
        env["LD_LIBRARY_PATH"] = library_dirs
    elif sys.platform == "darwin":
        env["DYLD_FALLBACK_LIBRARY_PATH"] = library_dirs
    commands = []

    def run(name: str, command: list[str], cwd: Path = source) -> None:
        started = time.monotonic()
        print(f"\n--- {name} ---", flush=True)
        log = results / f"{name}.log"
        with log.open("w", encoding="utf-8") as stream:
            process = subprocess.Popen(command, cwd=cwd, env=env, text=True,
                                       encoding="utf-8", errors="replace",
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            for line in process.stdout:
                stream.write(line)
                print(line, end="", flush=True)
            code = process.wait()
        commands.append({"name": name, "command": command, "returncode": code,
                         "elapsed_seconds": round(time.monotonic() - started, 3)})
        (results / "commands.json").write_text(
            json.dumps(commands, indent=2) + "\n", encoding="utf-8")
        if code:
            raise subprocess.CalledProcessError(code, command)

    common = ["-G", generator, f"-DCMAKE_BUILD_TYPE={configuration}",
              "-DOPENMS4_REQUIRE_CLEAN_SOURCE=ON"]
    if windows:
        common += ["-A", "x64", "-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL"]
    elif sys.platform == "darwin":
        common += [f"-DOpenMP_ROOT={dependency_prefix.as_posix()}",
                   f"-DCURL_ROOT={dependency_prefix.as_posix()}",
                   "-DCMAKE_FIND_FRAMEWORK=LAST"]
    run("driver-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tools/ci", "-v"])
    run("configure-cli", ["cmake", "-S", str(args.cli_source.resolve()), "-B", str(cli_build),
                          f"-DCMAKE_INSTALL_PREFIX={cli_install.as_posix()}",
                          f"-DCMAKE_PREFIX_PATH={core.as_posix()};{dependency_prefix.as_posix()}",
                          *common])
    run("build-cli", ["cmake", "--build", str(cli_build), "--config", configuration,
                      "--parallel", str(args.jobs)])
    run("install-cli", ["cmake", "--install", str(cli_build), "--config", configuration])
    run("configure-test-data",
        ["cmake", "-S", str(args.test_data_source.resolve()), "-B", str(data_build),
         f"-DCMAKE_INSTALL_PREFIX={data_install.as_posix()}",
         f"-DCMAKE_PREFIX_PATH={core.as_posix()};{dependency_prefix.as_posix()}", *common])
    run("install-test-data", ["cmake", "--install", str(data_build), "--config", configuration])
    # ProSE and FLASH publish the backend targets the bindings expose, and both
    # build their own executables against CLI, so the whole chain is installed
    # into one provider prefix before the bindings are configured.
    for name, provider in (("prose", args.prose_source), ("flash", args.flash_source)):
        provider_build = work / f"{name}-build"
        run(f"configure-{name}", ["cmake", "-S", str(provider.resolve()), "-B", str(provider_build),
                                  f"-DCMAKE_INSTALL_PREFIX={providers.as_posix()}",
                                  f"-DCMAKE_PREFIX_PATH={core.as_posix()};{cli_install.as_posix()};"
                                  f"{data_install.as_posix()};{dependency_prefix.as_posix()}",
                                  *common])
        run(f"build-{name}", ["cmake", "--build", str(provider_build), "--config", configuration,
                              "--parallel", str(args.jobs)])
        run(f"install-{name}", ["cmake", "--install", str(provider_build), "--config", configuration])
    prefixes = ";".join([core.as_posix(), providers.as_posix(), data_install.as_posix(),
                         dependency_prefix.as_posix()])
    options = ["-DPYOPENMS_BUILD_TESTING=ON", "-DPYOPENMS_GENERATE_STUBS=ON",
               "-DPYOPENMS_WITH_PROSE=ON", "-DPYOPENMS_WITH_FLASH=ON",
               f"-DPython_EXECUTABLE={sys.executable}"]
    if windows:
        options.append(f"-DPYOPENMS_DLL_PATH={(dependency_prefix / 'bin').as_posix()}")
    else:
        origin = "@loader_path" if sys.platform == "darwin" else "$ORIGIN"
        options.append(f"-DCMAKE_INSTALL_RPATH={origin}/../lib")
    run("configure-pyopenms", ["cmake", "-S", str(source), "-B", str(build),
                               f"-DCMAKE_INSTALL_PREFIX={install.as_posix()}",
                               f"-DCMAKE_PREFIX_PATH={prefixes}", *options, *common])
    run("build-pyopenms", ["cmake", "--build", str(build), "--config", configuration,
                           "--parallel", str(args.jobs)])
    if windows:
        dll_dirs = sorted({str(path.parent) for path in build.rglob("*.dll")})
        env["PATH"] = os.pathsep.join([*dll_dirs, env["PATH"]])
    run("test-pyopenms", ["ctest", "--test-dir", str(build), "-C", configuration,
                          "--output-on-failure", "--no-tests=error", "--parallel", str(args.jobs)])
    run("install-pyopenms", ["cmake", "--install", str(build), "--config", configuration])
    check_install(install, sys.executable)
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    install.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / "dependencies.lock.json", install / "dependencies.lock.json")
    (install / "source-revision.txt").write_text(revision + "\n", encoding="utf-8")
    archive_install(install, work / "dist",
                    f"OpenMS4-pyopenms-{args.platform}-Release-{revision[:12]}")

    # The wheel: the same bindings built through the PEP 517 backend, repaired so
    # the wheel carries Core, the backends and their third-party libraries.
    if sys.platform == "darwin":
        links = link_rpath_dependencies(
            [core / "lib", providers / "lib", cli_install / "lib"],
            [dependency_prefix / "lib", core / "lib", providers / "lib", cli_install / "lib"])
        print("\n--- linked @rpath dependencies ---\n" + "\n".join(links or ["none"]), flush=True)
    wheel_tools = {"linux": ["auditwheel", "patchelf"], "darwin": ["delocate"],
                   "win32": ["delvewheel"]}[sys.platform]
    run("install-wheel-tools", [sys.executable, "-m", "pip", "install", "--no-input",
                                "py-build-cmake>=0.3.0", *wheel_tools])
    # py-build-cmake escapes ";" in strings, so the prefix list must be a TOML array.
    wheel_options = {"CMAKE_PREFIX_PATH": json.dumps(prefixes.split(";")),
                     "PYOPENMS_PREPARE_WHEEL_REPAIR": "ON",
                     "PYOPENMS_WITH_PROSE": "ON", "PYOPENMS_WITH_FLASH": "ON",
                     "OPENMS4_REQUIRE_CLEAN_SOURCE": "ON"}
    if windows:
        wheel_options |= {"CMAKE_GENERATOR_PLATFORM": "x64",
                          "CMAKE_MSVC_RUNTIME_LIBRARY": "MultiThreadedDLL"}
    elif sys.platform == "darwin":
        wheel_options |= {"OpenMP_ROOT": dependency_prefix.as_posix(),
                          "CURL_ROOT": dependency_prefix.as_posix(), "CMAKE_FIND_FRAMEWORK": "LAST"}
    wheel_config = work / "wheel.toml"
    wheel_config.write_text(
        f'[cmake]\ngenerator = "{generator}"\nbuild_path = "{(work / "wheel-build").as_posix()}"\n[cmake.options]\n'
        + "".join(f'{key} = {value if value.startswith("[") else json.dumps(value)}\n'
                  for key, value in wheel_options.items()), encoding="utf-8")
    wheelhouse, repaired = work / "wheelhouse", work / "wheelhouse-repaired"
    run("build-wheel", [sys.executable, "-m", "pip", "wheel", str(source), "--no-build-isolation",
                        "--no-deps", "-w", str(wheelhouse), f"--config-settings=--local={wheel_config}"])
    (wheel,) = wheelhouse.glob("pyopenms-*.whl")
    if sys.platform == "darwin":
        # Records every resolved library path before delocate copies them, so a
        # duplicate basename (two libzstd copies on one runner image) is diagnosable.
        run("list-wheel-deps", ["delocate-listdeps", "--all", "--depending", str(wheel)])
    run("repair-wheel", repair_command(wheel, repaired, library_dirs.split(os.pathsep)))
    (wheel,) = repaired.glob("pyopenms-*.whl")

    # Test it the way a user gets it: a fresh environment, nothing on the library
    # path, the fixture paths CTest uses, and the bundled runtime data.
    venv = work / "wheel-venv"
    run("create-wheel-venv", [sys.executable, "-m", "venv", str(venv)])
    venv_python = venv / ("Scripts/python.exe" if windows else "bin/python")
    run("install-wheel", [str(venv_python), "-m", "pip", "install", "--no-input", str(wheel),
                          "pytest", "docutils", "pandas", "pyarrow!=24.0.0,!=25.0.0"])
    user_env = {k: v for k, v in os.environ.items()
                if k not in ("LD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH", "OPENMS_DATA_PATH")}
    user_env.update(test_environment(build, configuration))
    env, build_env = user_env, env
    test_dir = work / "wheel-test"
    test_dir.mkdir()
    run("test-wheel", [str(venv_python), "-m", "pytest", str(source / "tests"),
                       "--import-mode=importlib", "-p", "no:cacheprovider"], cwd=test_dir)
    env = build_env
    shutil.copy2(wheel, work / "dist" / wheel.name)
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    (work / "dist" / f"{wheel.name}.sha256").write_text(f"{digest}  {wheel.name}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
