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

'''qvm-backup tool'''

import asyncio
import functools
import getpass
import os
import signal
import sys
import yaml

try:
    import qubesadmin.events
    have_events = True
except ImportError:
    have_events = False
import qubesadmin.tools
from qubesadmin.exc import QubesException

backup_profile_dir = '/etc/qubes/backup'

parser = qubesadmin.tools.QubesArgumentParser()

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
    dest="compression", default=False,
    help="Compress the backup")
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

no_profile.add_argument("vms", nargs="*", action=qubesadmin.tools.VmNameAction,
    help="Backup only those VMs")


def write_backup_profile(output_stream, args, passphrase=None):
    '''Format backup profile and print it to *output_stream* (a file or
    stdout)

    :param output_stream: file-like object ro print the profile to
    :param args: parsed arguments
    :param passphrase: passphrase to use
    '''

    profile_data = {}
    profile_data['include'] = args.vms or None
    if args.exclude_list:
        profile_data['exclude'] = args.exclude_list
    if passphrase:
        profile_data['passphrase_text'] = passphrase
    if args.compression:
        profile_data['compression'] = args.compression
    if args.appvm:
        profile_data['destination_vm'] = args.appvm
    else:
        profile_data['destination_vm'] = 'dom0'
    profile_data['destination_path'] = args.backup_location

    yaml.safe_dump(profile_data, output_stream)


def print_progress(expected_profile, _subject, _event, backup_profile,
        progress):
    '''Event handler for reporting backup progress'''
    if backup_profile != expected_profile:
        return
    sys.stderr.write('\rMaking a backup... {:.02f}%'.format(float(progress)))

def main(args=None, app=None):
    '''Main function of qvm-backup tool'''
    args = parser.parse_args(args, app=app)
    profile_path = None
    if args.profile is None:
        if args.backup_location is None:
            parser.error('either --profile or \'backup_location\' is required')
        if args.app.qubesd_connection_type == 'socket':
            # when running in dom0, we can create backup profile, including
            # passphrase
            if args.save_profile:
                profile_name = args.save_profile
            else:
                # don't care about collisions because only the user in dom0 can
                # trigger this, and qrexec policy should not allow random VM
                # to execute the same backup in the meantime
                profile_name = 'backup-run-{}'.format(os.getpid())
            # first write the backup profile without passphrase, to display
            # summary
            profile_path = os.path.join(
                backup_profile_dir, profile_name + '.conf')
            with open(profile_path, 'w') as f_profile:
                write_backup_profile(f_profile, args)
        else:
            if args.save_profile:
                parser.error(
                    'Cannot save backup profile when running not in dom0')
                # unreachable - parser.error terminate the process
                return 1
            print('To perform the backup according to selected options, '
                'create backup profile ({}) in dom0 with following '
                  'content:'.format(
                    os.path.join(backup_profile_dir, 'profile_name.conf')))
            write_backup_profile(sys.stdout, args)
            print('# specify backup passphrase below')
            print('passphrase_text: ...')
            return 1
    else:
        profile_name = args.profile

    backup_summary = args.app.qubesd_call(
        'dom0', 'admin.backup.Info', profile_name)
    print(backup_summary.decode())

    if not args.yes:
        if input("Do you want to proceed? [y/N] ").upper() != "Y":
            if args.profile is None and not args.save_profile:
                os.unlink(profile_path)
            return 0

    if args.profile is None:
        if args.passphrase_file is not None:
            pass_f = open(args.passphrase_file) \
                if args.passphrase_file != "-" else sys.stdin
            passphrase = pass_f.readline().rstrip()
            if pass_f is not sys.stdin:
                pass_f.close()
        else:
            prompt = ("Please enter the passphrase that will be used to "
                      "encrypt and verify the backup: ")
            passphrase = getpass.getpass(prompt)

            if getpass.getpass("Enter again for verification: ") != passphrase:
                parser.error_runtime("Passphrase mismatch!")

        with open(profile_path, 'w') as f_profile:
            write_backup_profile(f_profile, args, passphrase)

    loop = asyncio.get_event_loop()
    if have_events:
        # pylint: disable=no-member
        events_dispatcher = qubesadmin.events.EventsDispatcher(args.app)
        events_dispatcher.add_handler('backup-progress',
            functools.partial(print_progress, profile_name))
        events_task = asyncio.ensure_future(
            events_dispatcher.listen_for_events())
    loop.add_signal_handler(signal.SIGINT,
        args.app.qubesd_call, 'dom0', 'admin.backup.Cancel', profile_name)
    try:
        loop.run_until_complete(loop.run_in_executor(None,
            args.app.qubesd_call, 'dom0', 'admin.backup.Execute', profile_name))
    except QubesException as err:
        print('\nBackup error: {}'.format(err), file=sys.stderr)
        return 1
    finally:
        if have_events:
            events_task.cancel()
            try:
                loop.run_until_complete(events_task)
            except asyncio.CancelledError:
                pass
        loop.close()
        if args.profile is None and not args.save_profile:
            os.unlink(profile_path)
        print('\n')
    return 0

if __name__ == '__main__':
    sys.exit(main())
