"""
Main classes that act as API for the user to interact with.
"""


import asyncio
import atexit
import hashlib
import importlib.util
import inspect
import os
import shutil
import sqlite3
import sys
import threading
import time
import traceback
from collections import namedtuple
from collections.abc import Callable
from datetime import datetime
from logging import DEBUG, INFO, NOTSET, getLogger, root
from pathlib import Path
from types import ModuleType
from typing import Any, Optional, Union
from warnings import warn

import requests
from furl import furl as URL
from icontract import require

from use import (
    AmbiguityWarning,
    Hash,
    Modes,
    NotReloadableWarning,
    NoValidationWarning,
    UnexpectedHash,
    VersionWarning,
    __version__,
    buffet_table,
    config,
    home,
    sessionID,
)
from use.aspectizing import _applied_decorators, apply_aspect
from use.hash_alphabet import JACK_as_num, is_JACK, num_as_hexdigest
from use.messages import KwargMessage, StrMessage, TupleMessage, UserMessage
from use.pimp import (
    _build_mod,
    _ensure_path,
    _fail_or_default,
    _modules_are_compatible,
    _parse_name,
    _real_path,
)
from use.pydantics import Version, git
from use.tools import methdispatch

log = getLogger(__name__)

# internal subpackage imports
test_version: str = locals().get("test_version")

_reloaders: dict["ProxyModule", "ModuleReloader"] = {}  # ProxyModule:Reloader
_using = {}

# sometimes all you need is a sledge hammer..
def _release_locks():
    for _ in range(2):
        [lock.unlock() for lock in threading._shutdown_locks]
        [reloader.stop() for reloader in _reloaders.values()]
    log.info(f"### SESSION END {datetime.now().strftime('%Y/%m/%d %H:%M:%S')} {sessionID} ###")


atexit.register(_release_locks)

ModInUse = namedtuple("ModInUse", "name mod path spec")


class ProxyModule(ModuleType):
    def __init__(self, mod):
        self.__implementation = mod
        self.__condition = threading.RLock()

    def __getattribute__(self, name):
        if name in (
            "_ProxyModule__implementation",
            "_ProxyModule__condition",
            "",
            "__class__",
            "__metaclass__",
            "__instancecheck__",
        ):
            return object.__getattribute__(self, name)
        with self.__condition:
            return getattr(self.__implementation, name)

    def __setattr__(self, name, value):
        if name in (
            "_ProxyModule__implementation",
            "_ProxyModule__condition",
        ):
            object.__setattr__(self, name, value)
            return
        with self.__condition:
            setattr(self.__implementation, name, value)

    def __matmul__(self, other: Callable):
        thing = self.__implementation
        if not other:
            raise NotImplementedError

        # a little hack in order to be able to do `use @ numpy`...
        if isinstance(self.__implementation, Use):
            thing = other

            def some_decorator(x):
                return x

            other = some_decorator

        assert isinstance(other, Callable)

        kwargs = {
            "excluded_types": {
                ProxyModule,
            },
            "dry_run": True,
        }

        return apply_aspect(thing, other, **kwargs)

    def __call__(self, *args, **kwargs):
        with self.__condition:
            return self.__implementation(*args, **kwargs)

    # to allow `numpy @ use` for a quick check
    def __rmatmul__(self, *args, **kwargs):
        return ProxyModule.__matmul__(self, *args, **kwargs)


class ModuleReloader:
    def __init__(self, *, proxy, name, path, package_name, initial_globals):
        self.proxy = proxy
        "ProxyModula that we refer to."
        self.name = name
        self.path = path
        self.package_name = package_name
        self.initial_globals = initial_globals
        self._condition = threading.RLock()
        self._stopped = True
        self._thread = None

    def start_async(self):
        loop = asyncio.get_running_loop()
        loop.create_task(self.run_async())

    @require(lambda self: self._thread is None or self._thread.is_alive())
    def start_threaded(self):
        self._stopped = False
        atexit.register(self.stop)
        self._thread = threading.Thread(target=self.run_threaded, name=f"reloader__{self.name}")
        self._thread.start()

    async def run_async(self):
        last_filehash = None
        while not self._stopped:
            with open(self.path, "rb") as file:
                code = file.read()
            current_filehash = hashlib.blake2b(code).hexdigest()
            if current_filehash != last_filehash:
                try:
                    mod = _build_mod(
                        module_name=self.name,
                        code=code,
                        initial_globals=self.initial_globals,
                        module_path=self.path.resolve(),
                    )
                    if not _modules_are_compatible(self.proxy, mod):
                        continue
                    self.proxy.__implementation = mod
                except KeyError:
                    traceback.print_exc()
            last_filehash = current_filehash
            await asyncio.sleep(1)

    def run_threaded(self):
        last_filehash = None
        while not self._stopped:
            with self._condition:
                with open(self.path, "rb") as file:
                    code = file.read()
                current_filehash = hashlib.blake2b(code).hexdigest()
                if current_filehash != last_filehash:
                    try:
                        mod = _build_mod(
                            module_name=self.name,
                            code=code,
                            initial_globals=self.initial_globals,
                            module_path=self.path,
                        )
                        if not _modules_are_compatible(self.proxy, mod):
                            continue
                        self.proxy._ProxyModule__implementation = mod
                    except KeyError:
                        traceback.print_exc()
                last_filehash = current_filehash
            time.sleep(1)

    def stop(self):
        self._stopped = True

    def __del__(self):
        self.stop()


class Use(ModuleType):
    """
    Welcome to the world of use

    """

    def __init__(self):
        self._using = _using
        # might run into issues during testing otherwise
        self.registry = self._set_up_registry()
        "Registry sqlite DB to store all relevant package metadata."

        if config.debugging:
            root.setLevel(DEBUG)

        if config.version_warning:
            try:
                response = requests.get("https://pypi.org/pypi/justuse/json")
                "Checking if there's a new version of justuse."
                data = response.json()
                max_version = max(Version(version) for version in data["releases"].keys())
                if Version(__version__) < max_version:
                    warn(
                        UserMessage.use_version_warning(max_version),
                        VersionWarning,
                    )
            except (KeyError, requests.exceptions.ConnectionError):
                if test_version:
                    raise
                log.error(
                    traceback.format_exc()
                )  # we really don't need to bug the user about this (either pypi is down or internet is broken)

    def clean_slate(self):
        shutil.rmtree(config.venv, ignore_errors=True)
        shutil.rmtree(config.packages, ignore_errors=True)
        config.venv.mkdir(mode=0o755, exist_ok=True)
        config.packages.mkdir(mode=0o755, parents=True, exist_ok=True)
        self.recreate_registry()

    def _set_up_registry(self, *, registry=None, path: Optional[Path] = None):
        # recreating reuses the registry connection and file
        if registry is None:
            if path or test_version and "DB_TEST" not in os.environ:
                registry = sqlite3.connect(path or ":memory:").cursor()
            else:
                try:
                    registry = sqlite3.connect(home / "registry.db").cursor()
                except Exception as e:
                    raise RuntimeError(UserMessage.couldnt_connect_to_db(e)) from e
        registry.row_factory = lambda cursor, row: {
            col[0]: row[idx] for idx, col in enumerate(cursor.description)
        }
        registry.execute("PRAGMA foreign_keys=ON")
        registry.execute("PRAGMA auto_vacuum = FULL")
        registry.executescript(
            """
CREATE TABLE IF NOT EXISTS "artifacts" (
	"id"    INTEGER,
	"distribution_id"   INTEGER,
	"import_relpath" TEXT,
	"artifact_path" TEXT,
  "module_path" TEXT,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("distribution_id") REFERENCES "distributions"("id") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "distributions" (
	"id"    INTEGER,
	"name"  TEXT NOT NULL,
	"version"   TEXT NOT NULL,
	"installation_path" TEXT,
	"date_of_installation"  INTEGER,
	"number_of_uses"    INTEGER,
	"date_of_last_use"  INTEGER,
	"pure_python_package"   INTEGER NOT NULL DEFAULT 1,
	PRIMARY KEY("id" AUTOINCREMENT)
);

CREATE TABLE IF NOT EXISTS "hashes" (
	"algo"  TEXT NOT NULL,
	"value" INTEGER NOT NULL,
	"artifact_id"   INTEGER NOT NULL,
	PRIMARY KEY("algo","value"),
	FOREIGN KEY("artifact_id") REFERENCES "artifacts"("id") ON DELETE CASCADE
);
		"""
        )
        registry.connection.commit()
        return registry

    def recreate_registry(self):
        number_of_backups = len(list(home.glob("registry.db*")))
        shutil.copyfile(home / "registry.db", home / f"registry.db.{number_of_backups}.bak")
        self._clear_registry()
        self._set_up_registry(registry=self.registry)
        self.cleanup()

    def _clear_registry(self):
        for table in self.registry.execute("SELECT name FROM sqlite_schema WHERE type='table';").fetchall():
            if table["name"] == "sqlite_sequence":
                continue
            self.registry.execute(f"DROP TABLE {table['name']};")
            self.registry.connection.commit()

    def install(self):
        # yeah, really.. __builtins__ sometimes appears as a dict and other times as a module, don't ask me why
        if isinstance(__builtins__, dict):
            __builtins__["use"] = self
        elif isinstance(__builtins__, ModuleType):
            setattr(__builtins__, "use", self)
        else:
            raise RuntimeWarning("__builtins__ is something unexpected")

    def uninstall(self):
        if isinstance(__builtins__, dict):
            if "use" in __builtins__:
                del __builtins__["use"]
        elif isinstance(__builtins__, ModuleType):
            if hasattr(__builtins__, "use"):
                delattr(__builtins__, "use")
        else:
            raise RuntimeWarning("__builtins__ is something unexpected")

    def del_entry(self, name, version):
        # TODO: CASCADE to artifacts etc
        self.registry.execute(
            "DELETE FROM hashes WHERE artifact_id IN (SELECT id FROM artifacts WHERE distribution_id IN (SELECT id FROM distributions WHERE name=? AND version=?))",
            (name, str(version)),
        )
        self.registry.execute(
            "DELETE FROM artifacts WHERE distribution_id IN (SELECT id FROM distributions WHERE name=? AND version=?)",
            (name, str(version)),
        )
        self.registry.execute("DELETE FROM distributions WHERE name=? AND version=?", (name, str(version)))
        self.registry.connection.commit()

    def cleanup(self):
        """Bring registry and downloaded packages in sync.

        First all packages are removed that don't have a matching registry entry, then all registry entries that don't have a matching pkg.
        """

        def delete_folder(path):
            for sub in path.iterdir():
                if sub.is_dir():
                    delete_folder(sub)
                else:
                    sub.unlink()
            path.rmdir()

        for name, version, artifact_path, installation_path in self.registry.execute(
            "SELECT name, version, artifact_path, installation_path FROM distributions JOIN artifacts on distributions.id = distribution_id"
        ).fetchall():
            if not (_ensure_path(artifact_path).exists() and _ensure_path(installation_path).exists()):
                self.del_entry(name, version)
        self.registry.connection.commit()

    def _set_mod(self, *, name, mod, path=None, spec=None):
        """Helper to get the order right."""
        self._using[name] = ModInUse(name, mod, path, spec)

    @methdispatch
    def __call__(self, thing, /, *args, **kwargs):
        raise NotImplementedError(UserMessage.cant_use(thing))

    @require(lambda hash_algo: hash_algo in Hash)
    @require(lambda as_import: as_import.isidentifier())
    @__call__.register(URL)
    def _use_url(
        self,
        url: URL,
        /,
        *,
        hash_algo=Hash.sha256,
        hash_value=None,
        initial_globals: Optional[dict[Any, Any]] = None,
        import_as: str = None,
        default=Modes.fastfail,
        modes=0,
    ) -> ProxyModule:
        """
        Import a module from a web source.

        >>> load = use(
                use.URL("https://raw.githubusercontent.com/amogorkon/stay/master/src/stay/stay.py"), modes=use.recklessness
                , import_as="stay").Decoder()
        >>> for x in load("a: b"): x
        {'a': 'b'}

        Args:
            url (URL): a web url, wrapped with use.URL()
            hash_algo (_type_, optional): Hash algo used to check. Defaults to Hash.sha256.
            hash_value (_type_, optional): Hash value used to pin the content. Defaults to None.
            initial_globals (Optional[dict[Any, Any]], optional): Any globals passed into the module. Defaults to None.
            import_as (str, optional): Valid identifier which should be used for "importing" -
                means the module can be imported anywhere else using this name. Defaults to None.
            default (_type_, optional): Any value (like a different module) in case importing fails. Defaults to Modes.fastfail.
            modes (int, optional):
                * use.recklessness - to skip hash validation


        Raises:
            ImportError: If no default is given, return ImportError if the module cannot be imported

        Returns:
            ProxyModule: the module wrapped with use.ProxyModule for convenience
        """
        log.debug(f"use-url: {url}")
        reckless = Modes.recklessness & modes

        response = requests.get(str(url))
        if response.status_code != 200:
            raise ImportError(UserMessage.web_error(url, response))
        this_hash = hash_algo.value(response.content).hexdigest()

        if hash_value and not reckless:
            if this_hash != hash_value:
                return _fail_or_default(
                    UnexpectedHash(f"{this_hash} does not match the expected hash {hash_value} - aborting!"),
                    default,
                )
        else:
            warn(UserMessage.no_validation(url, hash_algo, this_hash), NoValidationWarning)

        name = url.path.segments[-1]
        path = config.web_modules / f"{name}_{int(time.time())}"
        path.touch(mode=0o755)
        with open(path, "wb") as file:
            file.write(response.content)

        if import_as:
            assert import_as.islower(), f"import-as must be all lowercase, not {import_as}"
            assert import_as.isidentifier(), f"expected identifier, not {import_as}"
            assert (
                import_as not in sys.modules
            ), f"already imported some other module with the identifier {import_as}"
        try:
            mod = _build_mod(
                module_name=import_as or name,
                code=response.content,
                module_path=path,
                initial_globals=initial_globals,
            )
        except KeyError:
            raise
        if exc := None:
            return _fail_or_default(ImportError(exc), default)
        mod = ProxyModule(mod)
        if import_as:
            sys.modules[import_as] = mod

        return mod

    @__call__.register(git)
    def _use_git(
        self,
        git_repo: git,
        /,
        *,
        modes=0,
    ) -> ProxyModule:
        """Install git repo."""

    @__call__.register(Path)
    def _use_path(
        self,
        path,
        /,
        *,
        initial_globals=None,
        import_as: str = None,
        default=Modes.fastfail,
        modes=0,
    ) -> ProxyModule:
        """Import a module from a path.

        https://github.com/amogorkon/justuse/wiki/Use-Path

        Args:
                path ([type]): must be a pathlib.Path
                initial_globals ([type], optional): dict that should be globally available to the module before executing it. Defaults to None.
                default ([type], optional): Return instead if an exception is encountered.
                modes (int, optional): [description]. Defaults to 0; Acceptable mode for this variant: use.reloading.

        Returns:
                Optional[ModuleType]: The module if it was imported, otherwise whatever was specified as default.
        """
        initial_globals = initial_globals or {}
        if import_as:
            assert import_as.isidentifier()
            assert import_as not in sys.modules

        reloading = bool(Use.reloading & modes)

        exc = None
        mod = None
        original_cwd = Path.cwd()

        if path.is_dir():
            return _fail_or_default(ImportError(f"Can't import directory {path}"), default)

        try:
            name, module_name, package_name, path = _real_path(
                path=path, _applied_decorators=_applied_decorators, landmark=Use.__call__.__code__
            )
        except (NotImplementedError, ImportError):
            exc = traceback.format_exc()

        with open(path, "rb") as rfile:
            code = rfile.read()
        try:
            mod = _build_mod(
                module_name=module_name,
                code=code,
                initial_globals=initial_globals,
                module_path=path,
                package_name=package_name,
            )
        except KeyError:
            exc = traceback.format_exc()
        if exc:
            return _fail_or_default(exc, default)
        mod = ProxyModule(mod)

        if reloading:
            reloader = ModuleReloader(
                proxy=mod,
                name=name,
                path=path,
                initial_globals=initial_globals,
                package_name=package_name,
            )
            _reloaders[mod] = reloader

            threaded = False
            # this looks like a hack, but isn't one -
            # jupyter is running an async loop internally, which works better async than threaded!
            try:
                asyncio.get_running_loop()
            # we're dealing with non-async code, we need threading
            except RuntimeError:
                # can't have the code inside the handler because of "during handling of X, another exception Y happened"
                threaded = True
            if not threaded:
                reloader.start_async()
            else:
                reloader.start_threaded()

            if not all(
                inspect.isfunction(value)
                for key, value in mod.__dict__.items()
                if key not in initial_globals.keys() and not key.startswith("__")
            ):
                warn(UserMessage.not_reloadable(name), NotReloadableWarning)

        os.chdir(original_cwd)
        if exc:
            return _fail_or_default(ImportError(exc), default)

        if import_as:
            sys.modules[import_as] = mod
        self._set_mod(name=name, mod=mod)
        return mod

    @__call__.register(type(None))  # singledispatch is picky - can't be anything but a type
    def _use_kwargs(
        self,
        _: None,  # sic! otherwise single-dispatch with 'empty' *args won't work
        /,
        *,
        package_name: str = None,
        module_name: str = None,
        version: Optional[Union[Version, str]] = None,
        hash_algo=Hash.sha256,
        hashes: Optional[Union[str, list[str]]] = None,
        default=Modes.fastfail,
        modes: int = 0,
    ) -> ProxyModule:
        """
        Import a pkg by name.

        https://github.com/amogorkon/justuse/wiki/Use-String

        Args:
            name (str): The name of the pkg to import.
            version (str or Version, optional): The version of the pkg to import. Defaults to None.
            hash_algo (member of Use.Hash, optional): For future compatibility with more modern hashing algorithms. Defaults to Hash.sha256.
            hashes (str | [str]), optional): A single hash or list of hashes of the pkg to import. Defaults to None.
            default (anything, optional): Whatever should be returned in case there's a problem with the import. Defaults to mode.fastfail.
            modes (int, optional): Any combination of Use.modes . Defaults to 0.

        Raises:
            RuntimeWarning: May be raised if the auto-installation of the pkg fails for some reason.

        Returns:
            ProxyModule|Any: Module if successful, default as specified otherwise.
        """
        log.debug(f"use-kwargs: {package_name} {module_name} {version} {hashes}")
        return self._use_package(
            name=f"{package_name}/{module_name}",
            package_name=package_name,
            module_name=module_name,
            version=Version(version) if version else None,
            hash_algo=hash_algo,
            hashes=hashes,
            default=default,
            modes=modes,
            Message=KwargMessage,
        )

    @__call__.register(tuple)
    def _use_tuple(
        self,
        pkg_tuple,
        /,
        *,
        version: Optional[Union[Version, str]] = None,
        hash_algo=Hash.sha256,
        hashes: Optional[Union[str, list[str]]] = None,
        default=Modes.fastfail,
        modes: int = 0,
    ) -> ProxyModule:
        """
        Import a pkg by name.

        https://github.com/amogorkon/justuse/wiki/Use-String

        Args:
            name (str): The name of the pkg to import.
            version (str or Version, optional): The version of the pkg to import. Defaults to None.
            hash_algo (member of Use.Hash, optional): For future compatibility with more modern hashing algorithms. Defaults to Hash.sha256.
            hashes (str | [str]), optional): A single hash or list of hashes of the pkg to import. Defaults to None.
            default (anything, optional): Whatever should be returned in case there's a problem with the import. Defaults to mode.fastfail.
            modes (int, optional): Any combination of Use.modes . Defaults to 0.

        Raises:
            RuntimeWarning: May be raised if the auto-installation of the pkg fails for some reason.

        Returns:
            ProxyModule|Any: Module if successful, default as specified otherwise.
        """
        log.debug(f"use-tuple: {pkg_tuple} {version} {hashes}")
        package_name, module_name = pkg_tuple
        return self._use_package(
            name=f"{package_name}/{module_name}",
            package_name=package_name,
            module_name=module_name,
            version=Version(version) if version else None,
            hash_algo=hash_algo,
            hashes=hashes,
            default=default,
            modes=modes,
            Message=TupleMessage,
        )

    @__call__.register(str)
    def _use_str(
        self,
        name: str,
        /,
        *,
        version: Optional[Union[Version, str]] = None,
        hash_algo=Hash.sha256,
        hashes: Optional[Union[str, list[str]]] = None,
        default=Modes.fastfail,
        modes: int = 0,
    ) -> ProxyModule:
        """
        Import a pkg by name.

        https://github.com/amogorkon/justuse/wiki/Use-String

        Args:
            name (str): The name of the pkg to import.
            version (str or Version, optional): The version of the pkg to import. Defaults to None.
            hash_algo (member of Use.Hash, optional): For future compatibility with more modern hashing algorithms. Defaults to Hash.sha256.
            hashes (str | [str]), optional): A single hash or list of hashes of the pkg to import. Defaults to None.
            default (anything, optional): Whatever should be returned in case there's a problem with the import. Defaults to Modes.fastfail.
            modes (int, optional): Any combination of Use.modes . Defaults to 0.

        Raises:
            RuntimeWarning: May be raised if something non-critical happens during import.
            ImportError: May be raised if the auto-installation of the pkg fails for some reason.

        Returns:
            ProxyModule|Any: Module (wrapped in a ProxyModule) if successful, default as specified if the requested Module couldn't be imported for some reason.
        """
        package_name, module_name = _parse_name(name)
        return self._use_package(
            name=name,
            package_name=package_name,
            module_name=module_name,
            version=Version(version) if version else None,
            hash_algo=hash_algo,
            hashes=hashes,
            default=default,
            modes=modes,
            Message=StrMessage,
        )

    @require(lambda hash_algo: hash_algo != None)
    def _use_package(
        self,
        *,
        name,
        package_name: str,
        module_name: str,
        version: Optional[Version],
        hashes: Optional[Union[str, set]],
        default: Any,
        hash_algo: Hash,
        modes: int = 0,
        Message: type = UserMessage,
    ):
        auto_install = bool(Modes.auto_install & modes)
        no_public_installation = bool(Modes.no_public_installation & modes)
        fastfail = bool(Modes.fastfail & modes)
        fatal_exceptions = bool(Modes.fatal_exceptions & modes)
        no_browser = bool(Modes.no_browser & modes)
        cleanup = not bool(Modes.no_cleanup & modes)

        if module_name:
            module_name = module_name.replace("/", ".").replace("-", "_")

        # a single hash is a string
        if isinstance(hashes, str):
            # spaces are hard to see in JACK, so we ignore them
            hashes = ["".join(hashes.split())]
        if not hashes:
            hashes = set()
        hashes: set[int] = {
            JACK_as_num(H) if is_JACK(H) else int(H, 16) for H in ("".join(H.split()) for H in hashes)
        }

        # The "try and guess" behaviour is due to how classical imports work,
        # which is inherently ambiguous, but can't really be avoided for packages.
        # let's first see if the user might mean something else entirely
        if _ensure_path(f"./{module_name}.py").exists():
            warn(Message.ambiguous_name_warning(name), AmbiguityWarning)
        spec = None

        if name in self._using:
            spec = self._using[name].spec
        elif not auto_install:
            spec = importlib.util.find_spec(module_name.replace("-", "_"))

        case = bool(version), bool(hashes), bool(spec), auto_install
        log.info("case = %s", case)
        # welcome to the buffet table, where everything is a lie
        kwargs = {
            "name": name,
            "package_name": package_name,
            "module_name": module_name,
            "version": version,
            "user_provided_hashes": hashes,
            "hash_algo": hash_algo,
            "spec": spec,
            "fastfail": fastfail,
            "no_public_installation": no_public_installation,
            "fatal_exceptions": fatal_exceptions,
            "sys_version": Version(".".join(map(str, sys.version_info[:3]))),
            "no_browser": no_browser,
            "Message": Message,
            "registry": self.registry,
            "cleanup": cleanup,
        }

        result = buffet_table(case, kwargs)
        assert result
        assert isinstance(result, (Exception, ModuleType))

        if isinstance(result, Exception):
            return _fail_or_default(result, default)

        if isinstance(result, ModuleType):
            self._set_mod(name=name, mod=result, spec=spec)
            return ProxyModule(result)
