#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2019  WillyPillow <wp@nerde.pw>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""Template management for Qubes OS."""

import os
import base64
import collections
import configparser
import datetime
import enum
import fcntl
import fnmatch
import functools
import itertools
import logging
import re
import rpm
import shutil
import subprocess
import tempfile
import typing

import qubesadmin.app
import qubesadmin.exc
import qubesadmin.vm
import qubesadmin.utils

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

DATE_FMT = '%Y-%m-%d %H:%M:%S'
LOCK_FILE = '/run/qubes/qvm-template.lock'
PATH_PREFIX = '/var/lib/qubes/vm-templates'
PACKAGE_NAME_PREFIX = 'qubes-template-'
TAR_HEADER_BYTES = 512
TEMP_DIR = '/var/tmp'
WRAPPER_PAYLOAD_BEGIN = "###!Q!BEGIN-QUBES-WRAPPER!Q!###"
WRAPPER_PAYLOAD_END = "###!Q!END-QUBES-WRAPPER!Q!###"

# Search weight constants
WEIGHT_NAME_EXACT = 1 << 4
WEIGHT_NAME = 1 << 3
WEIGHT_SUMMARY = 1 << 2
WEIGHT_DESCRIPTION = 1 << 1
WEIGHT_URL = 1 << 0

WEIGHT_TO_FIELD = [
    (WEIGHT_NAME_EXACT, 'Name'),
    (WEIGHT_NAME, 'Name'),
    (WEIGHT_SUMMARY, 'Summary'),
    (WEIGHT_DESCRIPTION, 'Description'),
    (WEIGHT_URL, 'URL')]


class TemplateState(enum.Enum):
    """Enum representing the state of a template."""
    INSTALLED = 'installed'
    AVAILABLE = 'available'
    EXTRA = 'extra'
    UPGRADABLE = 'upgradable'

    def title(self) -> str:
        """Return a long description of the state. Can be used as headings."""
        # pylint: disable=invalid-name
        TEMPLATE_TITLES = {
            TemplateState.INSTALLED: 'Installed Templates',
            TemplateState.AVAILABLE: 'Available Templates',
            TemplateState.EXTRA: 'Extra Templates',
            TemplateState.UPGRADABLE: 'Available Upgrades'
        }
        return TEMPLATE_TITLES[self]


class VersionSelector(enum.Enum):
    """Enum representing how the candidate template version is chosen."""
    LATEST = enum.auto()
    """Install latest version."""
    REINSTALL = enum.auto()
    """Reinstall current version."""
    LATEST_LOWER = enum.auto()
    """Downgrade to the highest version that is lower than the current one."""
    LATEST_HIGHER = enum.auto()
    """Upgrade to the highest version that is higher than the current one."""


# pylint: disable=too-few-public-methods,inherit-non-class
class Template(typing.NamedTuple):
    """Details of a template."""
    name: str
    epoch: str
    version: str
    release: str
    reponame: str
    dlsize: int
    buildtime: datetime.datetime
    licence: str
    url: str
    summary: str
    description: str

    @property
    def evr(self):
        """Return a tuple of (EPOCH, VERSION, RELEASE)"""
        return self.epoch, self.version, self.release


class DlEntry(typing.NamedTuple):
    """Information about a template to be downloaded."""
    evr: typing.Tuple[str, str, str]
    reponame: str
    dlsize: int


# pylint: enable=too-few-public-methods,inherit-non-class


def query_local(vm: qubesadmin.vm.QubesVM) -> Template:
    """Return Template object associated with ``vm``.

    Requires the VM to be managed by qvm-template.
    """
    return Template(
        vm.features['template-name'],
        vm.features['template-epoch'],
        vm.features['template-version'],
        vm.features['template-release'],
        vm.features['template-reponame'],
        vm.get_disk_utilization(),
        datetime.datetime.strptime(vm.features['template-buildtime'], DATE_FMT),
        vm.features['template-license'],
        vm.features['template-url'],
        vm.features['template-summary'],
        vm.features['template-description'].replace('|', '\n'))


def query_local_evr(vm: qubesadmin.vm.QubesVM) -> typing.Tuple[str, str, str]:
    """Return the (epoch, version, release) of ``vm``.

    Requires the VM to be managed by qvm-template.
    """
    return (
        vm.features['template-epoch'],
        vm.features['template-version'],
        vm.features['template-release'])


def is_managed_template(vm: qubesadmin.vm.QubesVM) -> bool:
    """Return whether the VM is managed by qvm-template."""
    return vm.features.get('template-name', None) == vm.name


def get_managed_template_vm(app: qubesadmin.app.QubesBase, name: str
                            ) -> qubesadmin.vm.QubesVM:
    """Return the QubesVM object associated with the given name if it exists
    and is managed by qvm-template, otherwise raise an exception.

    :raises QubesVMNotFoundError: if the template is not installed
    :raises QubesVMError: if the VM exists but is not managed by qvm-template
    """
    if name not in app.domains:
        raise qubesadmin.exc.QubesVMNotFoundError(
            f"Template '{name}' not already installed.")
    vm = app.domains[name]
    if not is_managed_template(vm):
        raise qubesadmin.exc.QubesVMError(
            f"Template '{name}' is not managed by qvm-template.")
    return vm


def qubes_release() -> str:
    """Return the Qubes release."""
    if os.path.exists('/usr/share/qubes/marker-vm'):
        with open('/usr/share/qubes/marker-vm', 'r', encoding='ascii') as fd:
            # Get the first non-comment line
            release = [l.strip() for l in fd.readlines()
                       if l.strip() and not l.startswith('#')]
            # sanity check
            if release and release[0] and release[0][0].isdigit():
                return release[0]
    with open('/etc/os-release', 'r', encoding='ascii') as fd:
        release = None
        distro_id = None
        for line in fd:
            line = line.strip()
            if not line or line[0] == '#':
                continue
            key, val = line.split('=', 1)
            if key == 'ID':
                distro_id = val
            if key == 'VERSION_ID':
                release = val.strip('\'"') # strip possible quotes
        if distro_id and 'qubes' in distro_id and release:
            return release
    # Return default value instead of throwing so that it works on CI
    return '4.1'


def build_version_str(evr: typing.Tuple[str, str, str]) -> str:
    """Return version string described by ``evr``, which is in (epoch, version,
    release) format."""
    return '%s:%s-%s' % evr


def is_match_spec(name: str, epoch: str, version: str, release: str, spec: str
                  ) -> typing.Tuple[bool, float]:
    """Check whether (name, epoch, version, release) matches the spec string.

    For the algorithm, refer to section "NEVRA Matching" in the DNF
    documentation.

    Note that currently ``arch`` is ignored as the templates should be of
    ``noarch``.

    :return: A tuple. The first element indicates whether there is a match; the
        second element represents the priority of the match (lower is better)
    """
    if epoch != '0':
        targets = [
            f'{name}-{epoch}:{version}-{release}',
            f'{name}',
            f'{name}-{epoch}:{version}'
        ]
    else:
        targets = [
            f'{name}-{epoch}:{version}-{release}',
            f'{name}-{version}-{release}',
            f'{name}',
            f'{name}-{epoch}:{version}',
            f'{name}-{version}'
        ]
    for prio, target in enumerate(targets):
        if fnmatch.fnmatch(target, spec):
            return True, prio
    return False, float('inf')


def verify_rpm(path: str, key: str, *, nogpgcheck: bool = False,
               template_name: typing.Optional[str] = None) -> typing.Any:
    """Verify the digest and signature of a RPM package and return the package
    header.

    Note that verifying RPMs this way is prone to TOCTOU. This is okay for
    local files, but may create problems if multiple instances of
    **qvm-template** are downloading the same file, so a lock is needed in that
    case.

    :param path: Location of the RPM package
    :param key: Path to the GPG key file
    :param nogpgcheck: Whether to allow invalid GPG signatures
    :param template_name: expected template name - if specified, verifies if
           the package name matches expected template name

    :return: RPM package header. If verification fails, raises an exception.
    """
    import rpm

    assert isinstance(nogpgcheck, bool), 'Must pass a boolean for nogpgcheck'
    with open(path, 'rb') as fd:
        if not nogpgcheck:
            with tempfile.TemporaryDirectory() as rpmdb_dir:
                subprocess.check_call(
                    ['rpmkeys', '--dbpath=' + rpmdb_dir, '--import', key])
                try:
                    output = subprocess.check_output([
                        'rpmkeys',
                        '--dbpath=' + rpmdb_dir,
                        '--define=_pkgverify_level all',
                        '--define=_pkgverify_flags 0x0',
                        '--checksig',
                        '-',
                    ], env={'LC_ALL': 'C', **os.environ}, stdin=fd)
                except subprocess.CalledProcessError as e:
                    raise qubesadmin.exc.SignatureVerificationError(
                        f"Signature verification failed: {e.output.decode()}")
                if output != b'-: digests signatures OK\n':
                    raise qubesadmin.exc.SignatureVerificationError(
                        f"Signature verification failed: {output.decode()}")
            fd.seek(0)
        tset = rpm.TransactionSet()
        tset.setVSFlags(rpm.RPMVSF_MASK_NOSIGNATURES)
        hdr = tset.hdrFromFdno(fd)
    if template_name is not None:
        if hdr[rpm.RPMTAG_NAME] != PACKAGE_NAME_PREFIX + template_name:
            raise qubesadmin.exc.SignatureVerificationError(
                'Downloaded package does not match expected template name')
    return hdr


def extract_rpm(name: str, path: str, target: str) -> bool:
    """Extract a template RPM package.

    If the package contains root.img file split across multiple parts,
    only the first 512 bytes of the 00 part is retained (tar header) and
    a symlink to the rpm file is created in target directory.

    :param name: Name of the template
    :param path: Location of the RPM package
    :param target: Target path to extract to

    :return: Whether the extraction succeeded
    """
    with open(path, 'rb') as pkg_f:
        with subprocess.Popen(['rpm2archive', "-"],
                stdin=pkg_f,
                stdout=subprocess.PIPE) as rpm2archive:
            with subprocess.Popen([
                'tar', 'xz', '-C', target, f'.{PATH_PREFIX}/{name}/',
                '--exclude=root.img.part.?[!0]',
                '--exclude=root.img.part.[!0]0'
            ], stdin=rpm2archive.stdout, stdout=subprocess.DEVNULL) as tar:
                pass
    if rpm2archive.returncode != 0 or tar.returncode != 0:
        return False

    part_00_path = f'{target}/{PATH_PREFIX}/{name}/root.img.part.00'
    if os.path.exists(part_00_path):
        with subprocess.Popen([
            'truncate', f'--size={TAR_HEADER_BYTES}', part_00_path
        ]) as truncate:
            pass
        if truncate.returncode != 0:
            return False
        link_path = f'{target}/{PATH_PREFIX}/{name}/template.rpm'
        try:
            os.symlink(os.path.abspath(path), link_path)
        except OSError as e:
            log.error(f"Failed to create {link_path} symlink: {e!s}")
            return False
    return True


def _is_file_in_repo_templates_keys_dir(path: str) -> bool:
    """Check if the given path is a file located repo-template keys dir"""
    return os.path.isfile(path) and path.startswith(
        "/etc/qubes/repo-templates/keys/")

def _encode_key(path):
    """Base64-encoe a file to be placed in qvm-template payload"""
    if path.startswith("file://"):
        path = path[7:]

    if not _is_file_in_repo_templates_keys_dir(path):
        return ""

    encoded_key = "#" + path + "\n"
    with open(path, "rb") as key:
        encoded_key += f"#{base64.b64encode(key.read()).decode('ascii')}\n"
    return encoded_key

def _replace_dnf_vars(path, releasever):
    """Replace supported dnf variables in repo"""
    for var in ["$releasever", "${releasever}"]:
        path = path.replace(var, releasever)
    return path

def _append_keys(payload, releasever):
    """Add GPG key and SSL cert/keys to qvm-template payload"""
    config = configparser.ConfigParser()
    try:
        config.read_string(payload)
    except RuntimeError:
        return ""

    file_list = set()
    for section in config.sections():
        for option in ["gpgkey", "sslclientcert", "sslclientkey"]:
            if config.has_option(section, option):
                file_list.add(
                    _replace_dnf_vars(config.get(section, option),
                                      releasever))

    encoded_keys = "".join(
        [_encode_key(file_path) for file_path in sorted(file_list)])
    if not encoded_keys:
        return ""

    return f"\n{WRAPPER_PAYLOAD_BEGIN}\n{encoded_keys}{WRAPPER_PAYLOAD_END}"

def get_keys_for_repos(repo_files: typing.List[str],
                       releasever: str) -> typing.Dict[str, str]:
    """List gpg keys

    Returns a dict reponame -> key path
    """
    keys = {}
    for repo_file in repo_files:
        repo_config = configparser.ConfigParser()
        repo_config.read(repo_file)
        for repo in repo_config.sections():
            try:
                gpgkey_url = repo_config.get(repo, 'gpgkey')
            except configparser.NoOptionError:
                continue
            gpgkey_url = gpgkey_url.replace('$releasever', releasever)
            # support only file:// urls
            if gpgkey_url.startswith('file://'):
                keys[repo] = gpgkey_url[len('file://'):]
    return keys


def qrexec_popen(
        app: qubesadmin.app.QubesBase,
        service: str,
        updatevm: typing.Optional[str] = None,
        stdout: typing.Union[int, typing.IO] = subprocess.PIPE,
        filter_esc: bool = True) -> subprocess.Popen:
    """Return ``Popen`` object that communicates with the given qrexec call.

    Note that this falls back to invoking ``/etc/qubes-rpc/*`` directly if
    ``updatevm`` is empty string.

    :param app: Qubes application object
    :param service: The qrexec service to invoke
    :param updatevm: VM to use for the qrexec call. If empty/None, falls back
        to direct invocation.
    :param stdout: Where the process stdout points to. This is passed directly
        to ``subprocess.Popen``. Defaults to ``subprocess.PIPE``
    :param filter_esc: Whether to filter out escape sequences from
        stdout/stderr. Defaults to True

    :returns: ``Popen`` object that communicates with the given qrexec call
    """
    if updatevm:
        return app.domains[updatevm].run_service(
            service,
            filter_esc=filter_esc,
            stdout=stdout)
    # pylint: disable=consider-using-with
    return subprocess.Popen(
        [f'/etc/qubes-rpc/{service}'], stdin=subprocess.PIPE, stdout=stdout,
        stderr=subprocess.PIPE
    )

def qrexec_payload(
        app: qubesadmin.app.QubesBase,
        spec: str,
        refresh: bool,
        repos: typing.List[typing.Tuple[str, str]],
        releasever: str,
        repo_files: typing.List[str]) -> str:
    """Return payload string for the ``qubes.Template*`` qrexec calls.

    :param app: Qubes application object
    :param spec: Package spec to query (refer to ``<package-name-spec>`` in the
        DNF documentation)
    :param refresh: Whether to force refresh repo metadata
    :param repos: List of (operation, repo_id) tuples for repo configuration
    :param releasever: Qubes release version
    :param repo_files: List of paths to repo configuration files

    :return: Payload string

    :raises QubesValueError: if spec equals ``---`` or input contains ``\\n``
    """
    _ = app  # unused

    if spec == '---':
        raise qubesadmin.exc.QubesValueError(
            "Malformed template name: argument should not be '---'.")

    def check_newline(string, name):
        if '\n' in string:
            raise qubesadmin.exc.QubesValueError(
                f"Malformed {name}: argument should not contain '\\n'.")

    payload = ''
    for repo_op, repo_id in repos:
        check_newline(repo_id, '--' + repo_op)
        payload += f'--{repo_op}={repo_id}\n'
    if refresh:
        payload += '--refresh\n'
    check_newline(releasever, '--releasever')
    payload += f'--releasever={releasever}\n'
    check_newline(spec, 'template name')
    payload += spec + '\n'
    payload += '---\n'

    repo_config = ""
    for path in repo_files:
        with open(path, 'r', encoding='utf-8') as fd:
            repo_config += fd.read() + '\n'
    payload += repo_config

    payload += _append_keys(repo_config, releasever)
    return payload


def qrexec_repoquery(
        app: qubesadmin.app.QubesBase,
        repos: typing.List[typing.Tuple[str, str]],
        releasever: str,
        repo_files: typing.List[str],
        updatevm: typing.Optional[str] = None,
        spec: str = '*',
        refresh: bool = False) -> typing.List[Template]:
    """Query template information from repositories.

    :param app: Qubes application object
    :param repos: List of (operation, repo_id) tuples for repo configuration
    :param releasever: Qubes release version
    :param repo_files: List of paths to repo configuration files
    :param updatevm: VM to download updates from. Empty string for current VM.
    :param spec: Package spec to query (refer to ``<package-name-spec>`` in the
        DNF documentation). Defaults to ``*``
    :param refresh: Whether to force refresh repo metadata. Defaults to False

    :raises ConnectionError: if the qrexec call fails

    :return: List of ``Template`` objects representing the result of the query
    """
    payload = qrexec_payload(app, spec, refresh, repos, releasever, repo_files)
    proc = qrexec_popen(app, 'qubes.TemplateSearch', updatevm)
    proc.stdin.write(payload.encode('UTF-8'))
    proc.stdin.close()
    stdout = proc.stdout.read(1 << 20).decode('ascii', 'strict')
    proc.stdout.close()
    stderr = proc.stderr.read(1 << 10).decode('ascii', 'strict')
    proc.stderr.close()
    if proc.wait() != 0:
        for line in stderr.rstrip().split('\n'):
            log.error(f"[Qrexec] {line}")
        raise ConnectionError("qrexec call 'qubes.TemplateSearch' failed.")
    name_re = re.compile(r'\A[A-Za-z0-9._+][A-Za-z0-9._+-]*\Z')
    evr_re = re.compile(r'\A[A-Za-z0-9._+~]*\Z')
    date_re = re.compile(r'\A\d{4}-\d{1,2}-\d{1,2} \d{1,2}:\d{1,2}\Z')
    licence_re = re.compile(r'\A[A-Za-z0-9._+()][A-Za-z0-9._+()-]*\Z')
    result = []
    # FIXME: This breaks when \n is the first character of the description
    for line in stdout.split('|\n'):
        # Note that there's an empty entry at the end as .strip() is not used.
        # This is because if .strip() is used, the .split() will not work.
        if line == '':
            continue
        # This is specific to DNF5:
        if line.endswith('|'):
            line = line[:-1]
        entry = line.split('|')
        try:
            # If there is an incorrect number of entries, raise an error
            # Unpack manually instead of stuffing into `Template` right away
            # so that it's easier to mutate stuff.
            name, epoch, version, release, reponame, dlsize, \
            buildtime, licence, url, summary, description = entry

            # Ignore packages that are not templates
            if not name.startswith(PACKAGE_NAME_PREFIX):
                continue
            name = name[len(PACKAGE_NAME_PREFIX):]

            # Check that the values make sense
            if not re.fullmatch(name_re, name):
                raise ValueError
            for val in [epoch, version, release]:
                if not re.fullmatch(evr_re, val):
                    raise ValueError
            if not re.fullmatch(name_re, reponame):
                raise ValueError
            dlsize = int(dlsize)
            # First verify that the date does not look weird, then parse it
            if re.fullmatch(date_re, buildtime):
                buildtime = datetime.datetime.strptime(buildtime, \
                        '%Y-%m-%d %H:%M')
            elif buildtime.isnumeric():
                # DNF5 provides seconds since epoch
                buildtime = datetime.datetime.fromtimestamp(int(buildtime),
                    tz=datetime.timezone.utc)
            else:
                raise ValueError
            # XXX: Perhaps whitelist licenses directly?
            if not re.fullmatch(licence_re, licence):
                raise ValueError
            # Check name actually matches spec
            if not is_match_spec(PACKAGE_NAME_PREFIX + name,
                                 epoch, version, release, spec)[0]:
                continue

            result.append(Template(name, epoch, version, release, reponame,
                                   dlsize, buildtime, licence, url, summary,
                                   description))
        except (TypeError, ValueError):
            raise ConnectionError("qrexec call 'qubes.TemplateSearch' failed:"
                                   " unexpected data format.")
    return result


def qrexec_download(
        app: qubesadmin.app.QubesBase,
        spec: str,
        path: str,
        key: str,
        repos: typing.List[typing.Tuple[str, str]],
        releasever: str,
        repo_files: typing.List[str],
        updatevm: typing.Optional[str] = None,
        dlsize: typing.Optional[int] = None,
        refresh: bool = False,
        progress_callback: typing.Optional[typing.Callable[[int, int], None]] = None
) -> None:
    """Download a template from repositories.

    :param app: Qubes application object
    :param spec: Package spec to download
    :param path: Path to place the downloaded template
    :param key: Path to GPG key file for verification
    :param repos: List of (operation, repo_id) tuples for repo configuration
    :param releasever: Qubes release version
    :param repo_files: List of paths to repo configuration files
    :param updatevm: VM to download updates from. Empty string for current VM.
    :param dlsize: Size of template to be downloaded (for progress reporting)
    :param refresh: Whether to force refresh repo metadata
    :param progress_callback: Optional callback for progress updates.
        Called with (current_bytes, total_bytes).

    :raises ConnectionError: if the qrexec call fails
    """
    with tempfile.TemporaryDirectory() as rpmdb_dir:
        subprocess.check_call(
            ['rpmkeys', '--dbpath=' + rpmdb_dir, '--import', key])
        payload = qrexec_payload(app, spec, refresh, repos, releasever,
                                 repo_files)
        with subprocess.Popen([
            'rpmcanon',
            '--dbpath=' + rpmdb_dir,
            '--report-progress',
            '--',
            '/dev/stdin',
            path
        ], stdin=subprocess.PIPE, stdout=subprocess.PIPE) as rpmcanon:
            # Don't filter ESCs for binary files
            proc = qrexec_popen(app, 'qubes.TemplateDownload', updatevm,
                                stdout=rpmcanon.stdin, filter_esc=False)
            rpmcanon.stdin.close()
            proc.stdin.write(payload.encode('UTF-8'))
            proc.stdin.close()
            for i in rpmcanon.stdout:
                if i.endswith(b' bytes so far\n'):
                    if progress_callback:
                        progress_callback(int(i[:-14]), dlsize)
                elif i.endswith(b' bytes total\n'):
                    actual_size = int(i[:-13])
                    if dlsize is not None and dlsize != actual_size:
                        raise ConnectionError(
                            f"Downloaded file is {dlsize} bytes, "
                            f"expected {actual_size}")
                else:
                    raise ConnectionError(
                        f'Bad line from rpmcanon: {i!r}')

            if proc.wait() != 0:
                raise ConnectionError(
                    "qrexec call 'qubes.TemplateDownload' failed.")
            if rpmcanon.wait() != 0:
                raise ConnectionError("rpmcanon failed")


def locked(func):
    """Execute given function under a lock in *LOCK_FILE*"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with open(LOCK_FILE, 'w', encoding='ascii') as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise qubesadmin.exc.AlreadyRunning(
                    f"Cannot get lock on {LOCK_FILE}. Perhaps another instance "
                    f"of qvm-template is running?")
            try:
                return func(*args, **kwargs)
            finally:
                os.remove(LOCK_FILE)
    return wrapper


def filter_version(
        query_res,
        app: qubesadmin.app.QubesBase,
        version_selector: VersionSelector = VersionSelector.LATEST):
    """Select only one version for given template name

    :raises QubesVMNotFoundError: if template not installed (for REINSTALL,
        LATEST_LOWER, LATEST_HIGHER)
    :raises QubesVMError: if template exists but not managed by qvm-template
    """
    # We only select one package for each distinct package name
    results: typing.Dict[str, Template] = {}

    for entry in query_res:
        evr = (entry.epoch, entry.version, entry.release)
        insert = False
        if version_selector == VersionSelector.LATEST:
            if entry.name not in results:
                insert = True
            if entry.name in results \
                    and rpm.labelCompare(results[entry.name].evr, evr) < 0:
                insert = True
            if entry.name in results \
                    and rpm.labelCompare(results[entry.name].evr, evr) == 0 \
                    and 'testing' not in entry.reponame:
                # for the same-version matches, prefer non-testing one
                insert = True
        elif version_selector == VersionSelector.REINSTALL:
            vm = get_managed_template_vm(app, entry.name)
            cur_ver = query_local_evr(vm)
            if rpm.labelCompare(evr, cur_ver) == 0:
                insert = True
        elif version_selector in [VersionSelector.LATEST_LOWER,
                                  VersionSelector.LATEST_HIGHER]:
            vm = get_managed_template_vm(app, entry.name)
            cur_ver = query_local_evr(vm)
            cmp_res = -1 \
                if version_selector == VersionSelector.LATEST_LOWER \
                else 1
            if rpm.labelCompare(evr, cur_ver) == cmp_res:
                if entry.name not in results \
                        or rpm.labelCompare(results[entry.name].evr, evr) < 0:
                    insert = True
        if insert:
            results[entry.name] = entry

    return results.values()

def get_dl_list(
        app: qubesadmin.app.QubesBase,
        templates: typing.List[str],
        repos: typing.List[typing.Tuple[str, str]],
        releasever: str,
        repo_files: typing.List[str],
        updatevm: typing.Optional[str] = None,
        version_selector: VersionSelector = VersionSelector.LATEST,
) -> typing.Dict[str, DlEntry]:
    """Return list of templates that needs to be downloaded.

    :param args: Arguments received by the application.
    :param app: Qubes application object
    :param version_selector: Specify algorithm to select the candidate version
        of a package.  Defaults to ``VersionSelector.LATEST``

    :return: Dictionary that maps to ``DlEntry`` the names of templates that
        needs to be downloaded
    """
    full_candid: typing.Dict[str, DlEntry] = {}
    for template in templates:
        # Skip local RPMs
        if template.endswith('.rpm'):
            continue

        query_res = qrexec_repoquery(app, repos, releasever, repo_files,
                                     updatevm, PACKAGE_NAME_PREFIX + template)

        # We only select one package for each distinct package name
        query_res = filter_version(query_res, app, version_selector)
        # XXX: As it's possible to include version information in `template`,
        #      perhaps the messages can be improved
        if len(query_res) == 0:
            if version_selector == VersionSelector.LATEST:
                raise qubesadmin.exc.QubesVMNotFoundError(
                    f"Template '{template}' not found.")
            elif version_selector == VersionSelector.REINSTALL:
                raise qubesadmin.exc.QubesVMNotFoundError(
                    f"Same version of template '{template}' not found.")
            # Copy behavior of DNF and do nothing if version not found
            elif version_selector == VersionSelector.LATEST_LOWER:
                log.warning(f"Template '{template}' of lowest version already "
                            f"installed, skipping...")
            elif version_selector == VersionSelector.LATEST_HIGHER:
                log.warning(f"Template '{template}' of highest version already "
                            f"installed, skipping...")

        # Merge & choose the template with the highest version
        for entry in query_res:
            if entry.name not in full_candid \
                    or rpm.labelCompare(full_candid[entry.name].evr,
                                        entry.evr) < 0:
                full_candid[entry.name] = \
                    DlEntry(entry.evr, entry.reponame, entry.dlsize)

    return full_candid


def download(
        app: qubesadmin.app.QubesBase,
        downloaddir: str,
        keyring: str,
        repos: typing.List[typing.Tuple[str, str]],
        releasever: str,
        repo_files: typing.List[str],
        templates: typing.Optional[typing.List[str]] = None,
        updatevm: typing.Optional[str] = None,
        dl_list: typing.Optional[typing.Dict[str, DlEntry]] = None,
        version_selector: VersionSelector = VersionSelector.LATEST,
        retries: int = 5,
        nogpgcheck: bool = False,
        progress_callback: typing.Optional[
            typing.Callable[[str, typing.Optional[int], int], None]] = None,
) -> typing.Dict[str, rpm.hdr]:
    """Download template packages.

    :param app: Qubes application object
    :param downloaddir: Directory to store downloaded templates
    :param keyring: Path to default GPG keyring for verification
    :param repos: List of (operation, repo_id) tuples for repo configuration
    :param releasever: Qubes release version
    :param repo_files: List of paths to repo configuration files
    :param templates: List of template names to download. Required if dl_list
        is not provided.
    :param updatevm: VM to download updates from
    :param dl_list: Override list of templates to download. If not set,
        ``get_dl_list`` is called using ``templates``.
    :param version_selector: Specify algorithm to select the candidate version
        of a package.  Defaults to ``VersionSelector.LATEST``
    :param retries: Number of download retry attempts
    :param nogpgcheck: If True, log warning that nogpgcheck is ignored
    :param progress_callback: Optional callback for progress updates.
        Called with (spec, current_bytes, total_bytes). current_bytes==None
        signals the start of a new download.
    :return: Package headers of downloaded templates
    """
    if dl_list is None:
        if templates is None:
            raise qubesadmin.exc.QubesException(
                'Either templates or dl_list must be provided')
        dl_list = get_dl_list(app, templates, repos, releasever,
                              repo_files, updatevm,
                              version_selector=version_selector)

    keys = get_keys_for_repos(repo_files, releasever)

    package_hdrs = {}

    with tempfile.TemporaryDirectory(dir=downloaddir) as dl_dir:
        for name, entry in dl_list.items():
            version_str = build_version_str(entry.evr)
            spec = PACKAGE_NAME_PREFIX + name + '-' + version_str
            target = os.path.join(downloaddir, f'{spec}.rpm')
            target_temp = os.path.join(dl_dir, f'{spec}.rpm.UNTRUSTED')
            repo_key = keys.get(entry.reponame)
            if repo_key is None:
                repo_key = keyring
            if os.path.exists(target):
                log.info("'%s' already exists, skipping...", target)
                # but still verify the package
                package_hdrs[name] = verify_rpm(
                    target, repo_key, template_name=name)
                continue
            log.info("Downloading '%s'...", spec)
            # Signal start of new download
            if progress_callback:
                progress_callback(spec, None, entry.dlsize)
            done = False
            for attempt in range(retries):
                try:
                    # Create inner callback that adds spec to the call
                    if progress_callback:
                        def inner_callback(current: int, total: int,
                                           spec: str = spec) -> None:
                            progress_callback(spec, current, total)
                    else:
                        inner_callback = None
                    qrexec_download(app, spec, target_temp, repo_key,
                                    repos, releasever,
                                    repo_files, updatevm,
                                    entry.dlsize,
                                    progress_callback=inner_callback)
                    done = True
                    break
                except ConnectionError:
                    try:
                        os.remove(target_temp)
                    except FileNotFoundError:
                        pass
                    if attempt + 1 < retries:
                        log.warning("'%s' download failed, retrying...", spec)
            if not done:
                raise ConnectionError(f"'{spec}' download failed.")

            if nogpgcheck:
                log.warning('--nogpgcheck is ignored for downloaded templates')
            package_hdr = verify_rpm(target_temp, repo_key, template_name=name)
            # after package is verified, rename to the target location
            os.rename(target_temp, target)
            package_hdrs[name] = package_hdr
    return package_hdrs


def list_templates(
        app: qubesadmin.app.QubesBase,
        repos: typing.List[typing.Tuple[str, str]],
        releasever: str,
        repo_files: typing.List[str],
        updatevm: typing.Optional[str] = None,
        templates: typing.Optional[typing.List[str]] = None,
        installed: bool = False,
        available: bool = False,
        extras: bool = False,
        upgrades: bool = False,
        all_versions: bool = False,
) -> typing.Dict[TemplateState, typing.List[
        typing.Tuple[Template, typing.Optional[str]]]]:
    """Query templates based on filters.

    :param app: Qubes application object
    :param repos: List of (operation, repo_id) tuples for repo configuration
    :param releasever: Qubes release version
    :param repo_files: List of paths to repo configuration files
    :param updatevm: VM to download updates from
    :param templates: Optional list of template specs to filter by
    :param installed: Include installed templates
    :param available: Include available templates from repos
    :param extras: Include extras (installed but not in repos)
    :param upgrades: Include available upgrades
    :param all_versions: Show all versions, not just latest

    :return: Dict mapping TemplateState to list of (Template, install_time)
        tuples. install_time is None for non-installed templates.
    """
    result: typing.Dict[TemplateState, typing.List[
        typing.Tuple[Template, typing.Optional[str]]]] = {}

    def check_append(name: str, evr: typing.Tuple[str, str, str]) -> bool:
        return not templates or \
            any(is_match_spec(name, *evr, spec)[0] for spec in templates)

    def append_vm(vm: qubesadmin.vm.QubesVM) -> typing.Tuple[
            Template, typing.Optional[str]]:
        return (query_local(vm), vm.features['template-installtime'])

    query_res: typing.List[Template] = []
    if available or extras or upgrades:
        if templates:
            query_res_set: typing.Set[Template] = set()
            for spec in templates:
                query_res_set |= set(qrexec_repoquery(
                    app, repos, releasever, repo_files,
                    updatevm, PACKAGE_NAME_PREFIX + spec))
            query_res = list(query_res_set)
        else:
            query_res = qrexec_repoquery(app, repos, releasever,
                                         repo_files, updatevm)
        if not all_versions:
            query_res = filter_version(query_res, app)

    if installed:
        for vm in app.domains:
            if is_managed_template(vm) and \
                    check_append(vm.name, query_local_evr(vm)):
                result.setdefault(TemplateState.INSTALLED, []).append(append_vm(vm))

    if available:
        # Spec should already be checked by repoquery
        for data in query_res:
            result.setdefault(TemplateState.AVAILABLE, []).append((data, None))

    if extras:
        result[TemplateState.EXTRA] = []
        remote = set()
        for data in query_res:
            remote.add(data.name)
        for vm in app.domains:
            if is_managed_template(vm) and vm.name not in remote and \
                    check_append(vm.name, query_local_evr(vm)):
                result.setdefault(TemplateState.EXTRA, []).append(append_vm(vm))

    if upgrades:
        local: typing.Dict[str, typing.Tuple[str, str, str]] = {}
        for vm in app.domains:
            if is_managed_template(vm):
                local[vm.name] = query_local_evr(vm)
        # Spec should already be checked by repoquery
        for entry in query_res:
            evr = (entry.epoch, entry.version, entry.release)
            if entry.name in local:
                if rpm.labelCompare(local[entry.name], evr) < 0:
                    result.setdefault(TemplateState.UPGRADABLE, []).append((entry, None))

    return result


def clean_cache(cachedir: os.PathLike[str]) -> None:
    """Clean the local package cache.

    :param cachedir: Path to the cache directory to remove
    """
    # TODO: More fine-grained options?

    shutil.rmtree(cachedir)


def migrate_from_rpmdb(app: qubesadmin.app.QubesBase):
    """Migrate templates stored in rpmdb, into 'features' set on the VM itself.
    """
    rpm_ts = rpm.TransactionSet()
    pkgs_to_remove = []
    for pkg in rpm_ts.dbMatch():
        if not pkg[rpm.RPMTAG_NAME].startswith('qubes-template-'):
            continue
        try:
            vm = app.domains[pkg[rpm.RPMTAG_NAME][len('qubes-template-'):]]
        except KeyError:
            # no longer present, remove from rpmdb
            pkgs_to_remove.append(pkg)
            continue
        if is_managed_template(vm):
            # already migrated, cleanup
            pkgs_to_remove.append(pkg)
            continue
        try:
            vm.features['template-name'] = vm.name
            vm.features['template-epoch'] = pkg[rpm.RPMTAG_EPOCHNUM]
            vm.features['template-version'] = pkg[rpm.RPMTAG_VERSION]
            vm.features['template-release'] = pkg[rpm.RPMTAG_RELEASE]
            vm.features['template-reponame'] = '@commandline'
            vm.features['template-buildtime'] = \
                datetime.datetime.fromtimestamp(
                    pkg[rpm.RPMTAG_BUILDTIME], tz=datetime.timezone.utc).\
                strftime(DATE_FMT)
            vm.features['template-installtime'] = \
                datetime.datetime.fromtimestamp(
                    pkg[rpm.RPMTAG_INSTALLTIME], tz=datetime.timezone.utc).\
                strftime(DATE_FMT)
            vm.features['template-license'] = pkg[rpm.RPMTAG_LICENSE]
            vm.features['template-url'] = pkg[rpm.RPMTAG_URL]
            vm.features['template-summary'] = pkg[rpm.RPMTAG_SUMMARY]
            vm.features['template-description'] = \
                pkg[rpm.RPMTAG_DESCRIPTION].replace('\n', '|')
            vm.installed_by_rpm = False
        except Exception as e:  # pylint: disable=broad-except
            log.warning('Failed to set template %s metadata: %s', vm.name, e)
            continue
        pkgs_to_remove.append(pkg)
    subprocess.check_call(
        ['rpm', '-e', '--justdb'] +
        [p[rpm.RPMTAG_NAME] for p in pkgs_to_remove])


def search_templates(
        app: qubesadmin.app.QubesBase,
        repos: typing.List[typing.Tuple[str, str]],
        releasever: str,
        repo_files: typing.List[str],
        keywords: typing.List[str],
        updatevm: typing.Optional[str] = None,
        search_all: bool = False,
) -> typing.Tuple[
        typing.List[Template],
        typing.List[typing.Tuple[int, typing.List[typing.Tuple[int, str, bool]]]]]:
    """Search template details for given patterns.

    :param app: Qubes application object
    :param repos: List of (repo_name, repo_url) tuples
    :param releasever: Qubes release version for repo URLs
    :param repo_files: List of paths to repo files
    :param keywords: List of keywords to search for
    :param updatevm: Name of the VM to use for updates (or None for default)
    :param search_all: If True, search description and URL fields, and allow
        partial keyword matches. If False, only search name and summary,
        and require all keywords to match.
    :return: Tuple of (query_res, search_res) where query_res is the list of
        templates and search_res is a sorted list of (index, matches) tuples
        where matches is a list of (weight, keyword, is_exact) tuples.
    """
    # Search in both installed and available templates
    query_res = qrexec_repoquery(app, repos, releasever,
                                 repo_files, updatevm)
    for vm in app.domains:
        if is_managed_template(vm):
            query_res.append(query_local(vm))

    # Get latest version for each template
    query_res_tmp = []
    for _, grp in itertools.groupby(sorted(query_res), lambda x: x[0]):
        def compare(lhs, rhs):
            return lhs if rpm.labelCompare(lhs[1:4], rhs[1:4]) > 0 else rhs

        query_res_tmp.append(functools.reduce(compare, grp))
    query_res = query_res_tmp

    search_res_by_idx: \
        typing.Dict[int, typing.List[typing.Tuple[int, str, bool]]] = \
        collections.defaultdict(list)
    for keyword in keywords:
        for idx, entry in enumerate(query_res):
            needle_types = \
                [(entry.name, WEIGHT_NAME), (entry.summary, WEIGHT_SUMMARY)]
            if search_all:
                needle_types += [(entry.description, WEIGHT_DESCRIPTION),
                                 (entry.url, WEIGHT_URL)]
            for key, weight in needle_types:
                if fnmatch.fnmatch(key, '*' + keyword + '*'):
                    exact = keyword == key
                    if exact and weight == WEIGHT_NAME:
                        weight = WEIGHT_NAME_EXACT
                    search_res_by_idx[idx].append((weight, keyword, exact))

    if not search_all:
        keywords_set = set(keywords)
        idxs = list(search_res_by_idx.keys())
        for idx in idxs:
            if keywords_set != set(x[1] for x in search_res_by_idx[idx]):
                del search_res_by_idx[idx]

    def key_func(x):
        # ORDER BY weight DESC, list_of_needles ASC, name ASC
        idx, needles = x
        weight = sum(t[0] for t in needles)
        name = query_res[idx][0]
        return -weight, needles, name

    search_res = sorted(search_res_by_idx.items(), key=key_func)

    return query_res, search_res


def install_template(
        app: qubesadmin.app.QubesBase,
        name: str,
        rpmfile: str,
        reponame: str,
        package_hdr: rpm.hdr,
        allow_pv: bool = False,
        skip_start: bool = False,
        pool: typing.Optional[str] = None,
        override_existing: bool = False,
) -> None:
    """Install a template from an RPM file.

    :param app: Qubes application object
    :param name: Template name
    :param rpmfile: Path to the RPM file
    :param reponame: Repository name the template came from
    :param package_hdr: RPM package header
    :param allow_pv: Whether to allow PV mode
    :param skip_start: Whether to skip starting the template
    :param pool: Storage pool to use (only for new installs)
    :param override_existing: Whether this is an override (reinstall/upgrade/downgrade)
    """
    with tempfile.TemporaryDirectory(dir=TEMP_DIR) as target:
        if not extract_rpm(name, rpmfile, target):
            raise qubesadmin.exc.QubesException(
                f'Failed to extract {name} template')
        cmdline = [
            'qvm-template-postprocess',
            '--really',
            '--no-installed-by-rpm',
        ]
        if allow_pv:
            cmdline.append('--allow-pv')
        if skip_start:
            cmdline.append('--skip-start')
        if not override_existing and pool:
            cmdline += ['--pool', pool]
        subprocess.check_call(cmdline + [
            'post-install',
            name,
            target + PATH_PREFIX + '/' + name])

        app.domains.refresh_cache(force=True)
        tpl = app.domains[name]

        tpl.features['template-name'] = name
        tpl.features['template-epoch'] = \
            package_hdr[rpm.RPMTAG_EPOCHNUM]
        tpl.features['template-version'] = \
            package_hdr[rpm.RPMTAG_VERSION]
        tpl.features['template-release'] = \
            package_hdr[rpm.RPMTAG_RELEASE]
        tpl.features['template-reponame'] = reponame
        tpl.features['template-buildtime'] = \
            datetime.datetime.fromtimestamp(
                    int(package_hdr[rpm.RPMTAG_BUILDTIME]),
                    tz=datetime.timezone.utc) \
                .strftime(DATE_FMT)
        tpl.features['template-installtime'] = \
            datetime.datetime.now(
                tz=datetime.timezone.utc).strftime(DATE_FMT)
        tpl.features['template-license'] = \
            package_hdr[rpm.RPMTAG_LICENSE]
        tpl.features['template-url'] = \
            package_hdr[rpm.RPMTAG_URL]
        tpl.features['template-summary'] = \
            package_hdr[rpm.RPMTAG_SUMMARY]
        tpl.features['template-description'] = \
            package_hdr[rpm.RPMTAG_DESCRIPTION].replace('\n', '|')


def get_dependents(
        app: qubesadmin.app.QubesBase,
        templates: typing.List[str],
) -> typing.List[str]:
    """Get all VMs that depend on the given templates, transitively.

    Uses BFS to find all VMs that depend on the given templates.

    :param app: Qubes application object
    :param templates: List of template names to find dependents for
    :return: List of dependent VM names (includes the original templates)
    """
    dependents = list(templates)
    visited = set(dependents)
    idx = 0
    while idx < len(dependents):
        tpl = dependents[idx]
        idx += 1
        vm = app.domains[tpl]
        for holder, prop in qubesadmin.utils.vm_dependencies(app, vm):
            if holder is not None and holder.name not in visited:
                dependents.append(holder.name)
                visited.add(holder.name)
    return dependents


def get_or_create_dummy_template(
        app: qubesadmin.app.QubesBase,
        dummy: str = 'dummy',
) -> qubesadmin.vm.QubesVM:
    """Get or create a dummy template for reassigning dependencies.

    :param app: Qubes application object
    :param dummy: Base name for the dummy template
    :return: The dummy template VM
    """
    orig_dummy = dummy
    cnt = 1
    while dummy in app.domains and \
            app.domains[dummy].features.get('template-dummy', '0') != '1':
        dummy = f'{orig_dummy}-{cnt:d}'
        cnt += 1
    if dummy not in app.domains:
        dummy_vm = app.add_new_vm('TemplateVM', dummy, 'red')
        dummy_vm.features['template-dummy'] = 1
    else:
        dummy_vm = app.domains[dummy]
    return dummy_vm


def reassign_template_dependencies(
        app: qubesadmin.app.QubesBase,
        templates: typing.List[str],
        dummy_vm: qubesadmin.vm.QubesVM,
) -> typing.List[typing.Tuple[typing.Optional[str], str, str]]:
    """Reassign VMs that depend on templates to a dummy template.

    :param app: Qubes application object
    :param templates: List of template names being removed
    :param dummy_vm: The dummy template to reassign to
    :return: List of (holder_name, property, dummy_name) tuples describing
        what was changed. holder_name is None for global properties.
    """
    changes = []
    for tpl in templates:
        vm = app.domains[tpl]
        for holder, prop in qubesadmin.utils.vm_dependencies(app, vm):
            if holder:
                setattr(holder, prop, dummy_vm)
                holder.template = dummy_vm
                changes.append((holder.name, prop, dummy_vm.name))
            else:
                setattr(app, prop, '')
                changes.append((None, prop, ''))
    return changes
