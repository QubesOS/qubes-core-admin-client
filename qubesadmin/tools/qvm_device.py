# encoding=utf-8

#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2016 Bahtiar `kalkin-` Gadimov <bahtiar@gadimov.de>
# Copyright (C) 2016 Marek Marczykowski-Górecki
#                              <marmarek@invisiblethingslab.com>
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

"""Qubes volume and block device managment"""

import argparse
import os
import sys

import qubesadmin
import qubesadmin.exc
import qubesadmin.tools
import qubesadmin.devices


def prepare_table(dev_list):
    """ Converts a list of :py:class:`qubes.devices.DeviceInfo` objects to a
    list of tupples for the :py:func:`qubes.tools.print_table`.

    If :program:`qvm-devices` is running in a TTY, it will ommit duplicate
    data.

    :param iterable dev_list: List of :py:class:`qubes.devices.DeviceInfo`
        objects.
    :returns: list of tupples
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
    def __init__(self, device: qubesadmin.devices.DeviceInfo, attached_to=None):
        self.ident = "{!s}:{!s}".format(device.backend_domain, device.ident)
        self.description = device.description
        self.attached_to = attached_to if attached_to else ""
        self.frontends = []

    @property
    def assignments(self):
        """list of frontends the device is assigned to"""
        return ', '.join(self.frontends)


def list_devices(args):
    """ Called by the parser to execute the qubes-devices list
    subcommand. """
    app = args.app

    devices = set()
    if hasattr(args, 'domains') and args.domains:
        for domain in args.domains:
            for dev in domain.devices[args.devclass].attached():
                devices.add(dev)
            for dev in domain.devices[args.devclass].available():
                devices.add(dev)

    else:
        for domain in app.domains:
            for dev in domain.devices[args.devclass].available():
                devices.add(dev)

    result = {dev: Line(dev) for dev in devices}

    for dev in result:
        for domain in app.domains:
            if domain == dev.backend_domain:
                continue

            for assignment in domain.devices[args.devclass].assignments():
                if dev != assignment:
                    continue
                if assignment.options:
                    result[dev].frontends.append('{!s} ({})'.format(
                        domain, ', '.join('{}={}'.format(key, value)
                                          for key, value in
                                          assignment.options.items())))
                else:
                    result[dev].frontends.append(str(domain))

    qubesadmin.tools.print_table(prepare_table(result.values()))


def attach_device(args):
    """ Called by the parser to execute the :program:`qvm-devices attach`
        subcommand.
    """
    device_assignment = args.device_assignment
    vm = args.domains[0]
    options = dict(opt.split('=', 1) for opt in args.option or [])
    if args.ro:
        options['read-only'] = 'yes'
    device_assignment.persistent = args.persistent
    device_assignment.options = options
    vm.devices[args.devclass].attach(device_assignment)


def detach_device(args):
    """ Called by the parser to execute the :program:`qvm-devices detach`
        subcommand.
    """
    vm = args.domains[0]
    if args.device_assignment:
        vm.devices[args.devclass].detach(args.device_assignment)
    else:
        for device_assignment in vm.devices[args.devclass].assignments():
            vm.devices[args.devclass].detach(device_assignment)


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
        :py:class:``qubesadmin.device.DeviceAssignment`` from a
        BACKEND:DEVICE_ID string.
    """  # pylint: disable=too-few-public-methods

    def __init__(self, help='A backend & device id combination',
                 required=True, allow_unknown=False, **kwargs):
        # pylint: disable=redefined-builtin
        self.allow_unknown = allow_unknown
        super(DeviceAction, self).__init__(help=help, required=required,
                                           **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        """ Set ``namespace.device_assignment`` to ``values`` """
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
                        isinstance(dev, qubesadmin.devices.UnknownDevice):
                    raise KeyError(device_id)
            except KeyError:
                parser.error_runtime(
                    "backend vm {!r} doesn't expose device {!r}".format(
                        vmname, device_id))
            device_assignment = qubesadmin.devices.DeviceAssignment(
                vm, device_id)
            setattr(namespace, self.dest, device_assignment)
        except ValueError:
            parser.error(
                'expected a backend vm & device id combination like foo:bar '
                'got %s' % backend_device_id)


def get_parser(device_class=None):
    """Create :py:class:`argparse.ArgumentParser` suitable for
    :program:`qvm-block`.
    """
    parser = qubesadmin.tools.QubesArgumentParser(description=__doc__,
                                                  want_app=True)
    parser.register('action', 'parsers',
                    qubesadmin.tools.AliasedSubParsersAction)
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

    attach_parser.add_argument('VMNAME', nargs=1,
                               action=qubesadmin.tools.VmNameAction)
    detach_parser.add_argument('VMNAME', nargs=1,
                               action=qubesadmin.tools.VmNameAction)

    attach_parser.add_argument(metavar='BACKEND:DEVICE_ID',
                               dest='device_assignment',
                               action=DeviceAction)
    detach_parser.add_argument(metavar='BACKEND:DEVICE_ID',
                               dest='device_assignment',
                               nargs=argparse.OPTIONAL,
                               action=DeviceAction, allow_unknown=True)

    attach_parser.add_argument('--option', '-o', action='append',
                               help="Set option for the device in opt=value "
                                    "form (can be specified "
                                    "multiple times), see man qvm-device for "
                                    "details")
    attach_parser.add_argument('--ro', action='store_true', default=False,
                               help="Attach device read-only (alias for "
                                    "read-only=yes option, "
                                    "takes precedence)")
    attach_parser.add_argument('--persistent', '-p', action='store_true',
                               default=False,
                               help="Attach device persistently (so it will "
                                    "be automatically "
                                    "attached at qube startup)")

    attach_parser.set_defaults(func=attach_device)
    detach_parser.set_defaults(func=detach_device)

    parser.add_argument('--list-device-classes', action='store_true',
                        default=False)

    return parser


def main(args=None, app=None):
    """Main routine of :program:`qvm-block`."""
    basename = os.path.basename(sys.argv[0])
    devclass = None
    if basename.startswith('qvm-') and basename != 'qvm-device':
        devclass = basename[4:]

    args = get_parser(devclass).parse_args(args, app=app)

    if args.list_device_classes:
        print('\n'.join(qubesadmin.Qubes().list_deviceclass()))
        return 0

    try:
        args.func(args)
    except qubesadmin.exc.QubesException as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    # Special treatment for '--list-device-classes' (alias --list-classes)
    curr_action = sys.argv[1:]
    if set(curr_action).intersection(
            {'--list-device-classes', '--list-classes'}):
        sys.exit(main(args=['', '--list-device-classes']))

    sys.exit(main())
