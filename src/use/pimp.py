"""
Delegating package installation to pip, packaging and friends.
"""

import codecs
import collections
import contextlib
import importlib.machinery
import importlib.util
import inspect
import linecache
import os
import platform
import re
import sys
import tarfile
import time
import traceback
import zipfile
import zipimport
from collections.abc import Callable
from functools import lru_cache as cache
from functools import reduce
from importlib import metadata
from importlib.machinery import ModuleSpec, SourceFileLoader
from importlib.metadata import Distribution
from itertools import chain, product, zip_longest
from logging import getLogger
from numbers import Complex, Integral, Number, Rational, Real
from pathlib import Path, PureWindowsPath, WindowsPath
from shutil import rmtree
from sqlite3 import Cursor
from subprocess import CalledProcessError, run
from types import ModuleType
from typing import Any, get_args, get_origin
from warnings import catch_warnings, filterwarnings, warn

import furl
import requests
from beartype import beartype
from furl import furl as URL
from icontract import ensure, require
from packaging import tags
from packaging.specifiers import SpecifierSet

from use import Hash, InstallationError, Modes, UnexpectedHash, VersionWarning, config
from use.hash_alphabet import hexdigest_as_JACK, num_as_hexdigest
from use.messages import UserMessage, _web_pebkac_no_hash
from use.pydantics import PyPI_Project, PyPI_Release, RegistryEntry, Version
from use.tools import pipes

log = getLogger(__name__)


class PlatformTag:
    def __init__(self, platform: str):
        self.platform = platform

    def __str__(self):
        return self.platform

    def __repr__(self):
        return f"use.PlatformTag({self.platform!r})"

    def __hash__(self):
        return hash(self.platform)

    @require(lambda self, other: isinstance(other, self.__class__))
    def __eq__(self, other):
        return self.platform == other.platform


@beartype
def _ensure_version(
    result: ModuleType | Exception, *, name, requested_version, **kwargs
) -> ModuleType | Exception:
    if not isinstance(result, ModuleType):
        return result
    result_version = _get_version(mod=result)
    if result_version != requested_version:
        warn(
            UserMessage.version_warning(name, requested_version, result_version),
            category=VersionWarning,
        )
    return result


# fmt: off
@pipes
def _ensure_path(value: bytes| str| furl.Path | Path) -> Path:
    if isinstance(value, (str, bytes)):
        return Path(value).absolute()
    if isinstance(value, furl.Path):
        return (
            Path.cwd(),
            value.segments
            << map(Path)
            << tuple
            << reduce(Path.__truediv__),
        ) << reduce(Path.__truediv__)
    return value
# fmt: on


@cache
@beartype
def get_supported() -> frozenset[PlatformTag]:  # cov: exclude
    """
    Results of this function are cached. They are expensive to
    compute, thanks to some heavyweight usual players
    (*ahem* pip, package_resources, packaging.tags *cough*)
    whose modules are notoriously resource-hungry.

    Returns a set containing all platform
    supported on the current system.
    """
    get_supported = None
    with catch_warnings():
        filterwarnings(action="ignore", category=DeprecationWarning)
        with contextlib.suppress(ImportError):
            from pip._internal.resolution.legacy.resolver import get_supported
        if not get_supported:
            with contextlib.suppress(ImportError):
                from pip._internal.models.target_python import get_supported
        if not get_supported:
            with contextlib.suppress(ImportError):
                from pip._internal.utils.compatibility_tags import get_supported
        if not get_supported:
            with contextlib.suppress(ImportError):
                from pip._internal.resolution.resolvelib.factory import get_supported
    get_supported = get_supported or (lambda: [])

    items: list[PlatformTag] = [
        PlatformTag(platform=tag.platform) for tag in get_supported()
    ]

    # yay backwards compatibility..
    if hasattr(tags, "platform_tags"):
        items.extend(PlatformTag(platform=str(tag)) for tag in tags.platform_tags())
    else:
        items.extend(PlatformTag(platform=str(tag)) for tag in tags._platform_tags())

    return frozenset(items)


@beartype
def _filter_by_version(
    releases: list[PyPI_Release], *, version: Version
) -> list[PyPI_Release]:
    return list(filter(lambda r: r.version == version, releases))


class ZipFunctions:
    def __init__(self, artifact_path):
        self.archive = zipfile.ZipFile(artifact_path)

    def get(self):
        return (self.archive, [e.filename for e in self.archive.filelist])

    def read_entry(self, entry_name):
        with self.archive.open(entry_name) as f:
            bdata = f.read()
            text = bdata.decode("ISO-8859-1").splitlines() if len(bdata) < 8192 else ""
            return (Path(entry_name).stem, text)


class TarFunctions:
    def __init__(self, artifact_path):
        self.archive = tarfile.open(artifact_path)

    def get(self):
        return (
            self.archive,
            [m.name for m in self.archive.getmembers() if m.type == b"0"],
        )

    def read_entry(self, entry_name):
        m = self.archive.getmember(entry_name)
        with self.archive.extractfile(m) as f:
            bdata = f.read()
            text = bdata.decode("UTF-8").splitlines() if len(bdata) < 8192 else ""
            return (Path(entry_name).stem, text)


@beartype
@pipes
def archive_meta(artifact_path):
    DIST_PKG_INFO_REGEX = re.compile("(dist-info|-INFO|\\.txt$|(^|/)[A-Z0-9_-]+)$")

    if ".tar" in Path(str(artifact_path)).stem:
        functions = TarFunctions(artifact_path)
    else:
        functions = ZipFunctions(artifact_path)

    archive, names = functions.get()
    meta = (
        names << filter(DIST_PKG_INFO_REGEX.search) << map(functions.read_entry) >> dict
    )
    meta.update(
        dict(
            (lp := line.partition(": "), (lp[0].lower().replace("-", "_"), lp[2]))[-1]
            for line in meta.get("METADATA", meta.get("PKG-INFO"))
            if ": " in line
        )
    )
    name = meta.get("name", Path(artifact_path).stem.split("-")[0])
    meta["name"] = name
    if "top_level" not in meta:
        meta["top_level"] = [""]
    (
        top_level,
        name,
    ) = (meta["top_level"][0], meta["name"])
    import_name = name if top_level == name else ".".join((top_level, name))
    meta["names"] = names
    meta["import_name"] = import_name
    for relpath in sorted(
        [n for n in names if len(n) > 4 and n[-3:] == ".py"],
        key=lambda n: (
            not n.startswith(import_name),
            not n.endswith("__init__.py"),
            len(n),
        ),
    ):
        meta["import_relpath"] = relpath
        break
    else:
        meta["import_relpath"] = f"{import_name}.py"
    archive.close()
    return meta


@beartype
def _clean_sys_modules(pkg_name: str) -> None:
    for k in dict([
        (k, v)
        for k, v in list(sys.modules.items())
        if pkg_name in k.split(".")
        and (
            getattr(v, "__spec__", None) is None
            or isinstance(v, (SourceFileLoader, zipimport.zipimporter))
        )
    ]):
        if k in sys.modules:
            del sys.modules[k]


@beartype
def _pebkac_no_version(
    *,
    name: str,
    func: Callable[..., Exception | ModuleType] = None,
    Message: type,
    **kwargs,
) -> ModuleType | Exception:
    if func:
        result = func()
        if isinstance(result, (Exception, ModuleType)):
            return result
        assert False, f"{func}() returned {result!r}"

    return RuntimeWarning(Message.cant_import_no_version(name))


@beartype
@pipes
def _pebkac_no_hash(
    *,
    name: str,
    req_ver: Version,
    pkg_name: str,
    no_browser: bool,
    Message: type,
    hash_algo: Hash,
    **kwargs,
) -> RuntimeWarning:
    releases = _get_releases_from_pypi(pkg_name=pkg_name, req_ver=req_ver)
    filtered = _filter_by_platform(releases, tags=get_supported())
    ordered = _sort_releases(filtered)

    if not no_browser:
        _web_pebkac_no_hash(
            name=name,
            pkg_name=pkg_name,
            version=req_ver,
            releases=ordered,
        )

    if not ordered:
        return RuntimeWarning(Message.no_recommendation(pkg_name, req_ver))

    recommended_hash = hexdigest_as_JACK(ordered[0].digests.get(hash_algo.name))

    # for test_suggestion_works, don't remove
    print(recommended_hash)

    return RuntimeWarning(
        Message.pebkac_missing_hash(
            name=name,
            pkg_name=pkg_name,
            version=req_ver,
            recommended_hash=recommended_hash,
            no_browser=no_browser,
        )
    )


@beartype
@pipes
def _pebkac_no_version_no_hash(
    *,
    name: str,
    pkg_name: str,
    no_browser: bool,
    Message: type,
    **kwargs,
) -> Exception:
    # let's try to make an educated guess and give a useful suggestion
    proj = _get_project_from_pypi(pkg_name=pkg_name)
    if isinstance(proj, Exception):
        return proj
    releases = _get_releases(proj)

    ordered = releases >> _filter_by_platform(tags=get_supported()) >> _sort_releases
    # we tried our best, but we didn't find anything that could work

    # let's try to find *anything*
    if not ordered:
        ordered = _sort_releases(releases)
        if not ordered:
            # we tried our best..
            return RuntimeWarning(Message.pebkac_unsupported(pkg_name))

        if not no_browser:
            version = ordered[-1].version
            _web_pebkac_no_hash(
                name=name, pkg_name=pkg_name, version=version, project=proj
            )
            return RuntimeWarning(
                Message.pebkac_no_version_no_hash(
                    name=name,
                    pkg_name=pkg_name,
                    version=version,
                    no_browser=no_browser,
                )
            )

    recommended_version = ordered[0].version
    # for test_suggestion_works, don't remove (unless you want to work out the details)
    print(recommended_version)

    # we found something that could work, but it may not fit to the user's requirements
    return RuntimeWarning(
        Message.pebkac_no_version_no_hash(
            name=name,
            pkg_name=pkg_name,
            version=recommended_version,
            no_browser=no_browser,
        )
    )


@beartype
def _import_public_no_install(
    *,
    mod_name: str,
    **kwargs,
) -> Exception | ModuleType:
    return sys.modules.get(mod_name) or importlib.import_module(mod_name)


def _parse_name(name: str) -> tuple[str, str]:
    """Parse the user-provided name into a package name for installation and a module name for import.

    The package name is whatever pip would expect.
    The module name is whatever import would expect.

    Mini-DSL: / separates the package name from the module name.
    """
    if not name:
        return None, None

    def old():
        # as fallback
        match = re.match(r"(?P<pkg_name>[^/.]+)/?(?P<rest>[a-zA-Z0-9._]+)?$", name)
        assert match, f"Invalid name spec: {name!r}"
        names = match.groupdict()
        pkg_name = names["pkg_name"]
        rest = names["rest"]
        if not pkg_name:
            pkg_name = rest
        if not rest:
            rest = pkg_name
        return pkg_name

    pkg_name = None
    mod_name = ""
    if "/" in name:
        if name.count("/") > 1:
            raise ImportError(
                f"Invalid name spec: {name!r}, can't have multiple / characters as package/module separator."
            )
        pkg_name, _, mod_name = name.partition("/")
    else:
        pkg_name = old()
        mod_name = name
    return (pkg_name, mod_name)


@beartype
def _check_db_for_installation(
    *, registry=Cursor, pkg_name=str, version
) -> RegistryEntry | None:
    query = registry.execute(
        """
        SELECT
            artifact_path, installation_path, pure_python_package
        FROM distributions
        JOIN artifacts ON artifacts.id = distributions.id
        WHERE name=? AND version=?
        ORDER BY artifacts.id DESC
        """,
        (
            pkg_name,
            str(version),
        ),
    ).fetchone()
    return RegistryEntry(**query) if query else None


@beartype
def _auto_install(
    mod: ModuleType | Exception | None = None,
    *,
    pkg_name: str,
    mod_name: str,
    func: Callable[..., Exception | ModuleType] | None = None,
    req_ver: Version,
    hash_algo: Hash,
    user_provided_hashes: set[int],
    registry: Cursor,
    cleanup: bool,
    **kwargs,
) -> ModuleType | BaseException:
    """Install, if necessary, the package and import the module in any possible way.

    Args:
        user_provided_hashes (object):
    """
    if isinstance(mod, ModuleType | Exception):
        return mod

    if func:
        result = func()
        if isinstance(result, (Exception, ModuleType)):
            return result
        else:
            raise AssertionError(f"{func!r} returned {result!r}")

    if entry := _check_db_for_installation(
        registry=registry, pkg_name=pkg_name, version=req_ver
    ):
        # is there a point in checking the hashes at this point? probably not.
        if entry.pure_python_package:
            assert entry.artifact_path.exists()
            # let's not try to catch this - since this apparently already worked *at least once* - no fallback
            return zipimport.zipimporter(entry.artifact_path).load_module(mod_name)
        # else: we have an installed package, let's try to import it
        original_cwd = Path.cwd()
        assert entry.installation_path.exists()
        os.chdir(entry.installation_path)
        # with an installed package there may be weird issues we can't be sure about so let's be safe
        try:
            return _load_venv_entry(
                mod_name=mod_name,
                installation_path=entry.installation_path,
            )
        except BaseException as err:
            traceback.print_exc(file=sys.stderr)
            msg = err
        finally:
            os.chdir(original_cwd)
        return ImportError(msg)

    # else: we have to download the package and install it

    releases = _get_releases_from_pypi(pkg_name=pkg_name, req_ver=req_ver)
    if isinstance(releases, Exception):
        return releases
    # we *did* ask the user to give us hashes of artifacts that *should* work, so let's check for those.
    # We can't be sure which one of those hashes will work on this platform, so let's try all of them.
    for H in user_provided_hashes:
        log.info(f"Attempting auto-installation of <{num_as_hexdigest(H)}>...")
        url = next(
            (URL(R.url) for R in releases if H == int(R.digests[hash_algo.name], 16)),
            None,
        )

        if not url:
            return UnexpectedHash(
                f"user provided {user_provided_hashes}, do not match any of the {len(releases)} possible artifacts"
            )

        # got an url for an artifact with a hash given by the user, let's install it
        filename = url.asdict()["path"]["segments"][-1]
        artifact_path = config.packages / filename
        _download_artifact(
            artifact_path=artifact_path, url=url, hash_value=H, hash_algo=hash_algo
        )
        try:
            log.info("Attempting to install..")
            entry = _install(
                pkg_name=pkg_name,
                artifact_path=artifact_path,
                requested_version=req_ver,
                force_install=True,
            )
            # packages like tensorflow-gpu only need to be installed but nothing imported, so module name is empty
            log.info("Attempting to import...")
            mod = _load_venv_entry(
                mod_name=mod_name,
                installation_path=entry.installation_path,
            )
            log.info("Successfully imported.")
        except BaseException as err:
            msg = err  # sic
            log.error(err)
            traceback.print_exc(file=sys.stderr)
            if entry and cleanup:
                rmtree(entry.installation_path)
                assert not entry.installation_path.exists()
            continue

        _save_package_info(
            pkg_name=pkg_name,
            version=req_ver,
            artifact_path=entry.artifact_path,
            hash_value=int(
                hash_algo.value(entry.artifact_path.read_bytes()).hexdigest(), 16
            ),
            hash_algo=hash_algo,
            installation_path=entry.installation_path,
            registry=registry,
        )
        return mod
    log.critical(
        f"Could not install {pkg_name!r} {req_ver!r}. Hashes that were attempted: {[num_as_hexdigest(H) for H in user_provided_hashes]}"
    )
    return ImportError(msg)


@beartype
def _save_package_info(
    *,
    registry=Cursor,
    version: Version,
    artifact_path: Path,
    installation_path: Path,
    hash_value=int,
    hash_algo: Hash,
    pkg_name: str,
):
    """Update the registry to contain the pkg's metadata."""
    if not registry.execute(
        f"SELECT * FROM distributions WHERE name='{pkg_name}' AND version='{version}'"
    ).fetchone():
        registry.execute(
            f"""
INSERT INTO distributions (name, version, installation_path, date_of_installation, pure_python_package)
VALUES ('{pkg_name}', '{version}', '{installation_path}', {time.time()}, {installation_path is None})
"""
        )
        registry.execute(
            f"""
INSERT OR IGNORE INTO artifacts (distribution_id, artifact_path)
VALUES ({registry.lastrowid}, '{artifact_path}')
"""
        )
        registry.execute(
            f"""
INSERT OR IGNORE INTO hashes (artifact_id, algo, value)
VALUES ({registry.lastrowid}, '{hash_algo.name}', '{hash_value}')"""
        )
    registry.connection.commit()


@beartype
@ensure(lambda url: str(url).startswith("http"))
def _download_artifact(
    *, artifact_path: Path, url: URL, hash_algo: Hash, hash_value: int
):
    # let's check if we downloaded it already, just in case
    if (
        artifact_path.exists()
        and int(hash_algo.value(artifact_path.read_bytes()).hexdigest(), 16)
        == hash_value
    ):
        log.info("Artifact already downloaded. Hashes matching.")
        return
    # this should work since we just got the url from pypi itself - if this fails, we have bigger problems
    log.info("Downloading artifact from PyPI...")
    data = requests.get(url).content
    artifact_path.write_bytes(data)
    if int(hash_algo.value(artifact_path.read_bytes()).hexdigest(), 16) != hash_value:
        # let's try once again, cosmic rays and all, believing in pure dumb luck
        log.info("Artifact downloaded but hashes don't match. Trying again...")
        data = requests.get(url).content
        artifact_path.write_bytes(data)
    if int(hash_algo.value(artifact_path.read_bytes()).hexdigest(), 16) != hash_value:
        # this means either PyPI is hacked or there is a man-in-the-middle
        raise ImportError(
            "Hashes don't match. Aborting. Something very fishy is going on."
        )
    log.info("Download successful.")
    return


@beartype
def _is_pure_python_package(artifact_path: Path, meta: dict) -> bool:
    return next(
        (
            False
            for n, s in product(meta["names"], importlib.machinery.EXTENSION_SUFFIXES)
            if n.endswith(s)
        ),
        ".tar" not in str(artifact_path),
    )


@beartype
def _find_module_in_venv(pkg_name: str, version: Version, relp: str) -> Path:
    env_dir = config.venv / pkg_name / str(version)
    log.debug("env_dir=%s", env_dir)
    site_dirs = [
        env_dir / f"Lib{suffix}" / "site-packages"
        if sys.platform == "win32"
        else env_dir
        / f"lib{suffix}"
        / ("python%d.%d" % sys.version_info[:2])
        / "site-packages"
        for suffix in ("64", "")
    ]
    log.debug("site_dirs=%s", site_dirs)
    for p in env_dir.glob("**/*"):
        log.debug("  - %s", p.relative_to(env_dir).as_posix())

    original_sys_path = sys.path
    try:
        # Need strings for sys.path to work
        sys.path = [*map(str, site_dirs), *sys.path]
        sys.path_importer_cache.clear()
        importlib.invalidate_caches()
        # sic! importlib uses sys.path for lookup
        dist = Distribution.from_name(pkg_name)
        log.info("dist=%s", dist)
        log.debug("dist.files=%s", dist.files)
        for path in dist.files:
            log.debug("path=%s", path)
            file = dist.locate_file(path)
            log.debug("file=%s", file)
            if not file.exists():
                continue
            real_file = Path(*file.parts[: -len(path.parts)])
            log.debug("real_file=%s", real_file)
            if real_file.exists():
                return real_file

    finally:
        sys.path = original_sys_path
    raise ImportError("No module in site_dirs")


@beartype
def _install(
    *,
    pkg_name: str,
    requested_version: Version = None,
    force_install=False,
    artifact_path: Path,
) -> RegistryEntry:
    """Take care of the installation."""
    meta = archive_meta(artifact_path)
    import_parts = re.split("[\\\\/]", meta["import_relpath"])
    if "__init__.py" in import_parts:
        import_parts.remove("__init__.py")
    relp: str = meta["import_relpath"]
    venv_root = config.venv / pkg_name / str(requested_version)
    site_pkgs_dir = list(venv_root.rglob("site-packages"))
    if not any(site_pkgs_dir):
        force_install = True
        module_paths = []
    else:
        installation_path = site_pkgs_dir[0]
        module_paths = venv_root.rglob(f"**/{relp}")
        for path in module_paths:
            path.chmod(0o700)

    python_exe = Path(sys.executable)

    if not module_paths or force_install:
        # If we get here, the venv/pip setup is required.
        # we catch errors one level higher, so we don't have to deal with them here
        env = {}
        _realenv = {
            k: v
            for k, v in chain(os.environ.items(), env.items())
            if isinstance(k, str) and isinstance(v, str)
        }

        argv = [
            python_exe,
            "-m",
            "pip",
            "--disable-pip-version-check",
            "--no-color",
            "--verbose",
            "--verbose",
            "install",
            "--pre",
            "--root",
            PureWindowsPath(venv_root).drive
            if isinstance(venv_root, (WindowsPath, PureWindowsPath))
            else "/",
            "--prefix",
            str(venv_root),
            "--progress-bar",
            "on",
            "--prefer-binary",
            "--exists-action",
            "i",
            "--ignore-installed",
            "--no-warn-script-location",
            "--force-reinstall",
            "--no-warn-conflicts",
            artifact_path,
        ]
        try:
            setup = dict(
                executable=python_exe,
                args=[*map(str, argv)],
                bufsize=1024,
                input="",
                capture_output=False,
                timeout=45000,
                check=True,
                close_fds=True,
                env=_realenv,
                encoding="ISO-8859-1",
                errors="ISO-8859-1",
                text=True,
                shell=False,
            )
        except CalledProcessError as err:
            log.error("::".join(err.cmd, err.output, err.stdout, err.stderr))
            raise InstallationError(err) from err
        run(**setup)
        log.info("Installation successful.")

    installation_path = _find_module_in_venv(
        pkg_name=pkg_name, version=requested_version, relp=relp
    )

    return RegistryEntry(
        installation_path=installation_path,
        artifact_path=artifact_path,
        pure_python_package=False,
    )


@beartype
def _load_venv_entry(*, mod_name: str, installation_path: Path) -> ModuleType:
    if not mod_name:
        log.info("Module name is empty, returning empty Module.")
        return ModuleType("")
    origcwd = Path.cwd()
    original_sys_path = list(sys.path)
    # TODO we need to keep track of package-specific sys-paths
    if sys.path[0] != "":
        sys.path.insert(0, "")
    try:
        os.chdir(installation_path)
        # importlib and sys.path.. bleh
        return importlib.import_module(mod_name)
    except BaseException as err:
        msg = err
        log.error(msg)
        traceback.print_exc(file=sys.stderr)
    finally:
        os.chdir(origcwd)
        sys.path = original_sys_path
    raise ImportError(msg)


@beartype
def _get_project_from_pypi(*, pkg_name: str) -> PyPI_Project | Exception:
    # let's check if package name is correct
    url = f"https://pypi.org/pypi/{pkg_name}/json"
    response = requests.get(url)
    if response.status_code == 404:
        return ImportError(UserMessage.pebkac_unsupported(pkg_name))
    elif response.status_code != 200:
        return RuntimeWarning(UserMessage.web_error(url, response))
    return PyPI_Project(**response.json())


@beartype
def _get_releases_from_pypi(
    *, pkg_name: str, req_ver: Version
) -> list[PyPI_Release] | Exception:
    # let's check if package name is correct
    response = requests.get(url := f"https://pypi.org/pypi/{pkg_name}")
    if response.status_code == 404:
        return ImportError(UserMessage.pebkac_unsupported(pkg_name))
    elif response.status_code != 200:
        return RuntimeWarning(UserMessage.web_error(url, response))
    # let's check if the version is a thing
    response = requests.get(url := f"https://pypi.org/pypi/{pkg_name}/{req_ver}/json")
    if response.status_code == 404:
        return RuntimeWarning(UserMessage.bad_version_given(pkg_name, req_ver))
    # looks good, let's get the releases for this version
    urls = response.json()["urls"]
    releases = [PyPI_Release(**url, version=req_ver) for url in urls]
    return releases


@beartype
def _filter_by_platform(
    releases: list[PyPI_Release], *, tags: frozenset[PlatformTag]
) -> list[PyPI_Release]:
    def compatible(info: PyPI_Release, include_sdist=False) -> bool:
        return (
            _is_platform_compatible(info, tags, include_sdist)
            and not info.yanked
            and (include_sdist or info.justuse.ext not in ("tar", "tar.gz" "zip"))
        )

    filtered = [
        release for release in releases if compatible(release, include_sdist=False)
    ]
    return filtered or [
        release for release in releases if compatible(release, include_sdist=True)
    ]


@beartype
def _get_releases(project: PyPI_Project) -> list[PyPI_Release]:
    return reduce(list.__add__, project.releases.values(), [])


@beartype
@pipes
def _sort_releases(releases: list[PyPI_Release]) -> list[PyPI_Release]:
    return sorted(
        releases,
        key=(
            lambda r: (
                1 - int(r.filename.endswith(".tar.gz")),
                1 - int(r.is_sdist),
                r.version,
            )
        ),
        reverse=True,
    )


@cache
def _is_version_satisfied(specifier: str, sys_version) -> bool:
    """
    SpecifierSet("") matches anything, no need to artificially
    lock down versions at this point

    @see https://warehouse.readthedocs.io/api-reference/json.html
    @see https://packaging.pypa.io/en/latest/specifiers.html
    """
    specifiers = SpecifierSet(specifier or "")
    return not specifier or sys_version in specifiers


@beartype
@pipes
def _is_platform_compatible(
    info: PyPI_Release, platform_tags: frozenset[PlatformTag], include_sdist=False
) -> bool:
    if not include_sdist and (
        ".tar" in info.justuse.ext or info.justuse.python_tag in ("cpsource", "sdist")
    ):
        return False

    if "win" in (info.packagetype or "unknown") and sys.platform != "win32":
        return False

    if info.platform_tag:
        if "win32" in info.platform_tag and sys.platform != "win32":
            return False
        if "macosx" in info.platform_tag and sys.platform != "darwin":
            return False

    our_python_tag = tags.interpreter_name() + tags.interpreter_version()
    supported_tags = {
        our_python_tag,
        "py3",
        "cp3",
        f"cp{tags.interpreter_version()}",
        f"py{tags.interpreter_version()}",
    }

    if info.platform_tag:
        given_platform_tags = (
            info.platform_tag.split(".") << map(PlatformTag) >> frozenset
        )
    else:
        return include_sdist

    if info.is_sdist and info.requires_python:
        given_python_tag = {
            our_python_tag
            for p in info.requires_python.split(",")
            if Version(platform.python_version()) in SpecifierSet(p)
        }
    else:
        given_python_tag = set(info.python_tag.split("."))

    return any(supported_tags.intersection(given_python_tag)) and (
        (info.is_sdist and include_sdist)
        or any(given_platform_tags.intersection(platform_tags))
    )


@beartype
def _get_version(name: str | None = None, pkg_name=None, /, mod=None) -> Version | None:
    version: Callable[...] | Version | str | None = None
    for lookup_name in (name, pkg_name):
        if not lookup_name:
            continue
        try:
            if lookup_name is not None:
                meta = metadata.distribution(lookup_name)
                return Version(meta.version)
        except metadata.PackageNotFoundError:
            continue
    if not mod:
        return None
    version = getattr(mod, "__version__", version)
    if isinstance(version, str):
        return Version(version)
    version = getattr(mod, "version", version)
    if callable(version):
        version = version()
    return Version(version)


def _build_mod(
    *,
    mod_name,
    code: bytes,
    initial_globals: dict[str, Any] | None,
    module_path,
    pkg_name="",
) -> ModuleType:
    mod = ModuleType(mod_name)
    log.info(f"{Path.cwd()=} {pkg_name=} {mod_name=} {module_path=}")
    mod.__dict__.update(initial_globals or {})
    mod.__file__ = str(module_path)
    mod.__path__ = [str(module_path.parent)]
    mod.__package__ = pkg_name
    mod.__name__ = mod_name
    loader = SourceFileLoader(mod_name, str(module_path))
    mod.__loader__ = loader
    mod.__spec__ = ModuleSpec(mod_name, loader)
    code_text = codecs.decode(code)
    # module file "<", ">" chars are specially handled by inspect
    getattr(linecache, "cache")[module_path] = (
        len(code),  # size of source code
        None,  # last modified time; None means there is no physical file
        [
            *map(lambda ln: ln + "\x0a", code_text.splitlines())
        ],  # a list of lines, including trailing newline on each
        mod.__file__,  # file name, e.g. "<mymodule>" or the actual path to the file
    )
    # not catching this causes the most irritating bugs ever!
    try:
        codeobj = compile(code, module_path, "exec")
        exec(codeobj, mod.__dict__)
    except:  # reraise anything without handling - clean and simple.
        raise
    return mod


def _fail_or_default(exception: BaseException, default: Any):
    if default is not Modes.fastfail:
        return default
    else:
        raise exception


def _real_path(
    *, path: Path, _applied_decorators: dict, landmark
) -> tuple[str, str, str, Path]:
    source_dir = Path.cwd()
    # calling from another use()d module
    # let's see where we started
    main_mod = __import__("__main__")
    # there are a number of ways to call use() from a non-use() starting point
    # let's first check if we are running in jupyter
    jupyter = "ipykernel" in sys.modules
    # we're in jupyter, we use the CWD as set in the notebook
    if not jupyter and hasattr(main_mod, "__file__"):
        # problem: user wants to use.Path("some_file_in_the_same_dir")
        # so we have to figure out where the file of the calling function is.
        # but the *calling* function could also be a decorator, living completely elsewhere
        # so we have to figure out whether we're being called by a decorator first.
        # We use use.__call__ as landmark, because that's the official entry point
        # and we can count on it being called. From there we need to check whether it was aspectized.
        # If it was, we need to skip those decorators before finally get to the user code and
        # we can actually see from where we've been called.
        frame = inspect.currentframe()

        while True:
            if frame.f_code == landmark:
                break
            else:
                frame = frame.f_back
        # a few more steps..
        # BUG: somehow this doesn't work anymore - aspectizing is broken!
        # for _ in _applied_decorators[landmark]:
        #    frame = frame.f_back
        try:
            # frame is in __call__ (or rather methdispatch), we need to step two frames back
            source_dir = Path(frame.f_back.f_back.f_code.co_filename).resolve().parent
        # we are being called from a shell like thonny, so we have to assume cwd
        except OSError:
            source_dir = Path.cwd()

    if source_dir is None:
        if main_mod.__loader__ and hasattr(main_mod.__loader__, "path"):
            source_dir = _ensure_path(main_mod.__loader__.path).parent
        else:
            source_dir = Path.cwd()
    if not source_dir.joinpath(path).exists():
        if files := [*[*source_dir.rglob(f"**/{path}")]]:
            source_dir = _ensure_path(files[0]).parent
        else:
            source_dir = Path.cwd()
    if not source_dir.exists():
        raise NotImplementedError(
            "Can't determine a relative path from a virtual file."
        )
    if not path.exists():
        path = source_dir.joinpath(path).resolve()
    if not path.exists():
        raise ImportError(f"Sure '{path}' exists?")
    if not path.is_absolute():
        path = path.resolve()
    try:
        name = path.relative_to(source_dir)
    except ValueError:
        source_dir = path.parent
        os.chdir(source_dir)
        name = path.relative_to(source_dir)
    ext = name.as_posix().rpartition(".")[-1]
    name_as_path_with_ext = name.as_posix()
    name_as_path = name_as_path_with_ext[: -len(ext) - (1 if ext else 0)]
    name = name_as_path.replace("/", ".")
    name_parts = name.split(".")
    pkg_name = ".".join(name_parts[:-1])
    mod_name = path.stem  # sic!

    return name, mod_name, pkg_name, path


numerics = [bool, Integral, Rational, Real, Complex]


class NotComparableWarning(UserWarning):
    pass


def _modules_are_compatible(pre, post):
    for name, pre_obj in pre.__dict__.items():
        if callable(pre_obj):
            try:
                post_obj = getattr(post, name)
            except AttributeError:
                return False
            if _is_compatible(pre_obj, post_obj):
                continue
            else:
                return False
    return True


def _is_compatible(pre, post):
    sig = inspect.signature(pre)
    # first separate args and kwargs so we can sort kwargs alphabetically
    args = []
    kwargs = []

    for k, v in sig.parameters.items():
        if v.kind is v.VAR_KEYWORD or v.POSITIONAL_OR_KEYWORD:
            kwargs.append((k, v))
        else:
            args.append((k, v))

    pre_sig = []
    v = _extracted_from__is_compatible_(args, pre_sig, kwargs, sig)
    sig = inspect.signature(post)
    post_sig = []

    args = []
    kwargs = []

    for k, v in sig.parameters.items():
        if v.kind is v.VAR_KEYWORD or v.POSITIONAL_OR_KEYWORD:
            kwargs.append((k, v))
        else:
            args.append((k, v))

    v = _extracted_from__is_compatible_(args, post_sig, kwargs, sig)
    return all(_check(x, y) for x, y in zip_longest(pre_sig, post_sig, fillvalue=Any))


def _is_builtin(name: str) -> bool:
    if name in sys.builtin_module_names:
        return True
    spec = importlib.util.find_spec(name)
    return (
        spec is not None
        and spec.origin is not None
        and "site-packages" not in spec.origin
    )


# TODO Rename this here and in `_is_compatible`
def _extracted_from__is_compatible_(args, arg1, kwargs, sig):
    for k, result in args:
        result = result.annotation
        arg1.append(result if result is not inspect._empty else Any)

    for k, result in sorted(kwargs):
        result = result.annotation
        arg1.append(result if result is not inspect._empty else Any)

    result = sig.return_annotation
    arg1.append(result if result is not inspect._empty else Any)

    return result


def _check(x, y):
    if config.debugging:
        print(
            f"checking:\n  "
            f"{x!r:<30} "
            f"({type(x).__module__}.{type(x).__qualname__})\n  "
            f"{y!r:<30} "
            f"({type(y).__module__}.{type(y).__qualname__})"
        )

    # narrowing {(Any => Any) | (Any => something)} is OK
    if x is Any:
        return True
    # broadening (something => Any) is NOK
    if y is Any:
        return False

    # now to the more specific cases (something => something else)
    with contextlib.suppress(
        TypeError
    ):  # issubclass is allergic to container classes (types.GenericAlias)
        # let's first check if we're dealing with numbers
        if issubclass(x, Number) and issubclass(y, Number):
            # since the generic implementations aren't actual subclasses of each other
            # we have to map to the numeric tower classes
            for X in numerics:
                if issubclass(x, X):
                    break
            x = X
            for Y in numerics:
                if issubclass(y, Y):
                    break
            y = Y
    # Need to do this *before* we access `__name__`
    X = get_origin(x) or x
    Y = get_origin(y) or y

    # the other important type hierarchy are
    # containers
    # let's check if the user is using typing
    # classes and educate them to use
    # collections.abc instead
    for name, t in {"X": X, "Y": Y}.items():
        if t.__module__ != "typing":
            continue
        tca = getattr(collections.abc, t.__name__, 0)
        if not tca:
            continue
        warn(
            NotComparableWarning(
                f"{t} is of a type from the typing "
                " module, which can't be compared. "
                "Please use a type from the "
                "`collections.abc` module (`{tca!r}`)."
            )
        )
        locals().__setitem__(name, tca)

    if X is not None and Y is not None:
        # (Sequence => list) is OK, (list => Sequence) is NOK
        return (
            all(
                _check(x_, y_)
                for x_, y_ in zip_longest(get_args(x), get_args(y), fillvalue=Any)
            )
            if issubclass(Y, X)
            else False
        )

    try:
        # (x => y) where y is not a subclass of x is NOK
        return issubclass(y, x)
    except TypeError:  # (int => list[int]) or (list[int] => int) NOK
        return False


# function to run code in a jupyter notebook sandbox
def run_in_notebook(code):
    """Run code in a jupyter notebook sandbox.

    This function is useful to run code in a jupyter notebook
    without having to run the notebook server.

    Parameters
    ----------
    code : str
        The code to run.

    Returns
    -------
    None

    """
    from IPython.display import Javascript, display

    display(Javascript(f"IPython.notebook.kernel.execute('{code}')"))


def module_from_pyc(mod_name: str, path: Path, initial_globals: dict):
    """Create a module from a pyc file.

    Parameters
    ----------
    mod_name : str
        The name of the module.
    path : Path
        The path to the pyc file.
    initial_globals : dict
        The initial globals to pass to the module.

    Returns
    -------
    module
        The module

    """
    initial_globals = initial_globals or {}
    log.info(f"{Path.cwd()=} {mod_name=} {path=}")
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    mod.__dict__.update(initial_globals)
    spec.loader.exec_module(mod)
    return mod
