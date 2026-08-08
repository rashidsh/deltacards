import hashlib
import importlib.util
import sys
from collections.abc import Iterable
from pathlib import Path
from types import ModuleType


def discover_content_files(paths: Iterable[Path]) -> tuple[Path, ...]:
    result: set[Path] = set()

    for raw_path in paths:
        path = raw_path.expanduser().resolve()

        if path.is_file():
            if path.suffix == '.py':
                result.add(path)

            continue

        if not path.is_dir():
            continue

        for candidate in path.rglob('*.py'):
            relative = candidate.relative_to(path)

            # Ignore files and directories starting with "_".
            if any(
                part.startswith('_')
                for part in relative.parts
            ):
                continue

            result.add(candidate.resolve())

    return tuple(
        sorted(
            result,
            key=lambda path: path.as_posix().casefold(),
        )
    )


def _module_name(path: Path) -> str:
    digest = hashlib.sha256(
        path.as_posix().encode('utf-8')
    ).hexdigest()

    return f'_deltacards_custom_content_{digest}'


def import_content_file(path: Path) -> ModuleType:
    module_name = _module_name(path)

    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing

    spec = importlib.util.spec_from_file_location(module_name, path)
    if (spec is None) or (spec.loader is None):
        raise RuntimeError(f"Could not load custom content file {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        del sys.modules[module_name]
        raise RuntimeError(f"Could not load custom content file {path}") from exc

    return module


def load_custom_content(paths: Iterable[Path] | None = None) -> tuple[Path, ...]:
    if paths is None:
        paths = [Path.cwd() / 'custom_content']

    files = discover_content_files(paths)

    for path in files:
        import_content_file(path)

    return files
