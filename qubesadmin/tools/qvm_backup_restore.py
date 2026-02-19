#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2016 Marek Marczykowski-Górecki
#                               <marmarek@invisiblethingslab.com>
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

'''Console frontend for backup restore code'''

import getpass
import os
import sys

from qubesadmin.backup.restore import BackupRestore
from qubesadmin.backup.dispvm import RestoreInDisposableVM
import qubesadmin.exc
import qubesadmin.tools
import qubesadmin.utils

parser = qubesadmin.tools.QubesArgumentParser()

# WARNING:
# When adding options, update/verify also
# qubeadmin.restore.dispvm.RestoreInDisposableVM.arguments
#
parser.add_argument("--verify-only", action="store_true",
    dest="verify_only", default=False,
    help="Verify backup integrity without restoring any "
         "data")

parser.add_argument("--skip-broken", action="store_true", dest="skip_broken",
    default=False,
    help="Do not restore VMs that have missing TemplateVMs "
         "or NetVMs")

parser.add_argument("--ignore-missing", action="store_true",
    dest="ignore_missing", default=False,
    help="Restore VMs even if their associated TemplateVMs "
         "and NetVMs are missing")

parser.add_argument("--skip-conflicting", action="store_true",
    dest="skip_conflicting", default=False,
    help="Do not restore VMs that are already present on "
         "the host")

parser.add_argument("--rename-conflicting", action="store_true",
    dest="rename_conflicting", default=False,
    help="Restore VMs that are already present on the host "
         "under different names")

parser.add_argument("-x", "--exclude", action="append", dest="exclude",
    default=[],
    help="Skip restore of specified VM (may be repeated)")

parser.add_argument("--skip-dom0-home", action="store_false", dest="dom0_home",
    default=True,
    help="Do not restore dom0 user home directory")

parser.add_argument("--ignore-username-mismatch", action="store_true",
    dest="ignore_username_mismatch", default=False,
    help="Ignore dom0 username mismatch when restoring home "
         "directory")

parser.add_argument("--ignore-size-limit", action="store_true",
    dest="ignore_size_limit", default=False,
    help="Ignore size limit calculated from backup metadata")

parser.add_argument("--compression-filter", "-Z", action="store",
    dest="compression",
    help="Force specific compression filter program, "
         "instead of the one from the backup header")

parser.add_argument("-d", "--dest-vm", action="store", dest="appvm",
    help="Specify VM containing the backup to be restored")

parser.add_argument("-p", "--passphrase-file", action="store",
    dest="pass_file", default=None,
    help="Read passphrase from file, or use '-' to read from stdin")

parser.add_argument('--auto-close', action="store_true",
    help="Auto-close restore window and display log on the stdout "
         "(applies to --paranoid-mode)")

parser.add_argument("--location-is-service", action="store_true",
    help="Interpret backup location as a qrexec service name,"
         "possibly with an argument separated by +.Requires -d option.")

parser.add_argument('--paranoid-mode', '--plan-b', action="store_true",
    help="Isolate restore process in a DispVM, defend against untrusted backup;"
         "implies --skip-dom0-home")

parser.add_argument('backup_location', action='store',
    help="Backup directory name, or command to pipe from")

parser.add_argument('vms', nargs='*', action='store', default=[],
    help='Restore only those VMs')


def handle_broken(app, args, restore_info):
    '''Display information about problems with VMs selected for resetore'''
    there_are_conflicting_vms = False
    there_are_missing_templates = False
    there_are_missing_netvms = False
    dom0_username_mismatch = False

    for vm_info in restore_info.values():
        assert isinstance(vm_info, BackupRestore.VMToRestore)
        if BackupRestore.VMToRestore.EXCLUDED in \
                vm_info.problems:
            continue
        if BackupRestore.VMToRestore.MISSING_TEMPLATE in \
                vm_info.problems:
            there_are_missing_templates = True
        if BackupRestore.VMToRestore.MISSING_NETVM in \
                vm_info.problems:
            there_are_missing_netvms = True
        if BackupRestore.VMToRestore.ALREADY_EXISTS in \
                vm_info.problems:
            there_are_conflicting_vms = True
        if BackupRestore.Dom0ToRestore.USERNAME_MISMATCH in \
                vm_info.problems:
            dom0_username_mismatch = True


    if there_are_conflicting_vms:
        app.log.error(
            "*** There are VMs with conflicting names on the host! ***")
        if args.skip_conflicting:
            app.log.error(
                "Those VMs will not be restored. "
                "The host VMs will NOT be overwritten.")
        else:
            raise qubesadmin.exc.QubesException(
                "Remove VMs with conflicting names from the host "
                "before proceeding.\n"
                "Or use --skip-conflicting to restore only those VMs that "
                "do not exist on the host.\n"
                "Or use --rename-conflicting to restore those VMs under "
                "modified names (with numbers at the end).")

    if args.verify_only:
        app.log.info("The above VM archive(s) will be verified.")
        app.log.info("Existing VMs will NOT be removed or altered.")
    else:
        app.log.info("The above VMs will be copied and added to your system.")
        app.log.info("Existing VMs will NOT be removed.")

    if there_are_missing_templates:
        app.log.warning("*** One or more TemplateVMs are missing on the "
                        "host! ***")
        if not (args.skip_broken or args.ignore_missing):
            raise qubesadmin.exc.QubesException(
                "Install them before proceeding with the restore."
                "Or pass: --skip-broken or --ignore-missing.")
        if args.skip_broken:
            app.log.warning("Skipping broken entries: VMs that depend on "
                            "missing TemplateVMs will NOT be restored.")
        elif args.ignore_missing:
            app.log.warning("Ignoring missing entries: VMs that depend "
                "on missing TemplateVMs will have default value "
                "assigned.")
        else:
            raise qubesadmin.exc.QubesException(
                "INTERNAL ERROR! Please report this to the Qubes OS team!")

    if there_are_missing_netvms:
        app.log.warning("*** One or more NetVMs are missing on the "
                        "host! ***")
        if not (args.skip_broken or args.ignore_missing):
            raise qubesadmin.exc.QubesException(
                "Install them before proceeding with the restore."
                "Or pass: --skip-broken or --ignore-missing.")
        if args.skip_broken:
            app.log.warning("Skipping broken entries: VMs that depend on "
                            "missing NetVMs will NOT be restored.")
        elif args.ignore_missing:
            app.log.warning("Ignoring missing entries: VMs that depend "
                "on missing NetVMs will have default value assigned.")
        else:
            raise qubesadmin.exc.QubesException(
                "INTERNAL ERROR! Please report this to the Qubes OS team!")

    if 'dom0' in restore_info.keys() and args.dom0_home \
        and not args.verify_only:
        if dom0_username_mismatch:
            app.log.warning("*** Dom0 username mismatch! This can break "
                            "some settings! ***")
            if not args.ignore_username_mismatch:
                raise qubesadmin.exc.QubesException(
                    "Skip restoring the dom0 home directory "
                    "(--skip-dom0-home), or pass "
                    "--ignore-username-mismatch to continue anyway.")
            app.log.warning("Continuing as directed.")
        app.log.warning("NOTE: The archived dom0 home directory "
            "will be restored to a new directory "
            "'home-restore-<current-time>' "
            "created inside the dom0 home directory. Restored "
            "files should be copied or moved out of the new "
            "directory before using them.")


def print_backup_log(backup_log):
    """Print a log on stdout, coloring it red if it's a terminal"""
    if os.isatty(sys.stdout.fileno()):
        sys.stdout.write('\033[0;31m')
        sys.stdout.flush()
    sys.stdout.buffer.write(backup_log)
    if os.isatty(sys.stdout.fileno()):
        sys.stdout.write('\033[0m')
        sys.stdout.flush()


def main(args=None, app=None):
    '''Main function of qvm-backup-restore'''
    # pylint: disable=too-many-return-statements
    args = parser.parse_args(args, app=app)

    appvm = None
    if args.appvm:
        try:
            appvm = args.app.domains[args.appvm]
        except KeyError:
            parser.error(f'no such domain: {args.appvm!r}')

    if args.location_is_service and not args.appvm:
        parser.error('--location-is-service option requires -d')

    if args.paranoid_mode:
        args.dom0_home = False
        restore_in_dispvm = RestoreInDisposableVM(args.app, args)
        try:
            backup_log = restore_in_dispvm.run()
            if args.auto_close:
                print_backup_log(backup_log)
        except qubesadmin.exc.BackupRestoreError as e:
            if e.backup_log is not None:
                print_backup_log(e.backup_log)
            parser.error_runtime(str(e))
            return 1
        except qubesadmin.exc.QubesException as e:
            parser.error_runtime(str(e))
            return 1
        return

    if args.pass_file is not None:
        if args.pass_file == '-':
            passphrase = sys.stdin.readline().rstrip()
        else:
            with open(args.pass_file, encoding='utf-8') as pass_f:
                passphrase = pass_f.readline().rstrip()
    else:
        passphrase = getpass.getpass("Please enter the passphrase to verify "
                                     "and (if encrypted) decrypt the backup: ")

    args.app.log.info("Checking backup content...")

    try:
        backup = BackupRestore(args.app, args.backup_location,
            appvm, passphrase, location_is_service=args.location_is_service,
            force_compression_filter=args.compression)
    except qubesadmin.exc.QubesException as e:
        parser.error_runtime(str(e))
        # unreachable - error_runtime will raise SystemExit
        return 1

    backup.options.use_default_template = args.ignore_missing
    backup.options.use_default_netvm = args.ignore_missing
    backup.options.rename_conflicting = args.rename_conflicting
    backup.options.dom0_home = args.dom0_home
    backup.options.ignore_username_mismatch = args.ignore_username_mismatch
    backup.options.ignore_size_limit = args.ignore_size_limit
    backup.options.exclude = args.exclude
    backup.options.verify_only = args.verify_only

    restore_info = None
    try:
        restore_info = backup.get_restore_info()
    except qubesadmin.exc.QubesException as e:
        parser.error_runtime(str(e))

    if args.vms:
        # use original name here, not renamed
        backup.options.exclude += [vm_info.vm.name
            for vm_info in restore_info.values()
            if vm_info.vm.name not in args.vms]
        restore_info = backup.restore_info_verify(restore_info)

    print(backup.get_restore_summary(restore_info))

    try:
        handle_broken(args.app, args, restore_info)
    except qubesadmin.exc.QubesException as e:
        parser.error_runtime(str(e))

    if args.pass_file is None:
        if input("Do you want to proceed? [y/N] ").upper() != "Y":
            sys.exit(0)

    try:
        backup.restore_do(restore_info)
    except qubesadmin.exc.QubesException as e:
        parser.error_runtime(str(e))

if __name__ == '__main__':
    main()
