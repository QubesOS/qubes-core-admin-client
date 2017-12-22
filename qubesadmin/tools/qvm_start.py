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

'''qvm-start - start a domain'''
import argparse
import sys

import subprocess

import time

import qubesadmin.devices
import qubesadmin.exc
import qubesadmin.tools

class DriveAction(argparse.Action):
    '''Action for argument parser that stores drive image path.'''

    # pylint: disable=redefined-builtin,too-few-public-methods
    def __init__(self,
            option_strings,
            dest='drive',
            prefix='cdrom:',
            metavar='IMAGE',
            required=False,
            help='Attach drive'):
        super(DriveAction, self).__init__(option_strings, dest,
            metavar=metavar, help=help)
        self.prefix = prefix

    def __call__(self, parser, namespace, values, option_string=None):
        # pylint: disable=redefined-outer-name
        setattr(namespace, self.dest, self.prefix + values)


parser = qubesadmin.tools.QubesArgumentParser(
    description='start a domain', vmname_nargs='+')

parser.add_argument('--skip-if-running',
    action='store_true', default=False,
    help='Do not fail if the qube is already runnning')

parser_drive = parser.add_mutually_exclusive_group()

parser_drive.add_argument('--drive', metavar='DRIVE',
    help='temporarily attach specified drive as CD/DVD or hard disk (can be'
        ' specified with prefix "hd:" or "cdrom:", default is cdrom)')

parser_drive.add_argument('--hddisk',
    action=DriveAction, dest='drive', prefix='hd:',
    help='temporarily attach specified drive as hard disk')

parser_drive.add_argument('--cdrom', metavar='IMAGE',
    action=DriveAction, dest='drive', prefix='cdrom:',
    help='temporarily attach specified drive as CD/DVD')

parser_drive.add_argument('--install-windows-tools',
    action='store_const', dest='drive', default=False,
    const='cdrom:dom0:/usr/lib/qubes/qubes-windows-tools.iso',
    help='temporarily attach Windows tools CDROM to the domain')


def get_drive_assignment(app, drive_str):
    ''' Prepare :py:class:`qubesadmin.devices.DeviceAssignment` object for a
    given drive.

    If running in dom0, it will also take care about creating appropriate
    loop device (if necessary). Otherwise, only existing block devices are
    supported.

    :param app: Qubes() instance
    :param drive_str: drive argument
    :return: DeviceAssignment matching *drive_str*
    '''
    devtype = 'cdrom'
    if drive_str.startswith('cdrom:'):
        devtype = 'cdrom'
        drive_str = drive_str[len('cdrom:'):]
    elif drive_str.startswith('hd:'):
        devtype = 'disk'
        drive_str = drive_str[len('hd:'):]

    backend_domain_name, ident = drive_str.split(':', 1)
    try:
        backend_domain = app.domains[backend_domain_name]
    except KeyError:
        raise qubesadmin.exc.QubesVMNotFoundError(
            'No such VM: %s', backend_domain_name)
    if ident.startswith('/'):
        # it is a path - if we're running in dom0, try to call losetup to
        # export the device, otherwise reject
        if app.qubesd_connection_type == 'qrexec':
            raise qubesadmin.exc.QubesException(
                'Existing block device identifier needed when running from '
                'outside of dom0 (see qvm-block)')
        try:
            if backend_domain.klass == 'AdminVM':
                loop_name = subprocess.check_output(
                    ['sudo', 'losetup', '-f', '--show', ident])
            else:
                loop_name, _ = backend_domain.run(
                    'losetup -f --show ' + ident, user='root')
        except subprocess.CalledProcessError:
            raise qubesadmin.exc.QubesException(
                'Failed to setup loop device for %s', ident)
        loop_name = loop_name.strip()
        assert loop_name.startswith(b'/dev/loop')
        ident = loop_name.decode().split('/')[2]
        # wait for device to appear
        # FIXME: convert this to waiting for event
        timeout = 10
        while isinstance(backend_domain.devices['block'][ident],
                qubesadmin.devices.UnknownDevice):
            if timeout == 0:
                raise qubesadmin.exc.QubesException(
                    'Timeout waiting for {}:{} device to appear'.format(
                        backend_domain.name, ident))
            timeout -= 1
            time.sleep(1)

    options = {
        'devtype': devtype,
        'read-only': devtype == 'cdrom'
    }
    assignment = qubesadmin.devices.DeviceAssignment(
        backend_domain,
        ident,
        options=options,
        persistent=True)

    return assignment


def main(args=None, app=None):
    '''Main routine of :program:`qvm-start`.

    :param list args: Optional arguments to override those delivered from \
        command line.
    '''

    args = parser.parse_args(args, app=app)

    exit_code = 0
    for domain in args.domains:
        if domain.is_running():
            if args.skip_if_running:
                continue
            exit_code = 1
            parser.print_error(
                    'domain {} is already running'.format(domain.name))
            return exit_code
        drive_assignment = None
        try:
            if args.drive:
                drive_assignment = get_drive_assignment(args.app, args.drive)
                try:
                    domain.devices['block'].attach(drive_assignment)
                except:
                    drive_assignment = None
                    raise

            domain.start()

            if drive_assignment:
                # don't reconnect this device after VM reboot
                domain.devices['block'].update_persistent(
                    drive_assignment.device, False)
        except (IOError, OSError, qubesadmin.exc.QubesException) as e:
            if drive_assignment:
                try:
                    domain.devices['block'].detach(drive_assignment)
                except qubesadmin.exc.QubesException:
                    pass
            exit_code = 1
            parser.print_error(str(e))

    return exit_code


if __name__ == '__main__':
    sys.exit(main())
