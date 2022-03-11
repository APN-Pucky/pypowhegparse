import importlib
import io
import logging
import os
import re
import subprocess
import sys
import warnings
from datetime import datetime
from distutils.errors import DistutilsSetupError
from typing import Any, Callable, List, Optional, Union

import toml
from packaging.version import Version
from setuptools.dist import Distribution
from six.moves import collections_abc

DEFAULT_TEMPLATE = "{tag}"
DEFAULT_DEV_TEMPLATE = "{tag}.post{ccount}+git.{sha}"
DEFAULT_DIRTY_TEMPLATE = "{tag}.post{ccount}+git.{sha}.dirty"
DEFAULT_STARTING_VERSION = "0.0.1"
DEFAULT_SORT_BY = "creatordate"
ENV_VARS_REGEXP = re.compile(r"\{env:(?P<name>[^:}]+):?(?P<default>[^}]+\}*)?\}", re.IGNORECASE | re.UNICODE)
TIMESTAMP_REGEXP = re.compile(r"\{timestamp:?(?P<fmt>[^:}]+)?\}", re.IGNORECASE | re.UNICODE)

DEFAULT_CONFIG = {
    "template": DEFAULT_TEMPLATE,
    "dev_template": DEFAULT_DEV_TEMPLATE,
    "dirty_template": DEFAULT_DIRTY_TEMPLATE,
    "starting_version": DEFAULT_STARTING_VERSION,
    "version_callback": None,
    "version_file": None,
    "count_commits_from_version_file": False,
    "tag_formatter": None,
    "branch_formatter": None,
    "sort_by": DEFAULT_SORT_BY,
}

log = logging.getLogger(__name__)


def _exec(cmd):  # type: (str) -> List[str]
    try:
        stdout = subprocess.check_output(cmd, shell=True, universal_newlines=True)  # nosec
    except subprocess.CalledProcessError as e:
        stdout = e.output
    lines = stdout.splitlines()
    return [line.rstrip() for line in lines if line.rstrip()]


def get_branches():  # type: () -> List[str]
    branches = _exec("git branch -l --format '%(refname:short)'")
    if branches:
        return branches
    return []


def get_branch():  # type: () -> Optional[str]
    branches = _exec("git rev-parse --abbrev-ref HEAD")
    if branches:
        return branches[0]
    return None


def get_all_tags(sort_by=DEFAULT_SORT_BY):  # type: (str) -> List[str]
    tags = _exec("git tag --sort=-{}".format(sort_by))
    if tags:
        return tags
    return []


def get_branch_tags(*args, **kwargs):  # type: (*str, **str) -> List[str]
    warnings.warn(
        "`get_branch_tags` function is deprecated "
        "since setuptools-git-versioning v1.8.0 "
        "and will be dropped in v2.0.0\n"
        "Please use `get_tags` instead",
        category=UserWarning,
    )

    return get_tags(*args, **kwargs)


def get_tags(sort_by=DEFAULT_SORT_BY):  # type: (str) -> List[str]
    tags = _exec("git tag --sort=-{} --merged".format(sort_by))
    if tags:
        return tags
    return []


def get_tag(*args, **kwargs):  # type: (*str, **str) -> Optional[str]
    tags = get_tags(*args, **kwargs)
    if tags:
        return tags[0]
    return None


def get_sha(name="HEAD"):  # type: (str) -> Optional[str]
    sha = _exec('git rev-list -n 1 "{}"'.format(name))
    if sha:
        return sha[0]
    return None


def get_latest_file_commit(path):  # type: (str) -> Optional[str]
    sha = _exec('git log -n 1 --pretty=format:%H -- "{}"'.format(path))
    if sha:
        return sha[0]
    return None


def is_dirty():  # type: () -> bool
    res = _exec("git status --short")
    if res:
        return True
    return False


def count_since(name):  # type: (str) -> Optional[int]
    res = _exec('git rev-list --count HEAD "^{}"'.format(name))
    if res:
        return int(res[0])
    return None


def load_config_from_dict(dictionary):  # type: (Union[dict, collections_abc.Mapping]) -> dict
    config = {}
    for key, value in DEFAULT_CONFIG.items():
        config[key] = dictionary.get(key, value)
    return config


def read_toml(file_name):  # type: (str) -> dict
    if not os.path.exists(file_name) or not os.path.isfile(file_name):
        return {}

    with io.open(file_name, encoding="UTF-8", mode="r") as f:
        data = f.read()
    parsed_file = toml.loads(data)

    return parsed_file.get("tool", {}).get("setuptools-git-versioning", None)


# TODO: remove along with version_config
def parse_config(dist, attr, value):  # type: (Distribution, Any, Any) -> None
    if attr == "version_config" and value is not None:
        warnings.warn(
            "`version_config` option is deprecated "
            "since setuptools-git-versioning v1.8.0 "
            "and will be dropped in v2.0.0\n"
            "Please rename it to `setuptools_git_versioning`",
            category=UserWarning,
        )

        if getattr(dist, "setuptools_git_versioning", None) is not None:
            raise DistutilsSetupError(
                "You can set either `version_config` or `setuptools_git_versioning` "
                "but not both of them at the same time"
            )


# real version is generated here
def infer_version(dist):  # type: (Distribution) -> None
    value = getattr(dist, "setuptools_git_versioning", None) or getattr(dist, "version_config", None)

    if isinstance(value, bool):
        warnings.warn(
            "Passing boolean value to `version_config`/`setuptools_git_versioning` option is deprecated "
            "since setuptools-git-versioning 1.8.0 "
            "and will be dropped in v2.0.0\n"
            "Please change value to `{'enabled': False/True}`",
            category=UserWarning,
        )
        value = {"enabled": value}

    toml_value = read_toml("pyproject.toml")

    if value is None:
        value = toml_value
    elif toml_value:
        raise DistutilsSetupError(
            "Both setup.py and pyproject.toml have setuptools-git-versioning config. " "Please remove one of them"
        )

    if value is None:
        # Nothing to do here
        return

    if not isinstance(value, collections_abc.Mapping):
        raise DistutilsSetupError("Wrong config format. Expected dict, got: {value}".format(value=value))

    if not value or not value.get("enabled", True):
        # Nothing to do here
        return

    config = load_config_from_dict(value)

    version = version_from_git(dist.metadata.name, **config)
    dist.metadata.version = version


def read_version_from_file(path):  # type: (Union[str, os.PathLike]) -> str
    with open(path) as file:
        return file.read().strip()


def substitute_env_variables(template):  # type: (str) -> str
    for var, default in ENV_VARS_REGEXP.findall(template):
        if default.upper() == "IGNORE":
            default = ""
        elif not default:
            default = "UNKNOWN"

        value = os.environ.get(var, default)
        template, _ = ENV_VARS_REGEXP.subn(value, template, count=1)

    return template


def substitute_timestamp(template):  # type: (str) -> str
    now = datetime.now()
    for fmt in TIMESTAMP_REGEXP.findall(template):
        result = now.strftime(fmt or "%s")
        template, _ = TIMESTAMP_REGEXP.subn(result, template, count=1)

    return template


def resolve_substitutions(template, *args, **kwargs):  # type: (str, *Any, **Any) -> str
    while True:
        if "{env" in template:
            new_template = substitute_env_variables(template)
            if new_template == template:
                break
            else:
                template = new_template
        else:
            break

    if "{timestamp" in template:
        template = substitute_timestamp(template)

    return template.format(*args, **kwargs)


def import_reference(
    ref,  # type: str
    package_name=None,  # Optional[str]
):  # type: (...) -> Any
    if ":" not in ref:
        raise NameError("Wrong reference name: {ref}".format(ref=ref))

    module_name, attr = ref.split(":")
    module = importlib.import_module(module_name, package_name)

    return getattr(module, attr)


def load_callable(
    inp,  # type: str
    package_name=None,  # Optional[str]
):  # type: (...) -> Callable

    ref = import_reference(inp, package_name)
    if not callable(ref):
        raise ValueError("{ref} of type {type} is not callable".format(ref=ref, type=type(ref)))

    return ref


def load_tag_formatter(
    tag_formatter,  # type: Union[str, Callable[[str], str]]
    package_name=None,  # Optional[str]
):  # type: (...) -> Callable
    log.warning(
        "Parsing tag_formatter {tag_formatter} with type {type}".format(
            tag_formatter=tag_formatter,
            type=type(tag_formatter),
        )
    )

    if callable(tag_formatter):
        return tag_formatter

    try:
        return load_callable(tag_formatter, package_name)
    except (ImportError, NameError) as e:
        log.warning("tag_formatter is not a valid function reference:\n\t{e}".format(e=e))

    try:
        pattern = re.compile(tag_formatter)

        def formatter(tag):
            match = pattern.match(tag)
            if match:
                return match.group("tag")

            raise ValueError(
                "tag name {name} does not match regexp '{regexp}'".format(
                    name=tag,
                    regexp=tag_formatter,
                )
            )

        return formatter
    except re.error as e:
        log.warning("tag_formatter is not valid regexp:\n\t{e}".format(e=e))

    raise ValueError("Cannot parse tag_formatter")


def load_branch_formatter(
    branch_formatter,  # type: Union[str, Callable[[str], str]]
    package_name=None,  # Optional[str]
):  # type: (...) -> Callable
    log.warning(
        "Parsing branch_formatter {branch_formatter} with type {type}".format(
            branch_formatter=branch_formatter,
            type=type(branch_formatter),
        )
    )

    if callable(branch_formatter):
        return branch_formatter

    try:
        return load_callable(branch_formatter, package_name)
    except (ImportError, NameError) as e:
        log.warning("branch_formatter is not a valid function reference:\n\t{e}".format(e=e))

    try:
        pattern = re.compile(branch_formatter)

        def formatter(branch):
            match = pattern.match(branch)
            if match:
                return match.group("branch")

            raise ValueError(
                "Branch name {name} does not match regexp '{regexp}'".format(
                    name=branch,
                    regexp=branch_formatter,
                )
            )

        return formatter
    except re.error as e:
        log.warning("branch_formatter is not valid regexp:\n\t{e}".format(e=e))

    raise ValueError("Cannot parse branch_formatter")


# TODO: return Version object instead of str
def get_version_from_callback(
    version_callback,  # type: Union[str, Callable[[], str]]
    package_name=None,  # Optional[str]
):  # type: (...) -> str
    log.warning(
        "Parsing version_callback {version_callback} with type {type}".format(
            version_callback=version_callback,
            type=type(version_callback),
        )
    )

    if callable(version_callback):
        return version_callback()

    result = version_callback

    try:
        return load_callable(version_callback, package_name)()
    except ValueError:
        result = import_reference(version_callback, package_name)
    except (ImportError, NameError) as e:
        log.warning("version_callback is not a valid reference:\n\t{e}".format(e=e))

    return Version(result).public


# TODO: return Version object instead of str
def version_from_git(
    package_name=None,  # type: Optional[str]
    template=DEFAULT_TEMPLATE,  # type: str
    dev_template=DEFAULT_DEV_TEMPLATE,  # type: str
    dirty_template=DEFAULT_DIRTY_TEMPLATE,  # type: str
    starting_version=DEFAULT_STARTING_VERSION,  # type: str
    version_callback=None,  # type: Union[Any, Callable, None]
    version_file=None,  # type: Optional[str]
    count_commits_from_version_file=False,  # type: bool
    tag_formatter=None,  # type: Optional[Callable[[str], str]]
    branch_formatter=None,  # type: Optional[Callable[[str], str]]
    sort_by=DEFAULT_SORT_BY,  # type: str
):
    # type: (...) -> str

    if sys.version_info < (3, 7):
        warnings.warn(
            "Python 2.7, 3.5 and 3.6 support is deprecated "
            "since setuptools-git-versioning v1.8.0 "
            "and will be dropped in v2.0.0\n"
            "Please upgrade your Python version to 3.7+",
            category=UserWarning,
        )

    # Check if PKG-INFO file exists and Version is present in it
    if os.path.exists("PKG-INFO"):
        with open("PKG-INFO") as f:
            lines = f.readlines()
        for line in lines:
            if line.startswith("Version:"):
                return line[8:].strip()

    from_file = False
    tag = get_tag(sort_by=sort_by)

    if tag is None:
        # TODO: raise exception if both version_callback and version_file are set
        if version_callback is not None:
            return get_version_from_callback(version_callback, package_name)

        if version_file is None or not os.path.exists(version_file):
            return starting_version
        else:
            from_file = True
            tag = read_version_from_file(version_file)

            if not tag:
                return starting_version

            if not count_commits_from_version_file:
                # TODO: drop all leading non-numeric symbols
                return tag.lstrip("v")  # for tag "v1.0.0" drop leading "v" symbol

            tag_sha = get_latest_file_commit(version_file)
    else:
        tag_sha = get_sha(tag)

        if tag_formatter is not None:
            tag_fmt = load_tag_formatter(tag_formatter, package_name)
            tag = tag_fmt(tag)

    dirty = is_dirty()
    head_sha = get_sha()
    full_sha = head_sha if head_sha is not None else ""
    ccount = count_since(tag_sha) if tag_sha is not None else None
    on_tag = head_sha is not None and head_sha == tag_sha and not from_file

    branch = get_branch()
    if branch_formatter is not None and branch is not None:
        branch_fmt = load_branch_formatter(branch_formatter, package_name)
        branch = branch_fmt(branch)

    if dirty:
        t = dirty_template
    elif not on_tag and ccount is not None:
        t = dev_template
    else:
        t = template

    version = resolve_substitutions(t, sha=full_sha[:8], tag=tag, ccount=ccount, branch=branch, full_sha=full_sha)

    # Ensure local version label only contains permitted characters
    public, sep, local = version.partition("+")
    local_sanitized = re.sub(r"[^a-zA-Z0-9.]", ".", local)
    # TODO: drop all leading non-numeric symbols
    public_sanitized = public.lstrip("v")  # for version "v1.0.0" drop leading "v" symbol
    return public_sanitized + sep + local_sanitized
