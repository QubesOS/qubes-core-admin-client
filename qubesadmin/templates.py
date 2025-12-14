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
import configparser
import datetime
import enum
import fnmatch
import subprocess
import tempfile
import typing
import sys

import qubesadmin.app
import qubesadmin.exc
import qubesadmin.vm

DATE_FMT = '%Y-%m-%d %H:%M:%S'
PATH_PREFIX = '/var/lib/qubes/vm-templates'
PACKAGE_NAME_PREFIX = 'qubes-template-'
TAR_HEADER_BYTES = 512
WRAPPER_PAYLOAD_BEGIN = "###!Q!BEGIN-QUBES-WRAPPER!Q!###"
WRAPPER_PAYLOAD_END = "###!Q!END-QUBES-WRAPPER!Q!###"


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
            os.symlink(os.path.abspath(path),
                       f'{target}/{PATH_PREFIX}/{name}/template.rpm')
        except OSError as e:
            print(f"Failed to create {link_path} symlink: {e!s}",
                  file=sys.stderr)
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

def append_keys(payload, releasever):
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
