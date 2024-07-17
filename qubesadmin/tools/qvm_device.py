# encoding=utf-8

#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2016 Bahtiar `kalkin-` Gadimov <bahtiar@gadimov.de>
# Copyright (C) 2016 Marek Marczykowski-Górecki
#                              <marmarek@invisiblethingslab.com>
# Copyright (C) 2024 Piotr Bartman-Szwarc <prbartman@invisiblethingslab.com>
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

"""Qubes volume and block device management"""

import argparse
import os
import sys

import qubesadmin
import qubesadmin.exc
import qubesadmin.tools
import qubesadmin.device_protocol
from qubesadmin.device_protocol import (Port, DeviceInfo, UnknownDevice,
                                        DeviceAssignment)


def prepare_table(dev_list):
    """ Converts a list of :py:class:`qubes.devices.DeviceInfo` objects to a
    list of tuples for the :py:func:`qubes.tools.print_table`.

    If :program:`qvm-devices` is running in a TTY, it will omit duplicate
    data.

    :param iterable dev_list: List of :py:class:`qubes.devices.DeviceInfo`
        objects.
    :returns: list of tuples
    """
    output = []
    header = []
    if sys.stdout.isatty():
        header += [('BACKEND:DEVID', 'DESCRIPTION', 'USED BY')]  # NOQA

    for line in dev_list:
        output += [(
            line.ident,
            line.description,
            str(line.assignments),
        )]

    return header + sorted(output)


class Line(object):
    """Helper class to hold single device info for listing"""

    # pylint: disable=too-few-public-methods
    def __init__(self, device: DeviceInfo, attached_to=None):
        self.ident = "{!s}:{!s}".format(device.backend_domain, device.ident)
        self.description = device.description
        self.attached_to = attached_to if attached_to else ""
        self.frontends = []

    @property
    def assignments(self):
        """list of frontends the device is assigned to"""
        return ', '.join(self.frontends)


def list_devices(args):
    """
    Called by the parser to execute the qubes-devices list subcommand. """
    app = args.app

    domains = args.domains if hasattr(args, 'domains') else None
    devices = _load_devices(app, domains, args.devclass)

    result = {dev: Line(dev) for dev in devices}

    for dev in result:
        for vm in app.domains:
            frontends = _load_frontends_info(vm, dev, args.devclass)
            result[dev].frontends.extend(frontends)

    qubesadmin.tools.print_table(prepare_table(result.values()))


def _load_devices(app, domains, devclass):
    """
    Loads device exposed or connected to given domains.

    If `domains` is empty/`None` load all devices.
    """
    devices = set()
    if domains:
        ignore_errors = False
    else:
        ignore_errors = True
        domains = app.domains
    try:
        for vm in domains:
            try:
                for ass in vm.devices[devclass].get_dedicated_devices():
                    devices.add(ass.device)
                for dev in vm.devices[devclass].get_exposed_devices():
                    devices.add(dev)
            except qubesadmin.exc.QubesVMNotFoundError:
                if ignore_errors:
                    continue
                raise
    except qubesadmin.exc.QubesDaemonAccessError:
        raise qubesadmin.exc.QubesException(
            "Failed to list '%s' devices, this device type either "
            "does not exist or you do not have access to it.", devclass)
    return devices


def _load_frontends_info(vm, dev, devclass):
    """
    Returns string of vms to which a device is connected or `None`.
    """
    if vm == dev.backend_domain:
        return

    try:
        for assignment in vm.devices[devclass].get_dedicated_devices():
            if dev != assignment:
                continue
            if assignment.options:
                yield '{!s} ({})'.format(
                    vm, ', '.join('{}={}'.format(key, value)
                    for key, value in assignment.options.items()))
            else:
                yield str(vm)
    except qubesadmin.exc.QubesVMNotFoundError:
        pass


def attach_device(args):
    """ Called by the parser to execute the :program:`qvm-devices attach`
        subcommand.
    """
    vm = args.domains[0]
    device = args.device
    assignment = DeviceAssignment(
        device,
        # backward compatibility
        attach_automatically=args.required, required=args.required)
    options = dict(opt.split('=', 1) for opt in args.option or [])
    if args.ro:
        options['read-only'] = 'yes'
    parse_ro_option_as_read_only(options)
    assignment.options = options
    vm.devices[args.devclass].attach(assignment)
    # backward compatibility
    if args.required:
        vm.devices[args.devclass].assign(assignment)


def parse_ro_option_as_read_only(options):
    """
    For backward compatibility.

    Read-only option could be represented as `--ro`, `-o read-only=yes`
    or `-o ro=True` etc.
    """
    if 'ro' in options.keys():
        if options['ro'].lower() in ('1', 'true', 'yes'):
            options['read-only'] = 'yes'
            del options['ro']
        elif options['ro'].lower() in ('0', 'false', 'no'):
            options['read-only'] = 'no'
            del options['ro']
        else:
            raise ValueError(
                f"Unknown `read-only` option value: {options['ro']}")


def detach_device(args):
    """ Called by the parser to execute the :program:`qvm-devices detach`
        subcommand.
    """
    vm = args.domains[0]
    if args.device:
        device = args.device
        assignment = DeviceAssignment(device)
        vm.devices[args.devclass].detach(assignment)
    else:
        for ass in (vm.devices[args.devclass].get_attached_devices()):
            vm.devices[args.devclass].detach(ass)


def assign_device(args):
    """ Called by the parser to execute the :program:`qvm-devices assign`
        subcommand.
    """
    vm = args.domains[0]
    device = args.device
    assignment = DeviceAssignment(
        device, required=args.required, attach_automatically=True)
    options = dict(opt.split('=', 1) for opt in args.option or [])
    if args.ro:
        options['read-only'] = 'yes'
    parse_ro_option_as_read_only(options)
    options['identity'] = device.self_identity
    if args.port:
        options['identity'] = 'any'
    assignment.options = options
    vm.devices[args.devclass].assign(assignment)
    if vm.is_running() and not assignment.attached and not args.quiet:
        print("Assigned. To attach you can now restart domain or run: \n"
              f"\tqvm-{assignment.devclass} attach {vm} "
              f"{assignment.backend_domain}:{assignment.ident}")


def unassign_device(args):
    """ Called by the parser to execute the :program:`qvm-devices unassign`
        subcommand.
    """
    vm = args.domains[0]
    if args.device:
        device = args.device
        assignment = DeviceAssignment(
            device, frontend_domain=vm)
        _unassign_and_show_message(assignment, vm, args)
    else:
        for assignment in vm.devices[args.devclass].get_assigned_devices():
            _unassign_and_show_message(assignment, vm, args)


def _unassign_and_show_message(assignment, vm, args):
    """
    Helper for informing a user.
    """
    vm.devices[args.devclass].unassign(assignment)
    if assignment.attached and not args.quiet:
        print("Unassigned. To detach you can now restart domain or run: \n"
              f"\tqvm-{assignment.devclass} detach {vm} "
              f"{assignment.backend_domain}:{assignment.ident}")


def info_device(args):
    """ Called by the parser to execute the :program:`qvm-devices info`
        subcommand.
    """
    vm = args.domains[0]
    if args.device:
        device = args.device
        assignment = DeviceAssignment(device)
        print("description:", assignment.device.description)
        print("data:", assignment.device.data)
    else:
        for device_assignment in (
                vm.devices[args.devclass].get_dedicated_devices()):
            print("device_assignment:", device_assignment)
            print("description:", device_assignment.device.description)
            print("data:", device_assignment.device.data)


def init_list_parser(sub_parsers):
    """ Configures the parser for the :program:`qvm-devices list` subcommand """
    # pylint: disable=protected-access
    list_parser = sub_parsers.add_parser('list', aliases=('ls', 'l'),
                                         help='list devices')

    vm_name_group = qubesadmin.tools.VmNameGroup(
        list_parser, required=False, vm_action=qubesadmin.tools.VmNameAction,
        help='list devices assigned to specific domain(s)')
    list_parser._mutually_exclusive_groups.append(vm_name_group)
    list_parser.set_defaults(func=list_devices)


class DeviceAction(qubesadmin.tools.QubesAction):
    """ Action for argument parser that gets the
        :py:class:``qubesadmin.device.Device`` from a
        BACKEND:DEVICE_ID string.
    """  # pylint: disable=too-few-public-methods

    def __init__(self, help='A backend & device id combination',
                 required=True, allow_unknown=False, **kwargs):
        # pylint: disable=redefined-builtin
        self.allow_unknown = allow_unknown
        super().__init__(help=help, required=required, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        """ Set ``namespace.device`` to ``values`` """
        setattr(namespace, self.dest, values)

    def parse_qubes_app(self, parser, namespace):
        app = namespace.app
        backend_device_id = getattr(namespace, self.dest)
        devclass = namespace.devclass
        if backend_device_id is None:
            return

        try:
            vmname, device_id = backend_device_id.split(':', 1)
            vm = None
            try:
                vm = app.domains[vmname]
            except KeyError:
                parser.error_runtime("no backend vm {!r}".format(vmname))

            try:
                dev = vm.devices[devclass][device_id]
                if not self.allow_unknown and \
                        isinstance(dev, UnknownDevice):
                    raise KeyError(device_id)
            except KeyError:
                parser.error_runtime(
                    f"backend vm {vmname!r} doesn't expose "
                    f"{devclass} device {device_id!r}")
                dev = Port(vm, device_id, devclass)
            setattr(namespace, self.dest, dev)
        except ValueError:
            parser.error(
                'expected a backend vm & device id combination like foo:bar '
                'got %s' % backend_device_id)


def get_parser(device_class=None):
    """Create :py:class:`argparse.ArgumentParser` suitable for
    :program:`qvm-block`.
    """
    parser = qubesadmin.tools.QubesArgumentParser(description=__doc__)
    parser.register('action', 'parsers',
                    qubesadmin.tools.AliasedSubParsersAction)
    parser.allow_abbrev = False
    if device_class:
        parser.add_argument('devclass', const=device_class,
                            action='store_const',
                            help=argparse.SUPPRESS)
    else:
        parser.add_argument('devclass', metavar='DEVICE_CLASS', action='store',
                            help="Device class to manage ('pci', 'usb', etc)")

    # default action
    parser.set_defaults(func=list_devices)

    sub_parsers = parser.add_subparsers(
        title='commands',
        description="For more information see qvm-device command -h",
        dest='command')
    init_list_parser(sub_parsers)
    attach_parser = sub_parsers.add_parser(
        'attach', help="Attach device to domain", aliases=('at', 'a'))
    detach_parser = sub_parsers.add_parser(
        "detach", help="Detach device from domain", aliases=('d', 'dt'))
    assign_parser = sub_parsers.add_parser(
        'assign',
        help="Assign device to domain or edit existing assignment",
        aliases=('s',))
    unassign_parser = sub_parsers.add_parser(
        "unassign",
        help="Remove assignment of device from domain",
        aliases=('u',))
    info_parser = sub_parsers.add_parser(
        "info", help="Show info about device from domain", aliases=('i',))

    attach_parser.add_argument('VMNAME', nargs=1,
                               action=qubesadmin.tools.VmNameAction)
    detach_parser.add_argument('VMNAME', nargs=1,
                               action=qubesadmin.tools.VmNameAction)
    assign_parser.add_argument('VMNAME', nargs=1,
                               action=qubesadmin.tools.VmNameAction)
    unassign_parser.add_argument('VMNAME', nargs=1,
                                 action=qubesadmin.tools.VmNameAction)
    info_parser.add_argument('VMNAME', nargs=1,
                             action=qubesadmin.tools.VmNameAction)

    attach_parser.add_argument(metavar='BACKEND:DEVICE_ID',
                               dest='device',
                               action=DeviceAction)
    detach_parser.add_argument(metavar='BACKEND:DEVICE_ID',
                               dest='device',
                               nargs=argparse.OPTIONAL,
                               action=DeviceAction, allow_unknown=True)
    assign_parser.add_argument(metavar='BACKEND:DEVICE_ID',
                               dest='device',
                               action=DeviceAction)
    unassign_parser.add_argument(metavar='BACKEND:DEVICE_ID',
                                 dest='device',
                                 nargs=argparse.OPTIONAL,
                                 action=DeviceAction, allow_unknown=True)
    info_parser.add_argument(metavar='BACKEND:DEVICE_ID',
                             dest='device',
                             nargs=argparse.OPTIONAL,
                             action=DeviceAction, allow_unknown=True)

    option = (('--option', '-o',),
               {'action': 'append',
                'help': "Set option for the device in opt=value form "
                        "(can be specified multiple times), "
                        "see man qvm-device for details"})
    attach_parser.add_argument(*option[0], **option[1])
    assign_parser.add_argument(*option[0], **option[1])
    read_only = (('--ro',),
                 {'action': 'store_true', 'default': False,
                  'help': "Attach device read-only (alias for read-only=yes "
                          "option, takes precedence)"})
    attach_parser.add_argument(*read_only[0], **read_only[1])
    assign_parser.add_argument(*read_only[0], **read_only[1])
    attach_parser.add_argument('--persistent', '-p',
                               dest='required',
                               action='store_true',
                               default=False,
                               help="Alias to `assign --required` for backward "
                                    "compatibility")
    assign_parser.add_argument('--required', '-r',
                               dest='required',
                               action='store_true',
                               default=False,
                               help="Mark device as required so it will "
                                    "be required to the qube's startup and then"
                                    " automatically attached)")
    assign_parser.add_argument('--port',
                               action='store_true',
                               default=False,
                               help="Ignore device presented identity and "
                                    "attach any device connected to the given "
                                    "port number")
    attach_parser.set_defaults(func=attach_device)
    detach_parser.set_defaults(func=detach_device)
    assign_parser.set_defaults(func=assign_device)
    unassign_parser.set_defaults(func=unassign_device)
    info_parser.set_defaults(func=info_device)

    parser.add_argument('--list-device-classes', action='store_true',
                        default=False)

    return parser


def main(args=None, app=None):
    """Main routine of :program:`qvm-block`."""
    basename = os.path.basename(sys.argv[0])
    devclass = None
    if basename.startswith('qvm-') and basename != 'qvm-device':
        devclass = basename[4:]

    # Special treatment for '--list-device-classes' (alias --list-classes)
    sys_args = ['--' + arg for arg in args] if args else []
    curr_action = sys.argv[1:] + sys_args
    if set(curr_action).intersection(
            {'--list-device-classes', '--list-classes'}):
        print('\n'.join(app.list_deviceclass()))
        return 0

    parser = get_parser(devclass)
    args = parser.parse_args(args, app=app)

    try:
        args.func(args)
    except qubesadmin.exc.QubesException as e:
        parser.print_error(str(e))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
