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

'''Parser for qvm-backup-restore'''

import qubesadmin.toolparsers


def get_parser():
    '''Return argument parser for qvm-backup-restore'''
    parser = qubesadmin.toolparsers.QubesArgumentParser()

    parser.add_argument("--verify-only", action="store_true",
        dest="verify_only", default=False,
        help="Verify backup integrity without restoring any "
             "data")

    parser.add_argument("--skip-broken", action="store_true",
        dest="skip_broken", default=False,
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

    parser.add_argument("--skip-dom0-home", action="store_false",
        dest="dom0_home", default=True,
        help="Do not restore dom0 user home directory")

    parser.add_argument("--ignore-username-mismatch", action="store_true",
        dest="ignore_username_mismatch", default=False,
        help="Ignore dom0 username mismatch when restoring home "
             "directory")

    parser.add_argument("--ignore-size-limit", action="store_true",
        dest="ignore_size_limit", default=False,
        help="Ignore size limit calculated from backup metadata")

    parser.add_argument("-d", "--dest-vm", action="store", dest="appvm",
        help="Specify VM containing the backup to be restored")

    parser.add_argument("-p", "--passphrase-file", action="store",
        dest="pass_file", default=None,
        help="Read passphrase from file, or use '-' to read from stdin")

    parser.add_argument('backup_location', action='store',
        help="Backup directory name, or command to pipe from")

    parser.add_argument('vms', nargs='*', action='store', default=[],
        help='Restore only those VMs')

    return parser
