from collections.abc import Sequence
from importlib.util import cache_from_source
from logging import getLogger
from os import getenv
from pathlib import Path

from setuptools import setup
from setuptools.command.install import install as _install

USE_CYTHON = getenv("USE_CYTHON") == "1"
SRC_PREFIX = "src-python/"
INCLUDE_FILE_PATTERNS = ("syntropy/**/*.py",)
EXCLUDE_FILE_PATTERNS = (
    "syntropy/**/__init__.py",
    "syntropy/**/__main__.py",
    "syntropy/**/py.typed",
)

_logger = getLogger(__name__)


class install(_install):
    def run(self) -> None:
        super().run()

        if not USE_CYTHON:
            return

        build_py_obj = self.distribution.get_command_obj("build_py")
        build_py_obj.ensure_finalized()
        if getattr(build_py_obj, "editable_mode", False):
            return

        assert self.install_lib is not None
        install_lib = Path(self.install_lib)

        def norm_files_set(patterns: Sequence[str]) -> set[str]:
            files_set: set[str] = set()
            for pattern in patterns:
                for file in install_lib.glob(pattern):
                    files_set.add(str(file.resolve()))
            return files_set

        include_files_set = norm_files_set(INCLUDE_FILE_PATTERNS)
        exclude_files_set = norm_files_set(EXCLUDE_FILE_PATTERNS)

        for file in include_files_set.difference(exclude_files_set):
            protected_file = Path(file)
            _logger.info(f"Removing protected file: {protected_file}")

            protected_file.unlink(missing_ok=True)
            protected_file.with_suffix(".c").unlink(missing_ok=True)
            protected_file.with_suffix(".cpp").unlink(missing_ok=True)
            for optimization in ("", 1, 2):
                bytecode_file = cache_from_source(protected_file, optimization=optimization)
                Path(bytecode_file).unlink(missing_ok=True)


ext_modules = None
if USE_CYTHON:
    from Cython.Build import cythonize
    from setuptools import Extension

    src_root = Path(__file__).parent.joinpath(SRC_PREFIX)
    include_files: list[Path] = []
    exclude_files: set[Path] = set()

    for pattern in INCLUDE_FILE_PATTERNS:
        include_files.extend(src_root.glob(pattern))
    for pattern in EXCLUDE_FILE_PATTERNS:
        exclude_files.update(src_root.glob(pattern))

    exts: list[Extension] = []
    setup_dir = Path(__file__).parent
    for file_path in include_files:
        if file_path in exclude_files:
            continue
        rel = file_path.relative_to(src_root)
        if rel.suffix != ".py":
            continue
        mod_name = ".".join(rel.with_suffix("").parts)
        src = str(file_path.relative_to(setup_dir).as_posix())
        exts.append(Extension(mod_name, [src]))

    ext_modules = cythonize(
        exts,
        compiler_directives={"language_level": 3},
        annotate=False,
    )

setup(
    cmdclass={"install": install},
    ext_modules=ext_modules,
)
