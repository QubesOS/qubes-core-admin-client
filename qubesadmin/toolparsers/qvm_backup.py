# -*- encoding: utf8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2017 Marek Marczykowski-Górecki
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
# with this program; if not, see <http://www.gnu.org/licenses/>.

'''Parser for qvm-backup'''

import qubesadmin.toolparsers

def get_parser():
    parser = qubesadmin.toolparsers.QubesArgumentParser()

    parser.add_argument("--yes", "-y", action="store_true",
        dest="yes", default=False,
        help="Do not ask for confirmation")

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--profile', action='store',
        help='Perform backup defined by a given profile')
    no_profile = group.add_argument_group('Profile setup',
        'Manually specify profile options')
    no_profile.add_argument("--exclude", "-x", action="append",
        dest="exclude_list", default=[],
        help="Exclude the specified VM from the backup (may be "
             "repeated)")
    no_profile.add_argument("--dest-vm", "-d", action="store",
        dest="appvm", default=None,
        help="Specify the destination VM to which the backup "
             "will be sent (implies -e)")
    no_profile.add_argument("--encrypt", "-e", action="store_true",
        dest="encrypted", default=True,
        help="Ignored, backup is always encrypted")
    no_profile.add_argument("--passphrase-file", "-p", action="store",
        dest="passphrase_file", default=None,
        help="Read passphrase from a file, or use '-' to read "
             "from stdin")
    no_profile.add_argument("--compress", "-z", action="store_true",
        dest="compression", default=True,
        help="Compress the backup (default)")
    no_profile.add_argument("--no-compress", action="store_false",
        dest="compression",
        help="Do not compress the backup")
    no_profile.add_argument("--compress-filter", "-Z", action="store",
        dest="compression",
        help="Specify a non-default compression filter program "
             "(default: gzip)")
    no_profile.add_argument('--save-profile', action='store',
        help='Save profile under selected name for further use.'
             'Available only in dom0.')

    no_profile.add_argument("backup_location", action="store", default=None,
        nargs='?',
        help="Backup location (absolute directory path, "
             "or command to pipe backup to)")

    no_profile.add_argument("vms", nargs="*", action=qubesadmin.toolparsers.VmNameAction,
        help="Backup only those VMs")

    return parser
