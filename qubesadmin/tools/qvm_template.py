#
# The Qubes OS Project, https://www.qubes-os.org/
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

"""Tool for managing VM templates."""

import argparse
import collections
import configparser
import datetime
import enum
import fcntl
import fnmatch
import functools
import glob
import itertools
import json
import operator
import os
import re
import shutil
import subprocess
import sys
import tempfile
import typing

import tqdm
import xdg.BaseDirectory
import rpm

import qubesadmin
import qubesadmin.exc
import qubesadmin.vm
import qubesadmin.utils
import qubesadmin.templates
import qubesadmin.tools
import qubesadmin.tools.qvm_kill
import qubesadmin.tools.qvm_remove

from qubesadmin.templates import (
    DATE_FMT,
    PACKAGE_NAME_PREFIX,
    PATH_PREFIX,
    DlEntry,
    Template,
    TemplateState,
    VersionSelector,
    build_version_str,
    clean,
    download as templates_download,
    get_dl_list,
    get_keys_for_repos,
    get_managed_template_vm,
    is_managed_template,
    list_templates as templates_list,
    locked,
    migrate_from_rpmdb,
    qrexec_payload,
    qrexec_popen,
    qrexec_repoquery,
    query_local,
    query_local_evr,
    qubes_release,
)

TEMP_DIR = '/var/tmp'
CACHE_DIR = os.path.join(xdg.BaseDirectory.xdg_cache_home, 'qvm-template')
UNVERIFIED_SUFFIX = '.unverified'

UPDATEVM = str('global UpdateVM')


class RepoOptCallback(argparse.Action):
    """Parser action for storing repository related options, like
    --enablerepo, --disablerepo, etc. Store them in a single list, to preserve
    relative order."""
    def __call__(self, parser_arg, namespace, values, option_string=None):
        operation = option_string.lstrip('-')
        repo_actions = getattr(namespace, self.dest)
        repo_actions.append((operation, values))


def get_parser() -> argparse.ArgumentParser:
    """Generate argument parser for the application."""
    formatter = argparse.ArgumentDefaultsHelpFormatter
    parser_main = qubesadmin.tools.QubesArgumentParser(
        description=__doc__, formatter_class=formatter)
    parser_main.register(
        'action', 'parsers', qubesadmin.tools.AliasedSubParsersAction)
    subparsers = parser_main.add_subparsers(
        dest='command', description='Command to run.')

    def parser_add_command(cmd, help_str):
        return subparsers.add_parser(
            cmd,
            formatter_class=formatter,
            help=help_str,
            description=help_str)

    parser_main.add_argument('--repo-files', action='append',
        default=['/etc/qubes/repo-templates/*.repo'],
        help=('Specify files containing DNF repository configuration.'
            ' Can be used more than once.'))
    parser_main.add_argument('--keyring',
        default='/etc/qubes/repo-templates/keys/'
                f'RPM-GPG-KEY-qubes-{qubes_release()}-primary',
        help='Specify a file containing default RPM public key. '
             'Individual repositories may point at repo-specific key '
             'using \'gpgkey\' option')
    parser_main.add_argument('--updatevm', default=UPDATEVM,
        help=('Specify VM to download updates from.'
            ' (Set to empty string to specify the current VM.)'))
    parser_main.add_argument('--enablerepo', action=RepoOptCallback, default=[],
        metavar='REPOID', dest='repos',
        help=('Enable additional repositories by an id or a glob.'
            ' Can be used more than once.'))
    parser_main.add_argument('--disablerepo', action=RepoOptCallback,
        default=[],
        metavar='REPOID', dest='repos',
        help=('Disable certain repositories by an id or a glob.'
            ' Can be used more than once.'))
    parser_main.add_argument('--repoid', action=RepoOptCallback, default=[],
        dest='repos',
        help=('Enable just specific repositories by an id or a glob.'
            ' Can be used more than once.'))
    parser_main.add_argument('--releasever', default=qubes_release(),
        help='Override Qubes release version.')
    parser_main.add_argument('--refresh', action='store_true',
        help='Set repository metadata as expired before running the command.')
    parser_main.add_argument('--cachedir', default=CACHE_DIR,
        help='Specify cache directory.')
    parser_main.add_argument('--keep-cache', action='store_true', default=False,
        help='Keep downloaded packages in cache dir')
    parser_main.add_argument('--yes', action='store_true',
        help='Assume "yes" to questions.')
    # qvm-template {install,reinstall,downgrade,upgrade}
    parser_install = parser_add_command('install',
        help_str='Install template packages.')
    parser_install.add_argument('--pool',
        help='Specify storage pool to store created templates in.')
    parser_reinstall = parser_add_command('reinstall',
        help_str='Reinstall template packages.')
    parser_downgrade = parser_add_command('downgrade',
        help_str='Downgrade template packages.')
    parser_upgrade = parser_add_command('upgrade',
        help_str='Upgrade template packages.')
    for parser_x in [parser_install, parser_reinstall,
            parser_downgrade, parser_upgrade]:
        parser_x.add_argument('--allow-pv', action='store_true',
            help='Allow templates that set virt_mode to pv.')
        parser_x.add_argument('--skip-start', action='store_true',
            help='Do not start templates to call their '
                 'qubes.PostInstall service.')
        parser_x.add_argument('templates', nargs='*', metavar='TEMPLATESPEC')

    # qvm-template download
    parser_download = parser_add_command('download',
        help_str='Download template packages.')
    for parser_x in [parser_install, parser_reinstall,
            parser_downgrade, parser_upgrade, parser_download]:
        parser_x.add_argument('--downloaddir', default='.',
            help='Specify download directory.')
        parser_x.add_argument('--retries', default=5, type=int,
            help='Specify maximum number of retries for downloads.')
        parser_x.add_argument('--nogpgcheck', action='store_true',
            help='Disable signature checks.')
    parser_download.add_argument('templates', nargs='*',
        metavar='TEMPLATESPEC')

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
            help=('Show extras (e.g., ones that exist'
                ' locally but not in repos) templates.'))
        parser_x.add_argument('--upgrades', action='store_true',
            help='Show available upgrades.')
        parser_x.add_argument('--all-versions', action='store_true',
            help='Show all available versions, not only the latest.')
        readable = parser_x.add_mutually_exclusive_group()
        readable.add_argument('--machine-readable', action='store_true',
            help='Enable machine-readable output.')
        readable.add_argument('--machine-readable-json', action='store_true',
            help='Enable machine-readable output (JSON).')
        parser_x.add_argument('templates', nargs='*', metavar='TEMPLATESPEC')

    # qvm-template search
    parser_search = parser_add_command('search',
        help_str='Search template details for the given string.')
    parser_search.add_argument('--all', action='store_true',
        help=('Search also in the template description and URL. In addition,'
            ' the criterion are evaluated with OR instead of AND.'))
    parser_search.add_argument('templates', nargs='*', metavar='PATTERN')

    # qvm-template remove
    parser_remove = parser_add_command('remove',
        help_str='Remove installed templates.')
    parser_remove.add_argument('--disassoc', action='store_true',
            help=('Also disassociate VMs from the templates to be removed.'
                ' This creates a dummy template for the VMs to link with.'))
    parser_remove.add_argument('templates', nargs='*', metavar='TEMPLATE')

    # qvm-template purge
    parser_purge = parser_add_command('purge',
        help_str='Remove installed templates and associated VMs.')
    parser_purge.add_argument('templates', nargs='*', metavar='TEMPLATE')

    # qvm-template clean
    parser_clean = parser_add_command('clean',
        help_str='Remove locally cached packages.')
    _ = parser_clean # unused

    # qvm-template repolist
    parser_repolist = parser_add_command('repolist',
        help_str='Show configured repositories.')
    repolim = parser_repolist.add_mutually_exclusive_group()
    repolim.add_argument('--all', action='store_true',
        help='Show all repos.')
    repolim.add_argument('--enabled', action='store_true',
        help='Show only enabled repos (default).')
    repolim.add_argument('--disabled', action='store_true',
        help='Show only disabled repos.')
    parser_repolist.add_argument('repos', nargs='*', metavar='REPOS')

    # qvm-template migrate-from-rpmdb
    parser_add_command('migrate-from-rpmdb',
        help_str='Import R4.0 templates info to R4.1 format')

    return parser_main


parser = get_parser()


def confirm_action(msg: str, affected: typing.List[str]) -> None:
    """Confirm user action."""
    print(msg)
    for name in affected:
        print('  ' + name)

    confirm = ''
    while confirm != 'y':
        confirm = input('Are you sure? [y/N] ').lower()
        if confirm != 'y':
            print('command cancelled.')
            sys.exit(1)


def _make_download_progress_callback(quiet: bool):
    """Create a progress callback for template downloads using tqdm."""
    pbar = None
    last_bytes = 0

    def callback(spec: str, current: typing.Optional[int], total: int) -> None:
        nonlocal pbar, last_bytes
        if current is None:
            if pbar is not None:
                pbar.close()
            pbar = tqdm.tqdm(desc=spec, total=total, unit_scale=True,
                             unit_divisor=1000, unit='B', disable=quiet)
            last_bytes = 0
        elif pbar is not None:
            pbar.update(current - last_bytes)
            last_bytes = current

    def cleanup():
        nonlocal pbar
        if pbar is not None:
            pbar.close()

    return callback, cleanup


def download(
        args: argparse.Namespace,
        app: qubesadmin.app.QubesBase,
        path_override: typing.Optional[str] = None,
        dl_list: typing.Optional[typing.Dict[str, DlEntry]] = None,
        version_selector: VersionSelector = VersionSelector.LATEST) \
        -> typing.Dict[str, rpm.hdr]:
    """Command that downloads template packages.

    :param args: Arguments received by the application.
    :param app: Qubes application object
    :param path_override: Override path to store downloads. If not set or set
        to None, ``args.downloaddir`` is used. Optional
    :param dl_list: Override list of templates to download. If not set or set
        to None, ``get_dl_list`` is called, which generates the list from
        ``args``.  Optional
    :param version_selector: Specify algorithm to select the candidate version
        of a package.  Defaults to ``VersionSelector.LATEST``
    :return package headers of downloaded templates
    """
    path = path_override if path_override is not None else args.downloaddir
    progress_callback, cleanup = _make_download_progress_callback(args.quiet)
    try:
        return templates_download(
            app=app,
            downloaddir=path,
            keyring=args.keyring,
            repos=args.repos,
            releasever=args.releasever,
            repo_files=args.repo_files,
            templates=args.templates if dl_list is None else None,
            updatevm=args.updatevm,
            dl_list=dl_list,
            version_selector=version_selector,
            retries=args.retries,
            nogpgcheck=args.nogpgcheck,
            progress_callback=progress_callback,
        )
    except (qubesadmin.exc.QubesVMNotFoundError,
            qubesadmin.exc.QubesVMError,
            qubesadmin.exc.QubesValueError) as e:
        parser.error(str(e))
    except ConnectionError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    finally:
        cleanup()


@locked
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
    keys = get_keys_for_repos(args.repo_files, args.releasever)

    unverified_rpm_list = []  # rpmfile, reponame
    verified_rpm_list = []

    def verify(rpmfile, reponame, package_hdr=None):
        """Verify package signature and version and parse package header.

        If package_hdr is provided, the signature check is skipped and only
        other checks are performed."""
        if package_hdr is None:
            repo_key = keys.get(reponame)
            if repo_key is None:
                repo_key = args.keyring
            package_hdr = qubesadmin.templates.verify_rpm(rpmfile, repo_key,
                                     nogpgcheck=args.nogpgcheck)
            if not package_hdr:
                parser.error(f"Package '{rpmfile}' verification failed.")

        package_name = package_hdr[rpm.RPMTAG_NAME]
        if not package_name.startswith(PACKAGE_NAME_PREFIX):
            parser.error(f"Illegal package name for package '{rpmfile}'.")
        # Remove prefix to get the real template name
        name = package_name[len(PACKAGE_NAME_PREFIX):]

        # Check if already installed
        if not override_existing and name in app.domains:
            print(f"Template '{name}' already installed, skipping..."
                   " (You may want to use the"
                   " {reinstall,upgrade,downgrade}"
                   " operations.)", file=sys.stderr)
            return

        # Check if version is really what we want
        if override_existing:
            try:
                vm = get_managed_template_vm(app, name)
            except (qubesadmin.exc.QubesVMNotFoundError,
                    qubesadmin.exc.QubesVMError) as e:
                parser.error(str(e))
            pkg_evr = (
                str(package_hdr[rpm.RPMTAG_EPOCHNUM]),
                package_hdr[rpm.RPMTAG_VERSION],
                package_hdr[rpm.RPMTAG_RELEASE])
            vm_evr = query_local_evr(vm)
            cmp_res = rpm.labelCompare(pkg_evr, vm_evr)
            if version_selector == VersionSelector.REINSTALL \
                    and cmp_res != 0:
                parser.error(f'Same version of template \'{name}\' not found.')
            elif version_selector == VersionSelector.LATEST_LOWER \
                    and cmp_res != -1:
                print(f"Template '{name}' of lower version "
                      f"already installed, skipping...",
                      file=sys.stderr)
                return
            elif version_selector == VersionSelector.LATEST_HIGHER \
                    and cmp_res != 1:
                print(f"Template '{name}' of higher version"
                       " already installed, skipping...",
                      file=sys.stderr)
                return

        verified_rpm_list.append((rpmfile, reponame, name, package_hdr))

    # Process local templates
    for template in args.templates:
        if template.endswith('.rpm'):
            if not os.path.exists(template):
                parser.error(f'RPM file \'{template}\' not found.')
            unverified_rpm_list.append((template, '@commandline'))

    # First verify local RPMs and extract header
    for rpmfile, reponame in unverified_rpm_list:
        verify(rpmfile, reponame)
    unverified_rpm_list = {}

    os.makedirs(args.cachedir, exist_ok=True)

    # Get list of templates to download
    try:
        dl_list = get_dl_list(app, args.templates, args.repos, args.releasever,
                            args.repo_files, args.updatevm,
                            version_selector=version_selector)
    except (qubesadmin.exc.QubesVMNotFoundError,
            qubesadmin.exc.QubesVMError) as e:
        parser.error(str(e))
    dl_list_copy = dl_list.copy()
    for name, entry in dl_list.items():
        # Should be ensured by checks in repoquery
        assert entry.reponame != '@commandline'
        # Verify that the templates to be downloaded are not yet installed
        # Note that we *still* have to do this again in verify() for
        # already-downloaded templates
        if not override_existing and name in app.domains:
            print(f"Template '{name}' already installed, skipping..."
                   " (You may want to use the"
                   " {reinstall,upgrade,downgrade}"
                   " operations.)", file=sys.stderr)
            del dl_list_copy[name]
        else:
            # XXX: Perhaps this is better returned by download()
            version_str = build_version_str(entry.evr)
            target_file = \
                f'{PACKAGE_NAME_PREFIX}{name}-{version_str}.rpm'
            unverified_rpm_list[name] = (
                (os.path.join(args.cachedir, target_file), entry.reponame))
    dl_list = dl_list_copy

    # Ask the user for confirmation before we actually download stuff
    if override_existing and not args.yes:
        override_tpls = []
        # Local templates, already verified
        for _, _, name, _ in verified_rpm_list:
            override_tpls.append(name)
        # Templates not yet downloaded
        for name in dl_list:
            override_tpls.append(name)

        # Only confirm if we have something to do
        # since confiming w/ an empty list is probably silly
        if override_tpls:
            confirm_action(
                'This will override changes made in the following VMs:',
                override_tpls)

    package_hdrs = download(args, app,
                            dl_list=dl_list,
                            path_override=args.cachedir,
                            version_selector=version_selector)

    # Verify downloaded templates
    for name, (rpmfile, reponame) in unverified_rpm_list.items():
        verify(rpmfile, reponame, package_hdrs[name])
    del unverified_rpm_list

    # Unpack and install
    for rpmfile, reponame, name, package_hdr in verified_rpm_list:
        with tempfile.TemporaryDirectory(dir=TEMP_DIR) as target:
            print(f'Installing template \'{name}\'...', file=sys.stderr)
            if not qubesadmin.templates.extract_rpm(name, rpmfile, target):
                raise qubesadmin.exc.QubesException(
                    f'Failed to extract {name} template')
            cmdline = [
                'qvm-template-postprocess',
                '--really',
                '--no-installed-by-rpm',
            ]
            if args.allow_pv:
                cmdline.append('--allow-pv')
            if args.skip_start:
                cmdline.append('--skip-start')
            if not override_existing and args.pool:
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
        if rpmfile.startswith(args.cachedir) and not args.keep_cache:
            os.remove(rpmfile)


def list_templates(args: argparse.Namespace,
                   app: qubesadmin.app.QubesBase, command: str) -> None:
    """Command that lists templates.

    :param args: Arguments received by the application.
    :param app: Qubes application object
    :param command: If set to ``list``, display a listing similar to ``dnf
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

    def list_to_human_output(tpls):
        outputs = []
        for status, grp in itertools.groupby(tpls, lambda x: x[0]):
            def convert(row):
                return row[1:]
            outputs.append((status, list(map(convert, grp))))
        return outputs

    def list_to_machine_output(tpls):
        outputs = {}
        for status, grp in itertools.groupby(tpls, lambda x: x[0]):
            def convert(row):
                _, name, evr, reponame = row
                return {'name': name, 'evr': evr, 'reponame': reponame}
            outputs[status.value] = list(map(convert, grp))
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
        outputs = {}
        for status, grp in itertools.groupby(tpls, lambda x: x[0]):
            output = []
            for _, data, install_time in grp:
                name, epoch, version, release, reponame, dlsize, \
                    buildtime, licence, url, summary, description = data
                dlsize = str(dlsize)
                buildtime = buildtime.strftime(DATE_FMT)
                install_time = install_time if install_time else ''
                if replace_newline:
                    description = description.replace('\n', '|')
                output.append({
                    'name': name,
                    'epoch': epoch,
                    'version': version,
                    'release': release,
                    'reponame': reponame,
                    'size': dlsize,
                    'buildtime': buildtime,
                    'installtime': install_time,
                    'license': licence,
                    'url': url,
                    'summary': summary,
                    'description': description})
            outputs[status.value] = output
        return outputs

    if command == 'list':
        append = append_list
    elif command == 'info':
        append = append_info
    else:
        assert False, 'Unknown command'

    if not (args.installed or args.available or args.extras or args.upgrades):
        args.all = True

    try:
        query_results = templates_list(
            app=app,
            repos=args.repos,
            releasever=args.releasever,
            repo_files=args.repo_files,
            updatevm=args.updatevm,
            templates=args.templates if args.templates else None,
            installed=args.installed or args.all,
            available=args.available or args.all,
            extras=args.extras,
            upgrades=args.upgrades,
            all_versions=args.all_versions,
        )
    except (qubesadmin.exc.QubesVMNotFoundError,
            qubesadmin.exc.QubesVMError) as e:
        parser.error(str(e))

    for status in TemplateState:
        if status not in query_results:
            continue
        for data, install_time in query_results[status]:
            append(data, status, install_time)

    if len(tpl_list) == 0:
        parser.error('No matching templates to list')

    if args.machine_readable:
        if command == 'info':
            tpl_list_dict = info_to_machine_output(tpl_list)
        elif command == 'list':
            tpl_list_dict = list_to_machine_output(tpl_list)
        else:
            assert False, f"Invalid command {command}"
        for status, grp in tpl_list_dict.items():
            for line in grp:
                print('|'.join([status] + list(line.values())))
    elif args.machine_readable_json:
        if command == 'info':
            tpl_list_dict = \
                info_to_machine_output(tpl_list, replace_newline=False)
        elif command == 'list':
            tpl_list_dict = list_to_machine_output(tpl_list)
        print(json.dumps(tpl_list_dict))
    else:
        if command == 'info':
            tpl_list = info_to_human_output(tpl_list)
        elif command == 'list':
            tpl_list = list_to_human_output(tpl_list)
        for status, grp in tpl_list:
            print(status.title(), flush=True)
            qubesadmin.tools.print_table(grp)


def search(args: argparse.Namespace, app: qubesadmin.app.QubesBase) -> None:
    """Command that searches template details for given patterns.

    :param args: Arguments received by the application.
    :param app: Qubes application object
    """
    # Search in both installed and available templates
    query_res = qrexec_repoquery(app, args.repos, args.releasever,
                                 args.repo_files, args.updatevm)
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

    # pylint: disable=invalid-name
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
        return -weight, needles, name

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


def remove(
        args: argparse.Namespace,
        app: qubesadmin.app.QubesBase,
        disassoc: bool = False,
        purge: bool = False,
        dummy: str = 'dummy'
) -> None:
    """Command that remove templates.

    :param args: Arguments received by the application.
    :param app: Qubes application object
    :param disassoc: Whether to disassociate VMs from the templates
    :param purge: Whether to remove VMs based on the templates
    :param dummy: Name of dummy VM if disassoc is used
    """
    # NOTE: While QubesArgumentParser provide similar functionality
    #       it does not seem to work as a parent parser
    for tpl in args.templates:
        if tpl not in app.domains:
            parser.error(f"no such domain: '{tpl}'")

    remove_list = args.templates
    if purge:
        # Not disassociating first may result in dependency ordering issues
        disassoc = True
        # Remove recursively via BFS
        remove_set = set(remove_list)  # visited
        idx = 0
        while idx < len(remove_list):
            tpl = remove_list[idx]
            idx += 1
            vm = app.domains[tpl]
            for holder, prop in qubesadmin.utils.vm_dependencies(app, vm):
                if holder is not None and holder.name not in remove_set:
                    remove_list.append(holder.name)
                    remove_set.add(holder.name)

    if not args.yes:
        repeat = 3 if purge else 1
        # XXX: Mutating the list later seems to break the tests...
        remove_list_copy = remove_list.copy()
        for confirm_n in range(repeat):
            confirm_action(
                'This will completely remove the selected VM(s){}...'.format(
                    f' (confirmation {confirm_n + 1} of {repeat})'
                    if repeat > 1 else ''),
                remove_list_copy)

    if disassoc:
        # Remove the dummy afterwards if we're purging
        # as nothing should depend on it in the end
        remove_dummy = purge
        # Create dummy template; handle name collisions
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

        for tpl in remove_list:
            vm = app.domains[tpl]
            for holder, prop in qubesadmin.utils.vm_dependencies(app, vm):
                if holder:
                    setattr(holder, prop, dummy_vm)
                    holder.template = dummy_vm
                    print(f"Property '{prop}' of '{holder.name}' set to "
                          f"'{dummy}'.", file=sys.stderr)
                else:
                    print(f"Global property '{prop}' set to ''.",
                          file=sys.stderr)
                    setattr(app, prop, '')
        if remove_dummy:
            remove_list.append(dummy)

    if disassoc or purge:
        qubesadmin.tools.qvm_kill.main(['--'] + remove_list, app)
    qubesadmin.tools.qvm_remove.main(['--force', '--'] + remove_list, app)


def repolist(args: argparse.Namespace, app: qubesadmin.app.QubesBase) -> None:
    """Command that lists configured repositories.

    :param args: Arguments received by the application.
    :param app: Qubes application object
    """
    _ = app  # unused

    # Even if python3-dnf is now available on Debian 11+, this is not
    # an "essential operation" so the module is imported here
    # instead of top-level. Any other operation still work in case where
    # a failure occurs with python3-dnf.
    try:
        import dnf.repo
        import dnf.conf
    except ModuleNotFoundError:
        print("Error: Python module 'dnf' not found.", file=sys.stderr)
        sys.exit(1)

    if not args.all and not args.disabled:
        args.enabled = True

    with tempfile.TemporaryDirectory(dir=TEMP_DIR) as reposdir:
        for idx, path in enumerate(args.repo_files):
            src = os.path.abspath(path)
            # Use index as file name in case of collisions
            dst = os.path.join(reposdir, f'{idx:d}.repo')
            os.symlink(src, dst)
        conf = dnf.conf.Conf()
        conf.substitutions['releasever'] = args.releasever
        conf.reposdir = reposdir
        base = dnf.Base(conf)
        base.read_all_repos()

        # Filter (name, operation) from args.repos
        repoid = []
        enable_disable_repos = []
        repos: typing.List[dnf.repo.Repo] = []
        if args.repos:
            for repo in args.repos:
                operation, name = repo
                if operation == "repoid":
                    repoid.append(name)
                elif operation in ("enablerepo", "disablerepo"):
                    enable_disable_repos.append(name)
            if repoid:
                if enable_disable_repos:
                    print("Warning: Ignoring --enablerepo and --disablerepo "
                          "options.", file=sys.stderr)
                base.repos.get_matching('*').disable()
                for repo in repoid:
                    dnf_repo = base.repos.get_matching(repo)
                    dnf_repo.enable()
                    repos += list(dnf_repo)
            else:
                for repo in enable_disable_repos:
                    operation, name = repo
                    if operation == "enablerepo":
                        dnf_repo = base.repos.get_matching(repo)
                        dnf_repo.enable()
                        repos += list(dnf_repo)
                    elif operation == "disablerepo":
                        dnf_repo = base.repos.get_matching(repo)
                        dnf_repo.disable()
                        repos += list(dnf_repo)
            repos = list(set(repos))
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
    # do two passes to allow global options after command name too
    p_args, args = parser.parse_known_args(args)
    p_args = parser.parse_args(args, p_args)

    if not p_args.command:
        parser.error('A command needs to be specified.')

    # If the user specified other repo files...
    if len(p_args.repo_files) > 1:
        # ...remove the default entry
        p_args.repo_files.pop(0)

    # resolve wildcards
    p_args.repo_files = list(itertools.chain(
        *(glob.glob(path) for path in p_args.repo_files)))

    if app is None:
        app = qubesadmin.Qubes()

    if p_args.updatevm is UPDATEVM:
        p_args.updatevm = app.updatevm

    try:
        if p_args.refresh:
            qrexec_repoquery(app, p_args.repos, p_args.releasever,
                             p_args.repo_files, p_args.updatevm, refresh=True)

        if p_args.command == 'download':
            download(p_args, app)
        elif p_args.command == 'install':
            install(p_args, app)
        elif p_args.command == 'reinstall':
            install(p_args, app, version_selector=VersionSelector.REINSTALL,
                    override_existing=True)
        elif p_args.command == 'downgrade':
            install(p_args, app, version_selector=VersionSelector.LATEST_LOWER,
                    override_existing=True)
        elif p_args.command == 'upgrade':
            install(p_args, app, version_selector=VersionSelector.LATEST_HIGHER,
                    override_existing=True)
        elif p_args.command == 'list':
            list_templates(p_args, app, 'list')
        elif p_args.command == 'info':
            list_templates(p_args, app, 'info')
        elif p_args.command == 'search':
            search(p_args, app)
        elif p_args.command == 'remove':
            remove(p_args, app, disassoc=p_args.disassoc)
        elif p_args.command == 'purge':
            remove(p_args, app, purge=True)
        elif p_args.command == 'clean':
            clean(p_args.cachedir)
        elif p_args.command == 'repolist':
            repolist(p_args, app)
        elif p_args.command == 'migrate-from-rpmdb':
            if os.getuid() != 0:
                parser.error('This command needs to be run as root')
            migrate_from_rpmdb(app)
        else:
            parser.error(f'Command \'{p_args.command}\' not supported.')
    except Exception as e:  # pylint: disable=broad-except
        print('ERROR: ' + str(e), file=sys.stderr)
        app.log.debug(str(e), exc_info=sys.exc_info())
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
