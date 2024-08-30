import importlib.metadata
import contextlib

with contextlib.suppress(importlib.metadata.PackageNotFoundError):
    installed_version = None
    installed_version = importlib.metadata.version("foobar")