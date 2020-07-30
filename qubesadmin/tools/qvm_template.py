#!/usr/bin/env python3

import argparse
import collections
import datetime
import enum
import fnmatch
import functools
import itertools
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

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

def qubes_release():
    if os.path.exists('/usr/share/qubes/marker-vm'):
        with open('/usr/share/qubes/marker-vm', 'r') as fd:
            # Get last line (in the format `x.x`)
            return fd.readlines()[-1].strip()
    return subprocess.check_output(['lsb_release', '-sr'],
        encoding='UTF-8').strip()

parser = argparse.ArgumentParser(description='Qubes Template Manager')
parser.add_argument('operation', type=str)
parser.add_argument('templates', nargs='*')

# qrexec related
parser.add_argument('--repo-files', action='append',
    default=['/etc/yum.repos.d/qubes-templates.repo'],
    help='Specify files containing DNF repository configuration.')
parser.add_argument('--updatevm', default='sys-firewall',
    help='Specify VM to download updates from.')
# DNF-related options
parser.add_argument('--enablerepo', action='append',
    help='Enable additional repositories.')
parser.add_argument('--disablerepo', action='append',
    help='Disable certain repositories.')
parser.add_argument('--repoid', action='append',
    help='Enable just specific repositories.')
parser.add_argument('--releasever', default=qubes_release(),
    help='Override distro release version.')
parser.add_argument('--refresh', action='store_true',
    help='Set repository metadata as expired before running the command.')
parser.add_argument('--cachedir', default=CACHE_DIR,
    help='Override cache directory.')
# qvm-template install
parser.add_argument('--nogpgcheck', action='store_true',
    help='Disable signature checks.')
parser.add_argument('--allow-pv', action='store_true',
    help='Allow setting virt_mode to pv in configuration file.')
parser.add_argument('--pool',
    help='Specify pool to store created VMs in.')
# qvm-template download
parser.add_argument('--downloaddir', default='.',
    help='Override download directory.')
parser.add_argument('--retries', default=5, type=int,
    help='Override number of retries for downloads.')
# qvm-template list
parser.add_argument('--all', action='store_true')
parser.add_argument('--installed', action='store_true')
parser.add_argument('--available', action='store_true')
parser.add_argument('--extras', action='store_true')
parser.add_argument('--upgrades', action='store_true')
# qvm-template search
# Already defined above
#parser.add_argument('--all', action='store_true')

class TemplateState(enum.Enum):
    INSTALLED = 'installed'
    AVAILABLE = 'available'
    EXTRA = 'extra'
    UPGRADABLE = 'upgradable'

    def title(self):
        #pylint: disable=invalid-name
        TEMPLATE_TITLES = {
            TemplateState.INSTALLED: 'Installed Templates',
            TemplateState.AVAILABLE: 'Available Templates',
            TemplateState.EXTRA: 'Extra Templates',
            TemplateState.UPGRADABLE: 'Available Upgrades'
        }
        return TEMPLATE_TITLES[self]

class VersionSelector(enum.Enum):
    LATEST = enum.auto()
    REINSTALL = enum.auto()
    LATEST_LOWER = enum.auto()
    LATEST_HIGHER = enum.auto()

# NOTE: Verifying RPMs this way is prone to TOCTOU. This is okay for local
# files, but may create problems if multiple instances of `qvm-template` are
# downloading the same file, so a lock is needed in that case.
def verify_rpm(path, nogpgcheck=False, transaction_set=None):
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

def get_package_hdr(path, transaction_set=None):
    if transaction_set is None:
        transaction_set = rpm.TransactionSet()
    with open(path, 'rb') as fd:
        hdr = transaction_set.hdrFromFdno(fd)
        return hdr

def extract_rpm(name, path, target):
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

def parse_config(path):
    with open(path, 'r') as fd:
        return dict(line.rstrip('\n').split('=', 1) for line in fd)

def install(args, app, version_selector=VersionSelector.LATEST,
        override_existing=False):
    try:
        with open(LOCK_FILE, 'x') as _:
            pass
    except FileExistsError:
        parser.error(('%s already exists.'
            ' Perhaps another instance of qvm-template is running?')
            % LOCK_FILE)

    try:
        transaction_set = rpm.TransactionSet()

        rpm_list = []
        for template in args.templates:
            if template.endswith('.rpm'):
                if not os.path.exists(template):
                    parser.error('RPM file \'%s\' not found.' % template)
                size = os.path.getsize(template)
                rpm_list.append((template, size, '@commandline'))

        os.makedirs(args.cachedir, exist_ok=True)

        dl_list = get_dl_list(args, app, version_selector=version_selector)
        dl_list_copy = dl_list.copy()
        # Verify that the templates are not yet installed
        for name, (ver, dlsize, reponame) in dl_list.items():
            assert reponame != '@commandline'
            if not override_existing and name in app.domains:
                print(('Template \'%s\' already installed, skipping...'
                    ' (You may want to use the {reinstall,upgrade,downgrade}'
                    ' operations.)') % name, file=sys.stderr)
                del dl_list_copy[name]
            else:
                version_str = build_version_str(ver)
                target_file = \
                    '%s%s-%s.rpm' % (PACKAGE_NAME_PREFIX, name, version_str)
                rpm_list.append((os.path.join(args.cachedir, target_file),
                    dlsize, reponame))
        dl_list = dl_list_copy

        download(args, app, path_override=args.cachedir,
            dl_list=dl_list, suffix=UNVERIFIED_SUFFIX,
            version_selector=version_selector)

        for rpmfile, dlsize, reponame in rpm_list:
            if reponame != '@commandline':
                path = rpmfile + UNVERIFIED_SUFFIX
            else:
                path = rpmfile
            if not verify_rpm(path, args.nogpgcheck, transaction_set):
                parser.error('Package \'%s\' verification failed.' % rpmfile)
            if reponame != '@commandline':
                os.rename(path, rpmfile)

        for rpmfile, dlsize, reponame in rpm_list:
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
                elif override_existing:
                    if name not in app.domains:
                        parser.error(
                            "Template '%s' not already installed." % name)
                    vm = app.domains[name]
                    pkg_evr = (
                        str(package_hdr[rpm.RPMTAG_EPOCHNUM]),
                        package_hdr[rpm.RPMTAG_VERSION],
                        package_hdr[rpm.RPMTAG_RELEASE])
                    vm_evr = (
                        vm.features['template-epoch'],
                        vm.features['template-version'],
                        vm.features['template-release'])
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

def qrexec_popen(args, app, service, stdout=subprocess.PIPE, filter_esc=True):
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

def qrexec_payload(args, app, spec, refresh):
    _ = app # unused

    def check_newline(string, name):
        if '\n' in string:
            parser.error(f"Malformed {name}:" +
                " argument should not contain '\\n'.")

    payload = ''
    for repo in args.enablerepo if args.enablerepo else []:
        check_newline(repo, '--enablerepo')
        payload += '--enablerepo=%s\n' % repo
    for repo in args.disablerepo if args.disablerepo else []:
        check_newline(repo, '--disablerepo')
        payload += '--disablerepo=%s\n' % repo
    for repo in args.repoid if args.repoid else []:
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

def qrexec_repoquery(args, app, spec='*', refresh=False):
    proc = qrexec_popen(args, app, 'qubes.TemplateSearch')
    payload = qrexec_payload(args, app, spec, refresh)
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

            result.append((name, epoch, version, release, reponame, dlsize,
                buildtime, licence, url, summary, description))
        except (TypeError, ValueError):
            raise ConnectionError(("qrexec call 'qubes.TemplateSearch' failed:"
                " unexpected data format."))
    return result

def qrexec_download(args, app, spec, path, dlsize=None, refresh=False):
    with open(path, 'wb') as fd:
        # Don't filter ESCs for binary files
        proc = qrexec_popen(args, app, 'qubes.TemplateDownload',
            stdout=fd, filter_esc=False)
        payload = qrexec_payload(args, app, spec, refresh)
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
        return True

def build_version_str(evr):
    return '%s:%s-%s' % evr

def is_match_spec(name, epoch, version, release, spec):
    # Refer to "NEVRA Matching" in the DNF documentation
    # NOTE: Currently "arch" is ignored as the templates should be of "noarch"
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

def list_templates(args, app, operation):
    tpl_list = []

    def append_list(data, status, install_time=None):
        _ = install_time # unused
        #pylint: disable=unused-variable
        name, epoch, version, release, reponame, dlsize, \
            buildtime, licence, url, summary, description = data
        version_str = build_version_str((epoch, version, release))
        tpl_list.append((status, name, version_str, reponame))

    def append_info(data, status, install_time=None):
        name, epoch, version, release, reponame, dlsize, \
            buildtime, licence, url, summary, description = data
        tpl_list.append((status, 'Name', ':', name))
        tpl_list.append((status, 'Epoch', ':', epoch))
        tpl_list.append((status, 'Version', ':', version))
        tpl_list.append((status, 'Release', ':', release))
        tpl_list.append((status, 'Size', ':',
            qubesadmin.utils.size_to_human(dlsize)))
        tpl_list.append((status, 'Repository', ':', reponame))
        tpl_list.append((status, 'Buildtime', ':', str(buildtime)))
        if install_time:
            tpl_list.append((status, 'Install time', ':', str(install_time)))
        tpl_list.append((status, 'URL', ':', url))
        tpl_list.append((status, 'License', ':', licence))
        tpl_list.append((status, 'Summary', ':', summary))
        # Only show "Description" for the first line
        title = 'Description'
        for line in description.splitlines():
            tpl_list.append((status, title, ':', line))
            title = ''
        tpl_list.append((status, ' ', ' ', ' ')) # empty line

    if operation == 'list':
        append = append_list
    elif operation == 'info':
        append = append_info
    else:
        assert False and 'Unknown operation'

    def append_vm(vm, status):
        if vm.name == vm.features['template-name']:
            append((
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
                    vm.features['template-description'].replace('|', '\n')
                ),
                status,
                vm.features['template-install-time'])

    if not (args.installed or args.available or args.extras or args.upgrades):
        args.all = True

    if args.all or args.available or args.extras or args.upgrades:
        if args.templates:
            query_res = set()
            for spec in args.templates:
                query_res |= set(qrexec_repoquery(args, app, spec))
            query_res = list(query_res)
        else:
            query_res = qrexec_repoquery(args, app)

    if args.installed or args.all:
        for vm in app.domains:
            if 'template-name' in vm.features:
                if not args.templates or \
                        any(is_match_spec(
                            vm.features['template-name'],
                            vm.features['template-epoch'],
                            vm.features['template-version'],
                            vm.features['template-release'],
                            spec)[0]
                        for spec in args.templates):
                    append_vm(vm, TemplateState.INSTALLED)

    if args.available or args.all:
        for data in query_res:
            append(data, TemplateState.AVAILABLE)

    if args.extras:
        remote = set()
        #pylint: disable=unused-variable
        for name, epoch, version, release, reponame, dlsize, \
                buildtime, licence, url, summary, description in query_res:
            remote.add(name)
        for vm in app.domains:
            if 'template-name' in vm.features and \
                    vm.features['template-name'] not in remote:
                append_vm(vm, TemplateState.EXTRA)

    if args.upgrades:
        local = {}
        for vm in app.domains:
            if 'template-name' in vm.features:
                local[vm.features['template-name']] = (
                    vm.features['template-epoch'],
                    vm.features['template-version'],
                    vm.features['template-release'])
        for data in query_res:
            name, epoch, version, release, reponame, dlsize, \
                buildtime, licence, url, summary, description = data
            if name in local:
                if rpm.labelCompare(local[name], (epoch, version, release)) < 0:
                    append(data, TemplateState.UPGRADABLE)

    if len(tpl_list) == 0:
        parser.error('No matching templates to list')

    for k, grp in itertools.groupby(tpl_list, lambda x: x[0]):
        print(k.title())
        qubesadmin.tools.print_table(list(map(lambda x: x[1:], grp)))

def search(args, app):
    # Search in both installed and available templates
    query_res = qrexec_repoquery(args, app)
    for vm in app.domains:
        if 'template-name' in vm.features:
            query_res.append((
                vm.features['template-name'],
                vm.features['template-epoch'],
                vm.features['template-version'],
                vm.features['template-release'],
                vm.features['template-reponame'],
                vm.get_disk_utilization(),
                datetime.datetime.fromisoformat(
                    vm.features['template-buildtime']),
                vm.features['template-license'],
                vm.features['template-url'],
                vm.features['template-summary'],
                vm.features['template-description']))

    # Get latest version for each template
    query_res_tmp = []
    for name, grp in itertools.groupby(query_res, lambda x: x[0]):
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

    search_res = collections.defaultdict(list)
    for keyword in args.templates:
        #pylint: disable=unused-variable
        for idx, (name, epoch, version, release, reponame, dlsize, \
                buildtime, licence, url, summary, description) \
                in enumerate(query_res):
            needles = [(name, WEIGHT_NAME), (summary, WEIGHT_SUMMARY)]
            if args.all:
                needles += \
                    [(description, WEIGHT_DESCRIPTION), (url, WEIGHT_URL)]
            for key, weight in needles:
                if fnmatch.fnmatch(key, '*' + keyword + '*'):
                    exact = keyword == key
                    if exact and weight == WEIGHT_NAME:
                        weight = WEIGHT_NAME_EXACT
                    search_res[idx].append((weight, keyword, exact))

    # Requires changes to the qrexec call qubes.TemplateSearch
    if not args.all:
        keywords = set(args.templates)
        idxs = list(search_res.keys())
        for idx in idxs:
            if keywords != set(x[1] for x in search_res[idx]):
                del search_res[idx]

    def key_func(x):
        # ORDER BY weight DESC, list_of_needles ASC, name ASC
        idx, needles = x
        weight = sum(t[0] for t in needles)
        name = query_res[idx][0]
        return (-weight, needles, name)

    search_res = sorted(search_res.items(), key=key_func)

    def gen_header(idx, needles):
        #pylint: disable=unused-variable
        name, epoch, version, release, reponame, dlsize, \
            buildtime, licence, url, summary, description = query_res[idx]
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
        cur_header = gen_header(idx, needles)
        if last_header != cur_header:
            last_header = cur_header
            # XXX: The style is different from that of DNF
            print('===', cur_header, '===')
        name, epoch, version, release, reponame, dlsize, \
            buildtime, licence, url, summary, description = query_res[idx]
        print(name, ':', summary)

def get_dl_list(args, app, version_selector=VersionSelector.LATEST):
    full_candid = {}
    for template in args.templates:
        # This will be merged into `full_candid` later.
        # It is separated so that we can check whether it is empty.
        candid = {}

        # Skip local RPMs
        if template.endswith('.rpm'):
            continue

        query_res = qrexec_repoquery(args, app, PACKAGE_NAME_PREFIX + template)

        # We only select one package for each distinct package name
        #pylint: disable=unused-variable
        for name, epoch, version, release, reponame, dlsize, \
                buildtime, licence, url, summary, description in query_res:
            ver = (epoch, version, release)
            if version_selector == VersionSelector.LATEST:
                if name not in candid \
                        or rpm.labelCompare(candid[name][0], ver) < 0:
                    candid[name] = (ver, dlsize, reponame)
            elif version_selector == VersionSelector.REINSTALL:
                if name not in app.domains:
                    parser.error("Template '%s' not already installed." % name)
                vm = app.domains[name]
                cur_ver = (
                    vm.features['template-epoch'],
                    vm.features['template-version'],
                    vm.features['template-release'])
                if rpm.labelCompare(ver, cur_ver) == 0:
                    candid[name] = (ver, dlsize, reponame)
            elif version_selector in [VersionSelector.LATEST_LOWER,
                    VersionSelector.LATEST_HIGHER]:
                if name not in app.domains:
                    parser.error("Template '%s' not already installed." % name)
                vm = app.domains[name]
                cur_ver = (
                    vm.features['template-epoch'],
                    vm.features['template-version'],
                    vm.features['template-release'])
                cmp_res = -1 \
                        if version_selector == VersionSelector.LATEST_LOWER \
                        else 1
                if rpm.labelCompare(ver, cur_ver) == cmp_res:
                    if name not in candid \
                            or rpm.labelCompare(candid[name][0], ver) < 0:
                        candid[name] = (ver, dlsize, reponame)

        # XXX: As it's possible to include version information in `template`
        # Perhaps the messages can be improved
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
        for name, (ver, dlsize, reponame) in candid.items():
            if name not in full_candid \
                    or rpm.labelCompare(full_candid[name][0], ver) < 0:
                full_candid[name] = (ver, dlsize, reponame)

    return candid

def download(args, app, path_override=None,
        dl_list=None, suffix='', version_selector=VersionSelector.LATEST):
    if dl_list is None:
        dl_list = get_dl_list(args, app, version_selector=version_selector)

    path = path_override if path_override is not None else args.downloaddir
    for name, (ver, dlsize, reponame) in dl_list.items():
        _ = reponame # unused
        version_str = build_version_str(ver)
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
                    qrexec_download(args, app, spec, target_suffix, dlsize)
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
                print('\'%s\' download failed.' % spec, file=sys.stderr)
                sys.exit(1)

def remove(args, app):
    _ = args, app # unused

    # Remove 'remove' entry from the args...
    operation_idx = sys.argv.index('remove')
    argv = sys.argv[1:operation_idx] + sys.argv[operation_idx+1:]

    # ...then pass the args to qvm-remove
    # Use exec so stdio can be shared easily
    os.execvp('qvm-remove', ['qvm-remove'] + argv)

def clean(args, app):
    # TODO: More fine-grained options
    _ = app # unused

    shutil.rmtree(args.cachedir)

def main(args=None, app=None):
    args, _ = parser.parse_known_args(args)

    if app is None:
        app = qubesadmin.Qubes()

    if args.refresh:
        qrexec_repoquery(args, app, refresh=True)

    if args.operation == 'install':
        install(args, app)
    elif args.operation == 'reinstall':
        install(args, app, version_selector=VersionSelector.REINSTALL,
            override_existing=True)
    elif args.operation == 'downgrade':
        install(args, app, version_selector=VersionSelector.LATEST_LOWER,
            override_existing=True)
    elif args.operation == 'upgrade':
        install(args, app, version_selector=VersionSelector.LATEST_HIGHER,
            override_existing=True)
    elif args.operation == 'list':
        list_templates(args, app, 'list')
    elif args.operation == 'info':
        list_templates(args, app, 'info')
    elif args.operation == 'search':
        search(args, app)
    elif args.operation == 'download':
        download(args, app)
    elif args.operation == 'remove':
        remove(args, app)
    elif args.operation == 'clean':
        clean(args, app)
    else:
        parser.error('Operation \'%s\' not supported.' % args.operation)

    return 0

if __name__ == '__main__':
    sys.exit(main())
