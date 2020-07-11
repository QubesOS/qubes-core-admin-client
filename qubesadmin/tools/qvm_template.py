#!/usr/bin/env python3

import argparse
import datetime
import enum
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time

import dnf
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

def qubes_release():
    if os.path.exists('/usr/share/qubes/marker-vm'):
        with open('/usr/share/qubes/marker-vm', 'r') as f:
            # Get last line (in the format `x.x`)
            return f.readlines()[-1].strip()
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
parser.add_argument('--cachedir', default=CACHE_DIR,
    help='Override cache directory.')
# qvm-template install
parser.add_argument('--nogpgcheck', action='store_true',
    help='Disable signature checks.')
parser.add_argument('--allow-pv', action='store_true',
    help='Allow setting virt_mode to pv in configuration file.')
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

class TemplateState(enum.Enum):
    INSTALLED = 'installed'
    AVAILABLE = 'available'
    EXTRA = 'extra'
    UPGRADABLE = 'upgradable'

# NOTE: Verifying RPMs this way is prone to TOCTOU. This is okay for local
# files, but may create problems if multiple instances of `qvm-template` are
# downloading the same file, so a lock is needed in that case.
def verify_rpm(path, nogpgcheck=False, transaction_set=None):
    if transaction_set is None:
        transaction_set = rpm.TransactionSet()
    with open(path, 'rb') as f:
        try:
            hdr = transaction_set.hdrFromFdno(f)
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
    with open(path, 'rb') as f:
        hdr = transaction_set.hdrFromFdno(f)
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
    with open(path, 'r') as f:
        return dict(line.rstrip('\n').split('=', 1) for line in f)

def install(args, app):
    # TODO: Lock, mentioned in the note above
    transaction_set = rpm.TransactionSet()

    rpm_list = []
    for template in args.templates:
        if template.endswith('.rpm'):
            if not os.path.exists(template):
                parser.error('RPM file \'%s\' not found.' % template)
            rpm_list.append(template)

    os.makedirs(args.cachedir, exist_ok=True)

    dl_list = get_dl_list(args, app)
    dl_list_copy = dl_list.copy()
    # Verify that the templates are not yet installed
    for name, (ver, _) in dl_list.items():
        if name in app.domains:
            print(('Template \'%s\' already installed, skipping...'
                ' (You may want to use the {reinstall,upgrade,downgrade}'
                ' operations.)') % name, file=sys.stderr)
            del dl_list_copy[name]
        else:
            version_str = build_version_str(ver)
            target_file = \
                '%s%s-%s.rpm' % (PACKAGE_NAME_PREFIX, name, version_str)
            rpm_list.append(os.path.join(args.cachedir, target_file))
    dl_list = dl_list_copy

    download(args, app, path_override=args.cachedir,
        dl_list=dl_list, suffix=UNVERIFIED_SUFFIX)

    for idx, rpmfile in enumerate(rpm_list):
        path = rpmfile + UNVERIFIED_SUFFIX
        if not verify_rpm(path, args.nogpgcheck, transaction_set):
            parser.error('Package \'%s\' verification failed.' % template)
        os.rename(path, rpmfile)

    for rpmfile in rpm_list:
        with tempfile.TemporaryDirectory(dir=TEMP_DIR) as target:
            package_hdr = get_package_hdr(rpmfile)
            package_name = package_hdr[rpm.RPMTAG_NAME]
            if not package_name.startswith(PACKAGE_NAME_PREFIX):
                parser.error(
                    'Illegal package name for package \'%s\'.' % rpmfile)
            # Remove prefix to get the real template name
            name = package_name[len(PACKAGE_NAME_PREFIX):]

            # Another check for already-downloaded RPMs
            if name in app.domains:
                print(('Template \'%s\' already installed, skipping...'
                    ' (You may want to use the {reinstall,upgrade,downgrade}'
                    ' operations.)') % name, file=sys.stderr)
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
            subprocess.check_call(cmdline + [
                'post-install',
                name,
                target + PATH_PREFIX + '/' + name])

            app.domains.refresh_cache(force=True)
            tpl = app.domains[name]

            tpl.features['template-epoch'] = \
                package_hdr[rpm.RPMTAG_EPOCHNUM]
            tpl.features['template-version'] = \
                package_hdr[rpm.RPMTAG_VERSION]
            tpl.features['template-release'] = \
                package_hdr[rpm.RPMTAG_RELEASE]
            tpl.features['template-install-date'] = \
                str(datetime.datetime.today())
            tpl.features['template-name'] = name
            # TODO: Store source repo

def qrexec_popen(args, app, service, stdout=subprocess.PIPE, filter_esc=True):
    if args.updatevm:
        return app.domains[args.updatevm].run_service(
            service,
            filter_esc=filter_esc,
            stdout=stdout)
    else:
        return subprocess.Popen([
                '/etc/qubes-rpc/%s' % service,
            ],
            stdin=subprocess.PIPE,
            stdout=stdout,
            stderr=subprocess.PIPE)

def qrexec_payload(args, app, spec):
    def check_newline(string, name):
        if '\n' in string:
            parser.error(f"Malformed {name}:" +
                " argument should not contain '\\n'.")

    payload = ''
    for r in args.enablerepo if args.enablerepo else []:
        check_newline(r, '--enablerepo')
        payload += '--enablerepo=%s\n' % r
    for r in args.disablerepo if args.disablerepo else []:
        check_newline(r, '--disablerepo')
        payload += '--disablerepo=%s\n' % r
    for r in args.repoid if args.repoid else []:
        check_newline(r, '--repoid')
        payload += '--repoid=%s\n' % r
    check_newline(args.releasever, '--releasever')
    payload += '--releasever=%s\n' % args.releasever
    check_newline(spec, 'template name')
    payload += spec + '\n'
    payload += '---\n'
    for fn in args.repo_files:
        with open(fn, 'r') as f:
            payload += f.read() + '\n'
    return payload

def qrexec_repoquery(args, app, spec='*'):
    proc = qrexec_popen(args, app, 'qubes.TemplateSearch')
    payload = qrexec_payload(args, app, spec)
    stdout, stderr = proc.communicate(payload.encode('UTF-8'))
    stdout = stdout.decode('ASCII')
    if proc.wait() != 0:
        raise ConnectionError("qrexec call 'qubes.TemplateSearch' failed.")
    result = []
    for line in stdout.strip().split('\n'):
        entry = line.split(':')
        if not entry[0].startswith(PACKAGE_NAME_PREFIX):
            continue
        entry[0] = entry[0][len(PACKAGE_NAME_PREFIX):]
        result.append(entry)
    return result

def qrexec_download(args, app, spec, path, dlsize=None):
    with open(path, 'wb') as f:
        # Don't filter ESCs for binary files
        proc = qrexec_popen(args, app, 'qubes.TemplateDownload',
            stdout=f, filter_esc=False)
        payload = qrexec_payload(args, app, spec)
        proc.stdin.write(payload.encode('UTF-8'))
        proc.stdin.close()
        with tqdm.tqdm(desc=spec, total=dlsize, unit_scale=True,
                unit_divisor=1000, unit='B') as pbar:
            last = 0
            while proc.poll() == None:
                cur = f.tell()
                pbar.update(cur - last)
                last = cur
                time.sleep(0.1)
        if proc.wait() != 0:
            raise ConnectionError(
                "qrexec call 'qubes.TemplateDownload' failed.")
        return True

def build_version_str(evr):
    return '%s:%s-%s' % evr

def do_list(args, app):
    # TODO: Check local template name actually matches to account for renames
    # TODO: Also display repo like `dnf list`
    tpl_list = []

    if not (args.installed or args.available or args.extras or args.upgrades):
        args.all = True

    if args.all or args.available or args.extras or args.upgrades:
        query_res = qrexec_repoquery(args, app)

    if args.installed or args.all:
        for vm in app.domains:
            if 'template-install-date' in vm.features:
                version_str = build_version_str((
                    vm.features['template-epoch'],
                    vm.features['template-version'],
                    vm.features['template-release']))
                tpl_list.append(
                    (vm.name, version_str, TemplateState.INSTALLED.value))

    if args.available or args.all:
        for name, epoch, version, release, reponame, dlsize, summary \
                in query_res:
            version_str = build_version_str((epoch, version, release))
            tpl_list.append((name, version_str, TemplateState.AVAILABLE.value))

    if args.extras:
        remote = set()
        for name, epoch, version, release, reponame, dlsize, summary \
                in query_res:
            remote.add(name)
        for vm in app.domains:
            if 'template-name' in vm.features and \
                    vm.features['template-name'] not in remote:
                version_str = build_version_str((
                    vm.features['template-epoch'],
                    vm.features['template-version'],
                    vm.features['template-release']))
                tpl_list.append(
                    (vm.name, version_str, TemplateState.EXTRA.value))

    if args.upgrades:
        local = {}
        for vm in app.domains:
            if 'template-name' in vm.features:
                local[vm.features['template-name']] = (
                    vm.features['template-epoch'],
                    vm.features['template-version'],
                    vm.features['template-release'])
        for name, epoch, version, release, reponame, dlsize, summary \
                in query_res:
            if name in local:
                if rpm.labelCompare(local[name], (epoch, version, release)) < 0:
                    version_str = build_version_str((epoch, version, release))
                    tpl_list.append(
                        (name, version_str, TemplateState.UPGRADABLE.value))

    qubesadmin.tools.print_table(tpl_list)

def get_dl_list(args, app):
    candid = {}
    for template in args.templates:
        # Skip local RPMs
        if template.endswith('.rpm'):
            continue
        query_res = qrexec_repoquery(args, app, PACKAGE_NAME_PREFIX + template)
        if len(query_res) == 0:
            parser.error('Package \'%s\' not found.' % template)
            sys.exit(1)
        # We only select one (latest) package for each distinct package name
        for name, epoch, version, release, reponame, dlsize, summary \
                in query_res:
            ver = (epoch, version, release)
            if name not in candid or rpm.labelCompare(candid[name], ver) < 0:
                candid[name] = (ver, int(dlsize))
    return candid

def download(args, app, path_override=None, dl_list=None, suffix=''):
    if dl_list is None:
        dl_list = get_dl_list(args, app)

    path = path_override if path_override != None else args.downloaddir
    for name, (ver, dlsize) in dl_list.items():
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
            ok = False
            for attempt in range(args.retries):
                try:
                    qrexec_download(args, app, spec, target_suffix, dlsize)
                    ok = True
                    break
                except ConnectionError:
                    if attempt + 1 < args.retries:
                        print('\'%s\' download failed, retrying...' % spec,
                            file=sys.stderr)
            if not ok:
                print('\'%s\' download failed.' % spec, file=sys.stderr)
                os.remove(target_suffix)
                sys.exit(1)

def remove(args, app):
    # Use exec so stdio can be shared easily
    os.execvp('qvm-remove', ['qvm-remove'] + args.templates)

def clean(args, app):
    # TODO: More fine-grained options
    shutil.rmtree(args.cachedir)

def main(args=None, app=None):
    args = parser.parse_args(args)

    if app is None:
        app = qubesadmin.Qubes()

    if args.operation == 'install':
       install(args, app) 
    elif args.operation == 'list':
       do_list(args, app)
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
