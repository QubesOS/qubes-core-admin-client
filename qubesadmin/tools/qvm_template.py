#!/usr/bin/env python3

'''Tool for managing VM templates.'''

import argparse
import collections
import datetime
import enum
import fnmatch
import functools
import itertools
import operator
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import typing

import qubesadmin
import qubesadmin.tools
import rpm
import tqdm
import xdg.BaseDirectory

PATH_PREFIX = '/var/lib/qubes/vm-templates'
TEMP_DIR = '/var/tmp'
PACKAGE_NAME_PREFIX = 'qubes-template-'
CACHE_DIR = os.path.join(xdg.BaseDirectory.xdg_cache_home, 'qvm-template')
UNVERIFIED_SUFFIX = '.unverified'
LOCK_FILE = '/var/tmp/qvm-template.lck'

def qubes_release() -> str:
    """Return the Qubes release."""
    if os.path.exists('/usr/share/qubes/marker-vm'):
        with open('/usr/share/qubes/marker-vm', 'r') as fd:
            # Get last line (in the format `x.x`)
            return fd.readlines()[-1].strip()
    return subprocess.check_output(['lsb_release', '-sr'],
        encoding='UTF-8').strip()

def parser_gen() -> argparse.ArgumentParser:
    """Generate argument parser for the application."""
    formatter = argparse.ArgumentDefaultsHelpFormatter
    parser_main = argparse.ArgumentParser(description='Qubes Template Manager',
        formatter_class=formatter)
    subparsers = parser_main.add_subparsers(dest='operation', required=True,
        description='Command to run.')

    def parser_add_command(cmd, help_str, add_help=True):
        return subparsers.add_parser(cmd, formatter_class=formatter,
            help=help_str, description=help_str, add_help=add_help)

    # qrexec/DNF related
    parser_main.add_argument('--repo-files', action='append',
        default=['/usr/share/qubes/repo-templates/qubes-templates.repo'],
        help='Specify files containing DNF repository configuration.')
    parser_main.add_argument('--updatevm', default='sys-firewall',
        help='Specify VM to download updates from.')
    parser_main.add_argument('--enablerepo', action='append', default=[],
        help='Enable additional repositories.')
    parser_main.add_argument('--disablerepo', action='append', default=[],
        help='Disable certain repositories.')
    parser_main.add_argument('--repoid', action='append', default=[],
        help='Enable just specific repositories.')
    parser_main.add_argument('--releasever', default=qubes_release(),
        help='Override distro release version.')
    parser_main.add_argument('--refresh', action='store_true',
        help='Set repository metadata as expired before running the command.')
    parser_main.add_argument('--cachedir', default=CACHE_DIR,
        help='Specify cache directory.')
    # qvm-template {install,reinstall,downgrade,upgrade}
    parser_install = parser_add_command('install',
        help_str='Install template packages.')
    parser_install.add_argument('--pool',
        help='Specify pool to store created VMs in.')
    parser_reinstall = parser_add_command('reinstall',
        help_str='Reinstall template packages.')
    parser_downgrade = parser_add_command('downgrade',
        help_str='Downgrade template packages.')
    parser_upgrade = parser_add_command('upgrade',
        help_str='Upgrade template packages.')
    for parser_x in [parser_install, parser_reinstall,
            parser_downgrade, parser_upgrade]:
        parser_x.add_argument('--nogpgcheck', action='store_true',
            help='Disable signature checks.')
        parser_x.add_argument('--allow-pv', action='store_true',
            help='Allow setting virt_mode to pv in configuration file.')
        parser_x.add_argument('templates', nargs='*', metavar='TEMPLATE')
    # qvm-template download
    parser_download = parser_add_command('download',
        help_str='Download template package.')
    for parser_x in [parser_install, parser_reinstall,
            parser_downgrade, parser_upgrade, parser_download]:
        parser_x.add_argument('--downloaddir', default='.',
            help='Specify download directory.')
        parser_x.add_argument('--retries', default=5, type=int,
            help='Specify number of retries for downloads.')
    parser_download.add_argument('templates', nargs='*', metavar='TEMPLATE')
    # qvm-template {list,info}
    parser_list = parser_add_command('list',
        help_str='List templates.')
    parser_info = parser_add_command('info',
        help_str='Display details about templates.')
    for parser_x in [parser_list, parser_info]:
        parser_x.add_argument('--all', action='store_true',
            help='Show all templates (default).')
        parser_x.add_argument('--installed', action='store_true',
            help='Show installed templates.')
        parser_x.add_argument('--available', action='store_true',
            help='Show available templates.')
        parser_x.add_argument('--extras', action='store_true',
            help=('Show extras (e.g., ones that exists'
                ' locally but not in repos) templates.'))
        parser_x.add_argument('--upgrades', action='store_true',
            help='Show upgradable templates.')
        parser_x.add_argument('--machine-readable', action='store_true',
            help='Enable machine-readable output.')
        parser_x.add_argument('templates', nargs='*', metavar='TEMPLATE')
    # qvm-template search
    parser_search = parser_add_command('search',
        help_str='Search template details for the given string.')
    parser_search.add_argument('--all', action='store_true',
        help=('Search also in template description and URL. In addition,'
            ' the criterion are evaluated with OR instead of AND.'))
    parser_search.add_argument('templates', nargs='*', metavar='PATTERN')
    # qvm-template remove
    parser_remove = parser_add_command('remove',
        help_str='Remove installed templates.',
        add_help=False) # Forward --help to qvm-remove
    _ = parser_remove # unused
    # qvm-template clean
    parser_clean = parser_add_command('clean',
        help_str='Remove cached data.')
    _ = parser_clean # unused
    # qvm-template repolist
    parser_repolist = parser_add_command('repolist',
        help_str='Show configured repositories.')
    repolim = parser_repolist.add_mutually_exclusive_group()
    repolim.add_argument('--all', action='store_true',
        help='Show all repos.')
    repolim.add_argument('--enabled', action='store_true',
        help='Show enabled repos (default).')
    repolim.add_argument('--disabled', action='store_true',
        help='Show disabled repos.')
    parser_repolist.add_argument('repos', nargs='*', metavar='REPOS')

    return parser_main

parser = parser_gen()

class TemplateState(enum.Enum):
    """Enum representing the state of a template."""
    INSTALLED = 'installed'
    AVAILABLE = 'available'
    EXTRA = 'extra'
    UPGRADABLE = 'upgradable'

    def title(self) -> str:
        """Return a long description of the state. Can be used as headings."""
        #pylint: disable=invalid-name
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

class DlEntry(typing.NamedTuple):
    """Information about a template to be downloaded."""
    evr: typing.Tuple[str, str, str]
    reponame: str
    dlsize: int

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
    if epoch != 0:
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
        vm.features['template-buildtime'],
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
    and is managed by qvm-template, otherwise raise a parser error."""
    if name not in app.domains:
        parser.error("Template '%s' not already installed." % name)
    vm = app.domains[name]
    if not is_managed_template(vm):
        parser.error("Template '%s' is not managed by qvm-template." % name)
    return vm

def qrexec_popen(
        args: argparse.Namespace,
        app: qubesadmin.app.QubesBase,
        service: str,
        stdout: typing.Union[int, typing.IO] = subprocess.PIPE,
        filter_esc: bool = True) -> subprocess.Popen:
    """Return ``Popen`` object that communicates with the given qrexec call in
    ``args.updatevm``.

    Note that this falls back to invoking ``/etc/qubes-rpc/*`` directly if
    ``args.updatevm`` is None.

    :param args: Arguments received by the application. ``args.updatevm`` is
        used
    :param app: Qubes application object
    :param service: The qrexec call to invoke
    :param stdout: Where the process stdout points to. This is passed directly
        to ``subprocess.Popen``. Defaults to ``subprocess.PIPE``

        Note that stderr is always set to ``subprocess.PIPE``
    :param filter_esc: Whether to filter out escape sequences from
        stdout/stderr. Defaults to True

    :returns: ``Popen`` object that communicates with the given qrexec call
    """
    if args.updatevm:
        return app.domains[args.updatevm].run_service(
            service,
            filter_esc=filter_esc,
            stdout=stdout)
    return subprocess.Popen([
            '/etc/qubes-rpc/%s' % service,
        ],
        stdin=subprocess.PIPE,
        stdout=stdout,
        stderr=subprocess.PIPE)

def qrexec_payload(args: argparse.Namespace, app: qubesadmin.app.QubesBase,
        spec: str, refresh: bool) -> str:
    """Return payload string for the ``qubes.Template*`` qrexec calls.

    :param args: Arguments received by the application. Specifically,
        ``args.{enablerepo,disablerepo,repoid,releasever,repo_files}`` are used
    :param app: Qubes application object
    :param spec: Package spec to query (refer to ``<package-name-spec>`` in the
        DNF documentation)
    :param refresh: Whether to force refresh repo metadata

    :return: Payload string

    :raises: Parser error if spec equals ``---`` or input contains ``\\n``
    """
    _ = app # unused

    if spec == '---':
        parser.error("Malformed template name: argument should not be '---'.")

    def check_newline(string, name):
        if '\n' in string:
            parser.error(f"Malformed {name}:" +
                " argument should not contain '\\n'.")

    payload = ''
    for repo in args.enablerepo:
        check_newline(repo, '--enablerepo')
        payload += '--enablerepo=%s\n' % repo
    for repo in args.disablerepo:
        check_newline(repo, '--disablerepo')
        payload += '--disablerepo=%s\n' % repo
    for repo in args.repoid:
        check_newline(repo, '--repoid')
        payload += '--repoid=%s\n' % repo
    if refresh:
        payload += '--refresh\n'
    check_newline(args.releasever, '--releasever')
    payload += '--releasever=%s\n' % args.releasever
    check_newline(spec, 'template name')
    payload += spec + '\n'
    payload += '---\n'
    for path in args.repo_files:
        with open(path, 'r') as fd:
            payload += fd.read() + '\n'
    return payload

def qrexec_repoquery(
        args: argparse.Namespace,
        app: qubesadmin.app.QubesBase,
        spec: str = '*',
        refresh: bool = False) -> typing.List[Template]:
    """Query template information from repositories.

    :param args: Arguments received by the application. Specifically,
        ``args.{enablerepo,disablerepo,repoid,releasever,repo_files,updatevm}``
        are used
    :param app: Qubes application object
    :param spec: Package spec to query (refer to ``<package-name-spec>`` in the
        DNF documentation). Defaults to ``*``
    :param refresh: Whether to force refresh repo metadata. Defaults to False

    :raises ConnectionError: if the qrexec call fails

    :return: List of ``Template`` objects representing the result of the query
    """
    payload = qrexec_payload(args, app, spec, refresh)
    proc = qrexec_popen(args, app, 'qubes.TemplateSearch')
    stdout, stderr = proc.communicate(payload.encode('UTF-8'))
    stdout = stdout.decode('ASCII')
    if proc.wait() != 0:
        for line in stderr.decode('ASCII').rstrip().split('\n'):
            print('[Qrexec] %s' % line, file=sys.stderr)
        raise ConnectionError("qrexec call 'qubes.TemplateSearch' failed.")
    name_re = re.compile(r'^[A-Za-z0-9._+\-]*$')
    evr_re = re.compile(r'^[A-Za-z0-9._+~]*$')
    date_re = re.compile(r'^\d+-\d+-\d+ \d+:\d+$')
    licence_re = re.compile(r'^[A-Za-z0-9._+\-()]*$')
    result = []
    for line in stdout.split('|\n'):
        # Note that there's an empty entry at the end as .strip() is not used.
        # This is because if .strip() is used, the .split() will not work.
        if line == '':
            continue
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
            if not re.fullmatch(date_re, buildtime):
                raise ValueError
            buildtime = datetime.datetime.strptime(buildtime, '%Y-%m-%d %H:%M')
            # XXX: Perhaps whitelist licenses directly?
            if not re.fullmatch(licence_re, licence):
                raise ValueError
            # Check name actually matches spec
            if not is_match_spec(name, epoch, version, release, spec):
                continue

            result.append(Template(name, epoch, version, release, reponame,
                dlsize, buildtime, licence, url, summary, description))
        except (TypeError, ValueError):
            raise ConnectionError(("qrexec call 'qubes.TemplateSearch' failed:"
                " unexpected data format."))
    return result

def qrexec_download(
        args: argparse.Namespace,
        app: qubesadmin.app.QubesBase,
        spec: str,
        path: str,
        dlsize: typing.Optional[int] = None,
        refresh: bool = False) -> None:
    """Download a template from repositories.

    :param args: Arguments received by the application. Specifically,
        ``args.{enablerepo,disablerepo,repoid,releasever,repo_files,updatevm}``
        are used
    :param app: Qubes application object
    :param spec: Package spec to query (refer to ``<package-name-spec>`` in the
        DNF documentation)
    :param path: Path to place the downloaded template
    :param dlsize: Size of template to be downloaded. Used for the progress
        bar. Optional
    :param refresh: Whether to force refresh repo metadata. Defaults to False

    :raises ConnectionError: if the qrexec call fails
    """
    with open(path, 'wb') as fd:
        payload = qrexec_payload(args, app, spec, refresh)
        # Don't filter ESCs for binary files
        proc = qrexec_popen(args, app, 'qubes.TemplateDownload',
            stdout=fd, filter_esc=False)
        proc.stdin.write(payload.encode('UTF-8'))
        proc.stdin.close()
        with tqdm.tqdm(desc=spec, total=dlsize, unit_scale=True,
                unit_divisor=1000, unit='B') as pbar:
            last = 0
            while proc.poll() is None:
                cur = fd.tell()
                pbar.update(cur - last)
                last = cur
                time.sleep(0.1)
        if proc.wait() != 0:
            raise ConnectionError(
                "qrexec call 'qubes.TemplateDownload' failed.")

def verify_rpm(
        path: str,
        nogpgcheck: bool = False,
        transaction_set: typing.Optional[rpm.transaction.TransactionSet] = None
        ) -> bool:
    """Verify the digest and signature of a RPM package.

    Note that verifying RPMs this way is prone to TOCTOU. This is okay for
    local files, but may create problems if multiple instances of
    **qvm-template** are downloading the same file, so a lock is needed in that
    case.

    :param path: Location of the RPM package
    :param nogpgcheck: Whether to allow invalid GPG signatures
    :param transaction_set: Override RPM ``TransactionSet``. Optional

    :return: Whether the RPM is verified
    """
    if transaction_set is None:
        transaction_set = rpm.TransactionSet()
    with open(path, 'rb') as fd:
        try:
            hdr = transaction_set.hdrFromFdno(fd)
            if hdr[rpm.RPMTAG_SIGSIZE] is None \
                    and hdr[rpm.RPMTAG_SIGPGP] is None \
                    and hdr[rpm.RPMTAG_SIGGPG] is None:
                return nogpgcheck
        except rpm.error as e:
            if str(e) == 'public key not trusted' \
                    or str(e) == 'public key not available':
                return nogpgcheck
            return False
    return True

def get_package_hdr(
        path: str,
        transaction_set: typing.Optional[rpm.transaction.TransactionSet] = None
        ) -> rpm.hdr:
    """Return header of a RPM package.

    Note that this function **does not** check the integrity of the package.

    :param path: Location of the RPM package
    :param transaction_set: Override RPM ``TransactionSet``. Optional

    :return: RPM headers
    """
    if transaction_set is None:
        transaction_set = rpm.TransactionSet()
    with open(path, 'rb') as fd:
        hdr = transaction_set.hdrFromFdno(fd)
        return hdr

def extract_rpm(name: str, path: str, target: str) -> bool:
    """Extract a template RPM package.

    :param name: Name of the template
    :param path: Location of the RPM package
    :param target: Target path to extract to

    :return: Whether the extraction succeeded
    """
    rpm2cpio = subprocess.Popen(['rpm2cpio', path], stdout=subprocess.PIPE)
    # `-D` is GNUism
    cpio = subprocess.Popen([
            'cpio',
            '-idm',
            '-D',
            target,
            '.%s/%s/*' % (PATH_PREFIX, name)
        ], stdin=rpm2cpio.stdout, stdout=subprocess.DEVNULL)
    return rpm2cpio.wait() == 0 and cpio.wait() == 0

def get_dl_list(
        args: argparse.Namespace,
        app: qubesadmin.app.QubesBase,
        version_selector: VersionSelector = VersionSelector.LATEST
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
    for template in args.templates:
        # This will be merged into `full_candid` later.
        # It is separated so that we can check whether it is empty.
        candid: typing.Dict[str, DlEntry] = {}

        # Skip local RPMs
        if template.endswith('.rpm'):
            continue

        query_res = qrexec_repoquery(args, app, PACKAGE_NAME_PREFIX + template)

        # We only select one package for each distinct package name
        for entry in query_res:
            ver = (entry.epoch, entry.version, entry.release)
            insert = False
            if version_selector == VersionSelector.LATEST:
                if entry.name not in candid \
                        or rpm.labelCompare(candid[entry.name][0], ver) < 0:
                    insert = True
            elif version_selector == VersionSelector.REINSTALL:
                vm = get_managed_template_vm(app, entry.name)
                cur_ver = query_local_evr(vm)
                if rpm.labelCompare(ver, cur_ver) == 0:
                    insert = True
            elif version_selector in [VersionSelector.LATEST_LOWER,
                    VersionSelector.LATEST_HIGHER]:
                vm = get_managed_template_vm(app, entry.name)
                cur_ver = query_local_evr(vm)
                cmp_res = -1 \
                    if version_selector == VersionSelector.LATEST_LOWER \
                    else 1
                if rpm.labelCompare(ver, cur_ver) == cmp_res:
                    if entry.name not in candid \
                            or rpm.labelCompare(candid[entry.name][0], ver) < 0:
                        insert = True
            if insert:
                candid[entry.name] = DlEntry(ver, entry.reponame, entry.dlsize)

        # XXX: As it's possible to include version information in `template`,
        #      perhaps the messages can be improved
        if len(candid) == 0:
            if version_selector == VersionSelector.LATEST:
                parser.error('Template \'%s\' not found.' % template)
            elif version_selector == VersionSelector.REINSTALL:
                parser.error('Same version of template \'%s\' not found.' \
                    % template)
            # Copy behavior of DNF and do nothing if version not found
            elif version_selector == VersionSelector.LATEST_LOWER:
                print(("Template '%s' of lowest version"
                    " already installed, skipping..." % template),
                    file=sys.stderr)
            elif version_selector == VersionSelector.LATEST_HIGHER:
                print(("Template '%s' of highest version"
                    " already installed, skipping..." % template),
                    file=sys.stderr)

        # Merge & choose the template with the highest version
        for name, dlentry in candid.items():
            if name not in full_candid \
                    or rpm.labelCompare(full_candid[name].evr, dlentry.evr) < 0:
                full_candid[name] = dlentry

    return full_candid

def download(
        args: argparse.Namespace,
        app: qubesadmin.app.QubesBase,
        path_override: typing.Optional[str] = None,
        dl_list: typing.Optional[typing.Dict[str, DlEntry]] = None,
        suffix: str = '',
        version_selector: VersionSelector = VersionSelector.LATEST) -> None:
    """Command that downloads template packages.

    :param args: Arguments received by the application.
    :param app: Qubes application object
    :param path_override: Override path to store downloads. If not set or set
        to None, ``args.downloaddir`` is used. Optional
    :param dl_list: Override list of templates to download. If not set or set
        to None, ``get_dl_list`` is called, which generates the list from
        ``args``.  Optional
    :param suffix: Suffix to add to the file name of downloaded packages. This
        is useful if you want to distinguish between verified and unverified
        packages. Defaults to an empty string
    :param version_selector: Specify algorithm to select the candidate version
        of a package.  Defaults to ``VersionSelector.LATEST``
    """
    if dl_list is None:
        dl_list = get_dl_list(args, app, version_selector=version_selector)

    path = path_override if path_override is not None else args.downloaddir
    for name, entry in dl_list.items():
        version_str = build_version_str(entry.evr)
        spec = PACKAGE_NAME_PREFIX + name + '-' + version_str
        target = os.path.join(path, '%s.rpm' % spec)
        target_suffix = target + suffix
        if suffix != '' and os.path.exists(target_suffix):
            print('\'%s\' already exists, skipping...' % target,
                file=sys.stderr)
        if os.path.exists(target):
            print('\'%s\' already exists, skipping...' % target,
                file=sys.stderr)
            if suffix != '':
                os.rename(target, target_suffix)
        else:
            print('Downloading \'%s\'...' % spec, file=sys.stderr)
            done = False
            for attempt in range(args.retries):
                try:
                    qrexec_download(args, app, spec, target_suffix,
                        entry.dlsize)
                    done = True
                    break
                except ConnectionError:
                    os.remove(target_suffix)
                    if attempt + 1 < args.retries:
                        print('\'%s\' download failed, retrying...' % spec,
                            file=sys.stderr)
                except:
                    # Also remove file if interrupted by other means
                    os.remove(target_suffix)
                    raise
            if not done:
                print('Error: \'%s\' download failed.' % spec, file=sys.stderr)
                sys.exit(1)

def install(
        args: argparse.Namespace,
        app: qubesadmin.app.QubesBase,
        version_selector: VersionSelector = VersionSelector.LATEST,
        override_existing: bool = False) -> None:
    """Command that installs template packages.

    This command creates a lock file to ensure that two instances are not
    running at the same time.

    :param args: Arguments received by the application.
    :param app: Qubes application object
    :param version_selector: Specify algorithm to select the candidate version
        of a package.  Defaults to ``VersionSelector.LATEST``
    :param override_existing: Whether to override existing packages. Used for
        reinstall, upgrade, and downgrade operations
    """
    try:
        with open(LOCK_FILE, 'x') as _:
            pass
    except FileExistsError:
        parser.error(('%s already exists.'
            ' Perhaps another instance of qvm-template is running?')
            % LOCK_FILE)

    try:
        transaction_set = rpm.TransactionSet()

        rpm_list = [] # rpmfile, reponame
        for template in args.templates:
            if template.endswith('.rpm'):
                if not os.path.exists(template):
                    parser.error('RPM file \'%s\' not found.' % template)
                rpm_list.append((template, '@commandline'))

        os.makedirs(args.cachedir, exist_ok=True)

        dl_list = get_dl_list(args, app, version_selector=version_selector)
        dl_list_copy = dl_list.copy()
        # Verify that the templates are not yet installed
        for name, entry in dl_list.items():
            # Should be ensured by checks in repoquery
            assert entry.reponame != '@commandline'
            if not override_existing and name in app.domains:
                print(('Template \'%s\' already installed, skipping...'
                    ' (You may want to use the'
                    ' {reinstall,upgrade,downgrade}'
                    ' operations.)') % name, file=sys.stderr)
                del dl_list_copy[name]
            else:
                version_str = build_version_str(entry.evr)
                target_file = \
                    '%s%s-%s.rpm' % (PACKAGE_NAME_PREFIX, name, version_str)
                rpm_list.append(
                    (os.path.join(args.cachedir, target_file), entry.reponame))
        dl_list = dl_list_copy

        download(args, app, path_override=args.cachedir,
            dl_list=dl_list, suffix=UNVERIFIED_SUFFIX,
            version_selector=version_selector)

        # Verify package and remove unverified suffix
        for rpmfile, reponame in rpm_list:
            if reponame != '@commandline':
                path = rpmfile + UNVERIFIED_SUFFIX
            else:
                path = rpmfile
            if not verify_rpm(path, args.nogpgcheck, transaction_set):
                parser.error('Package \'%s\' verification failed.' % rpmfile)
            if reponame != '@commandline':
                os.rename(path, rpmfile)

        # Unpack and install
        for rpmfile, reponame in rpm_list:
            with tempfile.TemporaryDirectory(dir=TEMP_DIR) as target:
                package_hdr = get_package_hdr(rpmfile)
                package_name = package_hdr[rpm.RPMTAG_NAME]
                if not package_name.startswith(PACKAGE_NAME_PREFIX):
                    parser.error(
                        'Illegal package name for package \'%s\'.' % rpmfile)
                # Remove prefix to get the real template name
                name = package_name[len(PACKAGE_NAME_PREFIX):]

                # Another check for already-downloaded RPMs
                if not override_existing and name in app.domains:
                    print(('Template \'%s\' already installed, skipping...'
                        ' (You may want to use the'
                        ' {reinstall,upgrade,downgrade}'
                        ' operations.)') % name, file=sys.stderr)
                    continue

                # Check if local versus candidate version is in line with the
                # operation
                if override_existing:
                    vm = get_managed_template_vm(app, name)
                    pkg_evr = (
                        str(package_hdr[rpm.RPMTAG_EPOCHNUM]),
                        package_hdr[rpm.RPMTAG_VERSION],
                        package_hdr[rpm.RPMTAG_RELEASE])
                    vm_evr = query_local_evr(vm)
                    cmp_res = rpm.labelCompare(pkg_evr, vm_evr)
                    if version_selector == VersionSelector.REINSTALL \
                            and cmp_res != 0:
                        parser.error(
                            'Same version of template \'%s\' not found.' \
                            % name)
                    elif version_selector == VersionSelector.LATEST_LOWER \
                            and cmp_res != -1:
                        print(("Template '%s' of lower version"
                            " already installed, skipping..." % name),
                            file=sys.stderr)
                        continue
                    elif version_selector == VersionSelector.LATEST_HIGHER \
                            and cmp_res != 1:
                        print(("Template '%s' of higher version"
                            " already installed, skipping..." % name),
                            file=sys.stderr)
                        continue

                print('Installing template \'%s\'...' % name, file=sys.stderr)
                extract_rpm(name, rpmfile, target)
                cmdline = [
                    'qvm-template-postprocess',
                    '--really',
                    '--no-installed-by-rpm',
                ]
                if args.allow_pv:
                    cmdline.append('--allow-pv')
                if args.pool:
                    cmdline += ['--pool', args.pool]
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
                    str(datetime.datetime.fromtimestamp(
                        int(package_hdr[rpm.RPMTAG_BUILDTIME])))
                tpl.features['template-install-time'] = \
                    str(datetime.datetime.today())
                tpl.features['template-license'] = \
                    package_hdr[rpm.RPMTAG_LICENSE]
                tpl.features['template-url'] = \
                    package_hdr[rpm.RPMTAG_URL]
                tpl.features['template-summary'] = \
                    package_hdr[rpm.RPMTAG_SUMMARY]
                tpl.features['template-description'] = \
                    package_hdr[rpm.RPMTAG_DESCRIPTION].replace('\n', '|')
    finally:
        os.remove(LOCK_FILE)

def list_templates(args: argparse.Namespace,
        app: qubesadmin.app.QubesBase, operation: str) -> None:
    """Command that lists templates.

    :param args: Arguments received by the application.
    :param app: Qubes application object
    :param operation: If set to ``list``, display a listing similar to ``dnf
        list``. If set to ``info``, display detailed template information
        similar to ``dnf info``. Otherwise, an ``AssertionError`` is raised.
    """
    tpl_list = []

    def append_list(data, status, install_time=None):
        _ = install_time # unused
        version_str = build_version_str(
            (data.epoch, data.version, data.release))
        tpl_list.append((status, data.name, version_str, data.reponame))

    def append_info(data, status, install_time=None):
        tpl_list.append((status, data, install_time))

    def list_to_output(tpls):
        outputs = []
        for status, grp in itertools.groupby(tpls, lambda x: x[0]):
            outputs.append((status, list(map(lambda x: x[1:], grp))))
        return outputs

    def info_to_human_output(tpls):
        outputs = []
        for status, grp in itertools.groupby(tpls, lambda x: x[0]):
            output = []
            for _, data, install_time in grp:
                output.append(('Name', ':', data.name))
                output.append(('Epoch', ':', data.epoch))
                output.append(('Version', ':', data.version))
                output.append(('Release', ':', data.release))
                output.append(('Size', ':',
                    qubesadmin.utils.size_to_human(data.dlsize)))
                output.append(('Repository', ':', data.reponame))
                output.append(('Buildtime', ':', str(data.buildtime)))
                if install_time:
                    output.append(('Install time', ':', str(install_time)))
                output.append(('URL', ':', data.url))
                output.append(('License', ':', data.licence))
                output.append(('Summary', ':', data.summary))
                # Only show "Description" for the first line
                title = 'Description'
                for line in data.description.splitlines():
                    output.append((title, ':', line))
                    title = ''
                output.append((' ', ' ', ' ')) # empty line
            outputs.append((status, output))
        return outputs

    def info_to_machine_output(tpls, replace_newline=True):
        outputs = []
        for status, grp in itertools.groupby(tpls, lambda x: x[0]):
            output = []
            for _, data, install_time in grp:
                name, epoch, version, release, reponame, dlsize, \
                    buildtime, licence, url, summary, description = data
                dlsize = str(dlsize)
                buildtime = str(buildtime)
                install_time = str(install_time) if install_time else ''
                if replace_newline:
                    description = description.replace('\n', '|')
                output.append((name, epoch, version, release, reponame,
                    dlsize, buildtime, install_time, licence, url, summary,
                    description))
            outputs.append((status, output))
        return outputs

    if operation == 'list':
        append = append_list
    elif operation == 'info':
        append = append_info
    else:
        assert False and 'Unknown operation'

    def append_vm(vm, status):
        append(query_local(vm), status, vm.features['template-install-time'])

    if not (args.installed or args.available or args.extras or args.upgrades):
        args.all = True

    if args.all or args.available or args.extras or args.upgrades:
        if args.templates:
            query_res_set: typing.Set[Template] = set()
            for spec in args.templates:
                query_res_set |= set(qrexec_repoquery(args, app, spec))
            query_res = list(query_res_set)
        else:
            query_res = qrexec_repoquery(args, app)

    if args.installed or args.all:
        for vm in app.domains:
            if is_managed_template(vm):
                if not args.templates or \
                        any(is_match_spec(
                                vm.name,
                                *query_local_evr(vm),
                                spec)[0]
                            for spec in args.templates):
                    append_vm(vm, TemplateState.INSTALLED)

    if args.available or args.all:
        for data in query_res:
            append(data, TemplateState.AVAILABLE)

    if args.extras:
        remote = set()
        for data in query_res:
            remote.add(data.name)
        for vm in app.domains:
            if is_managed_template(vm) and vm.name not in remote:
                append_vm(vm, TemplateState.EXTRA)

    if args.upgrades:
        local = {}
        for vm in app.domains:
            if is_managed_template(vm):
                local[vm.name] = query_local_evr(vm)
        for entry in query_res:
            if entry.name in local:
                if rpm.labelCompare(local[entry.name],
                        (entry.epoch, entry.version, entry.release)) < 0:
                    append(entry, TemplateState.UPGRADABLE)

    if len(tpl_list) == 0:
        parser.error('No matching templates to list')

    if not args.machine_readable:
        if operation == 'info':
            tpl_list = info_to_human_output(tpl_list)
        elif operation == 'list':
            tpl_list = list_to_output(tpl_list)
        for status, grp in tpl_list:
            print(status.title())
            qubesadmin.tools.print_table(grp)
    else:
        if operation == 'info':
            tpl_list = info_to_machine_output(tpl_list)
        elif operation == 'list':
            tpl_list = list_to_output(tpl_list)
        for status, grp in tpl_list:
            print('|' + status.value)
            for line in grp:
                print('|'.join(line) + '|')

def search(args: argparse.Namespace, app: qubesadmin.app.QubesBase) -> None:
    """Command that searches template details for given patterns.

    :param args: Arguments received by the application.
    :param app: Qubes application object
    """
    # Search in both installed and available templates
    query_res = qrexec_repoquery(args, app)
    for vm in app.domains:
        if is_managed_template(vm):
            query_res.append(query_local(vm))

    # Get latest version for each template
    query_res_tmp = []
    for _, grp in itertools.groupby(sorted(query_res), lambda x: x[0]):
        def compare(lhs, rhs):
            return lhs if rpm.labelCompare(lhs[1:4], rhs[1:4]) < 0 else rhs
        query_res_tmp.append(functools.reduce(compare, grp))
    query_res = query_res_tmp

    #pylint: disable=invalid-name
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

    search_res_by_idx: \
            typing.Dict[int, typing.List[typing.Tuple[int, str, bool]]] = \
        collections.defaultdict(list)
    for keyword in args.templates:
        for idx, entry in enumerate(query_res):
            needle_types = \
                [(entry.name, WEIGHT_NAME), (entry.summary, WEIGHT_SUMMARY)]
            if args.all:
                needle_types += [(entry.description, WEIGHT_DESCRIPTION),
                            (entry.url, WEIGHT_URL)]
            for key, weight in needle_types:
                if fnmatch.fnmatch(key, '*' + keyword + '*'):
                    exact = keyword == key
                    if exact and weight == WEIGHT_NAME:
                        weight = WEIGHT_NAME_EXACT
                    search_res_by_idx[idx].append((weight, keyword, exact))

    if not args.all:
        keywords = set(args.templates)
        idxs = list(search_res_by_idx.keys())
        for idx in idxs:
            if keywords != set(x[1] for x in search_res_by_idx[idx]):
                del search_res_by_idx[idx]

    def key_func(x):
        # ORDER BY weight DESC, list_of_needles ASC, name ASC
        idx, needles = x
        weight = sum(t[0] for t in needles)
        name = query_res[idx][0]
        return (-weight, needles, name)

    search_res = sorted(search_res_by_idx.items(), key=key_func)

    def gen_header(needles):
        fields = []
        weight_types = set(x[0] for x in needles)
        for weight, field in WEIGHT_TO_FIELD:
            if weight in weight_types:
                fields.append(field)
        exact = all(x[-1] for x in needles)
        match = 'Exactly Matched' if exact else 'Matched'
        keywords = sorted(list(set(x[1] for x in needles)))
        return ' & '.join(fields) + ' ' + match + ': ' + ', '.join(keywords)

    last_header = ''
    for idx, needles in search_res:
        # Print headers
        cur_header = gen_header(needles)
        if last_header != cur_header:
            last_header = cur_header
            # XXX: The style is different from that of DNF
            print('===', cur_header, '===')
        print(query_res[idx].name, ':', query_res[idx].summary)

def remove(args: argparse.Namespace, app: qubesadmin.app.QubesBase) -> None:
    """Command that remove templates.

    :param args: Arguments received by the application.
    :param app: Qubes application object
    """
    _ = args, app # unused

    # Remove 'remove' entry from the args...
    operation_idx = sys.argv.index('remove')
    argv = sys.argv[1:operation_idx] + sys.argv[operation_idx+1:]

    # ...then pass the args to qvm-remove
    # Use exec so stdio can be shared easily
    os.execvp('qvm-remove', ['qvm-remove'] + argv)

def clean(args: argparse.Namespace, app: qubesadmin.app.QubesBase) -> None:
    """Command that cleans the local package cache.

    :param args: Arguments received by the application.
    :param app: Qubes application object
    """
    # TODO: More fine-grained options
    _ = app # unused

    shutil.rmtree(args.cachedir)

def repolist(args: argparse.Namespace, app: qubesadmin.app.QubesBase) -> None:
    """Command that lists configured repositories.

    :param args: Arguments received by the application.
    :param app: Qubes application object
    """
    _ = app # unused

    # python-dnf is not packaged on Debian
    # As this is not an "essential operation", the module is imported here
    # instead of top-level so that other operations still work.
    try:
        import dnf
    except ModuleNotFoundError:
        print("Error: Python module 'dnf' not found.", file=sys.stderr)
        sys.exit(1)

    if not args.all and not args.disabled:
        args.enabled = True

    with tempfile.TemporaryDirectory(dir=TEMP_DIR) as reposdir:
        for idx, path in enumerate(args.repo_files):
            src = os.path.abspath(path)
            # Use index as file name in case of collisions
            dst = os.path.join(reposdir, '%d.repo' % idx)
            os.symlink(src, dst)
        conf = dnf.conf.Conf()
        conf.substitutions['releasever'] = args.releasever
        conf.reposdir = reposdir
        base = dnf.Base(conf)
        base.read_all_repos()
        if args.repoid:
            base.repos.get_matching('*').disable()
            for repo in args.repoid:
                base.repos.get_matching(repo).enable()
        else:
            for repo in args.enablerepo:
                base.repos.get_matching(repo).enable()
            for repo in args.disablerepo:
                base.repos.get_matching(repo).disable()

        if args.repos:
            repos = []
            for repo in args.repos:
                repos += list(base.repos.get_matching(repo))
            repos = list(set(repos))
            repos.sort(key=operator.attrgetter('id'))
        else:
            repos = list(base.repos.values())
            repos.sort(key=operator.attrgetter('id'))

        table = []
        for repo in repos:
            if args.all or (args.enabled == repo.enabled):
                state = 'enabled' if repo.enabled else 'disabled'
                table.append((repo.id, repo.name, state))

        qubesadmin.tools.print_table(table)

def main(args: typing.Optional[typing.Sequence[str]] = None,
        app: typing.Optional[qubesadmin.app.QubesBase] = None) -> int:
    """Main routine of **qvm-template**.

    :param args: Override arguments received by the application. Optional
    :param app: Override Qubes application object. Optional

    :return: Return code of the application
    """
    p_args, unk_args = parser.parse_known_args(args)
    if p_args.operation != 'remove' and unk_args:
        p_args = parser.parse_args(args) # this should result in an error
        assert False and 'This line should not be executed.'
        # FIXME: Currently doing things this way as we have to forward
        # arguments to qvm-remove. While argparse.REMAINDER should be able to
        # solve this, there's a bug (issue 17050) that prevents it from working
        # on inputs where the first argument is an option, like 'qvm-template
        # remove --help'. The bug should be fixed in Python 3.9.

    # If the user specified other repo files...
    if len(p_args.repo_files) > 1:
        # ...remove the default entry
        p_args.repo_files.pop(0)

    if app is None:
        app = qubesadmin.Qubes()

    if p_args.refresh:
        qrexec_repoquery(p_args, app, refresh=True)

    if p_args.operation == 'download':
        download(p_args, app)
    elif p_args.operation == 'install':
        install(p_args, app)
    elif p_args.operation == 'reinstall':
        install(p_args, app, version_selector=VersionSelector.REINSTALL,
            override_existing=True)
    elif p_args.operation == 'downgrade':
        install(p_args, app, version_selector=VersionSelector.LATEST_LOWER,
            override_existing=True)
    elif p_args.operation == 'upgrade':
        install(p_args, app, version_selector=VersionSelector.LATEST_HIGHER,
            override_existing=True)
    elif p_args.operation == 'list':
        list_templates(p_args, app, 'list')
    elif p_args.operation == 'info':
        list_templates(p_args, app, 'info')
    elif p_args.operation == 'search':
        search(p_args, app)
    elif p_args.operation == 'remove':
        remove(p_args, app)
    elif p_args.operation == 'clean':
        clean(p_args, app)
    elif p_args.operation == 'repolist':
        repolist(p_args, app)
    else:
        parser.error('Operation \'%s\' not supported.' % p_args.operation)

    return 0

if __name__ == '__main__':
    sys.exit(main())
