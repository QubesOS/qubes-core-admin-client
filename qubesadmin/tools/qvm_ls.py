# pylint: disable=too-few-public-methods

#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2015  Joanna Rutkowska <joanna@invisiblethingslab.com>
# Copyright (C) 2015  Wojtek Porczyk <woju@invisiblethingslab.com>
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
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

'''qvm-ls - List available domains'''


from __future__ import print_function

import argparse
import collections
import sys
import textwrap

import qubesadmin
import qubesadmin.spinner
import qubesadmin.tools
import qubesadmin.utils
import qubesadmin.vm

#
# columns
#

class Column(object):
    '''A column in qvm-ls output characterised by its head and a way
    to fetch a parameter describing the domain.

    :param str head: Column head (usually uppercase).
    :param str attr: Attribute, possibly complex (containing ``.``). This may \
        also be a callable that gets as its only argument the domain.
    :param str doc: Description of column (will be visible in --help-columns).
    '''

    #: collection of all columns
    columns = {}

    def __init__(self, head, attr=None, doc=None):
        self.ls_head = head
        self.__doc__ = doc if doc is None else qubesadmin.utils.format_doc(doc)

        # intentionally not always do set self._attr,
        # to cause AttributeError in self.format()
        if attr is not None:
            self._attr = attr

        self.__class__.columns[self.ls_head] = self


    def cell(self, vm):
        '''Format one cell.

        .. note::

            This is only for technical formatting (filling with space). If you
            want to subclass the :py:class:`Column` class, you should override
            :py:meth:`Column.format` method instead.

        :param qubes.vm.qubesvm.QubesVM: Domain to get a value from.
        :returns: string to display
        :rtype: str
        '''

        value = self.format(vm) or '-'
        return value


    def format(self, vm):
        '''Format one cell value.

        Return value to put in a table cell.

        :param qubes.vm.qubesvm.QubesVM: Domain to get a value from.
        :returns: Value to put, or :py:obj:`None` if no value.
        :rtype: str or None
        '''

        ret = None
        try:
            if isinstance(self._attr, str):
                ret = vm
                for attrseg in self._attr.split('.'):
                    ret = getattr(ret, attrseg)
            elif isinstance(self._attr, collections.Callable):
                ret = self._attr(vm)

        except (AttributeError, ZeroDivisionError):
            # division by 0 may be caused by arithmetic in callable attr
            return None

        if ret is None:
            return None

        return str(ret)

    def __repr__(self):
        return '{}(head={!r})'.format(self.__class__.__name__,
            self.ls_head)


    def __eq__(self, other):
        return self.ls_head == other.ls_head


    def __lt__(self, other):
        return self.ls_head < other.ls_head


class PropertyColumn(Column):
    '''Column that displays value from property (:py:class:`property` or
    :py:class:`qubes.property`) of domain.

    :param name: Name of VM property.
    '''

    def __init__(self, name):
        ls_head = name.replace('_', '-').upper()
        super(PropertyColumn, self).__init__(
            head=ls_head,
            attr=name)

    def __repr__(self):
        return '{}(head={!r}'.format(
            self.__class__.__name__,
            self.ls_head)


def process_vm(vm):
    '''Process VM object to find all listable properties.

    :param qubesmgmt.vm.QubesVM vm: VM object.
    '''

    for prop_name in vm.property_list():
        PropertyColumn(prop_name)


def flag(field):
    '''Mark method as flag field.

    :param int field: Which field to fill (counted from 1)
    '''

    def decorator(obj):
        # pylint: disable=missing-docstring
        obj.field = field
        return obj
    return decorator


def simple_flag(field, letter, attr, doc=None):
    '''Create simple, binary flag.

    :param str attr: Attribute name to check. If result is true, flag is fired.
    :param str letter: The letter to show.
    '''

    def helper(self, vm):
        # pylint: disable=missing-docstring,unused-argument
        try:
            value = getattr(vm, attr)
        except AttributeError:
            value = False

        if value:
            return letter[0]

    helper.__doc__ = doc
    helper.field = field
    return helper


class StatusColumn(Column):
    '''Some fancy flags that describe general status of the domain.'''
    # pylint: disable=no-self-use

    def __init__(self):
        super(StatusColumn, self).__init__(
            head='STATUS',
            doc=self.__class__.__doc__)


    @flag(1)
    def type(self, vm):
        '''Type of domain.

        0   AdminVM (AKA Dom0)
        aA  AppVM
        dD  DisposableVM
        sS  StandaloneVM
        tT  TemplateVM

        When it is HVM (optimised VM), the letter is capital.
        '''

        if isinstance(vm, qubesadmin.vm.AdminVM):
            return '0'

        ret = None
        # TODO right order, depending on inheritance
        if isinstance(vm, qubesadmin.vm.TemplateVM):
            ret = 't'
        if isinstance(vm, qubesadmin.vm.AppVM):
            ret = 'a'
        if isinstance(vm, qubesadmin.vm.StandaloneVM):
            ret = 's'
        if isinstance(vm, qubesadmin.vm.DispVM):
            ret = 'd'

        if ret is not None:
            if getattr(vm, 'hvm', False):
                return ret.upper()
            return ret


    @flag(2)
    def power(self, vm):
        '''Current power state.

        r   running
        t   transient
        p   paused
        s   suspended
        h   halting
        d   dying
        c   crashed
        ?   unknown
        '''

        state = vm.get_power_state().lower()
        if state == 'unknown':
            return '?'
        elif state in ('running', 'transient', 'paused', 'suspended',
                'halting', 'dying', 'crashed'):
            return state[0]


    updateable = simple_flag(3, 'U', 'updateable',
        doc='If the domain is updateable.')

    provides_network = simple_flag(4, 'N', 'provides_network',
        doc='If the domain provides network.')

    installed_by_rpm = simple_flag(5, 'R', 'installed_by_rpm',
        doc='If the domain is installed by RPM.')

    internal = simple_flag(6, 'i', 'internal',
        doc='If the domain is internal (not normally shown, no appmenus).')

    debug = simple_flag(7, 'D', 'debug',
        doc='If the domain is being debugged.')

    autostart = simple_flag(8, 'A', 'autostart',
        doc='If the domain is marked for autostart.')

    # TODO (not sure if really):
    # include in backups
    # uses_custom_config

    def _no_flag(self, vm):
        '''Reserved for future use.'''


    @classmethod
    def get_flags(cls):
        '''Get all flags as list.

        Holes between flags are filled with :py:meth:`_no_flag`.

        :rtype: list
        '''

        flags = {}
        for mycls in cls.__mro__:
            for attr in mycls.__dict__.values():
                if not hasattr(attr, 'field'):
                    continue
                if attr.field in flags:
                    continue
                flags[attr.field] = attr

        return [(flags[i] if i in flags else cls._no_flag)
            for i in range(1, max(flags) + 1)]


    def format(self, vm):
        return ''.join((flag(self, vm) or '-') for flag in self.get_flags())


def calc_size(vm, volume_name):
    ''' Calculates the volume size in MB '''
    try:
        return vm.volumes[volume_name].size // 1024 // 1024
    except KeyError:
        return 0

def calc_usage(vm, volume_name):
    ''' Calculates the volume usage in MB '''
    try:
        return vm.volumes[volume_name].usage // 1024 // 1024
    except KeyError:
        return 0

def calc_used(vm, volume_name):
    ''' Calculates the volume usage in percent '''
    size = calc_size(vm, volume_name)
    if size == 0:
        return 0
    usage = calc_usage(vm, volume_name)
    return usage * 100 // size


# todo maxmem

Column('GATEWAY',
    attr='netvm.gateway',
    doc='Network gateway.')

Column('MEMORY',
    attr=(lambda vm: vm.get_mem() / 1024 if vm.is_running() else None),
    doc='Memory currently used by VM')

Column('DISK',
    attr=(lambda vm: vm.storage.get_disk_utilization() / 1024 / 1024),
    doc='Total disk utilisation.')


Column('PRIV-CURR',
    attr=(lambda vm: calc_usage(vm, 'private')),
    doc='Disk utilisation by private image (/home, /usr/local).')

Column('PRIV-MAX',
    attr=(lambda vm: calc_size(vm, 'private')),
    doc='Maximum available space for private image.')

Column('PRIV-USED',
    attr=(lambda vm: calc_used(vm, 'private')),
    doc='Disk utilisation by private image as a percentage of available space.')


Column('ROOT-CURR',
    attr=(lambda vm: calc_usage(vm, 'root')),
    doc='Disk utilisation by root image (/usr, /lib, /etc, ...).')

Column('ROOT-MAX',
    attr=(lambda vm: calc_size(vm, 'root')),
    doc='Maximum available space for root image.')

Column('ROOT-USED',
    attr=(lambda vm: calc_used(vm, 'root')),
    doc='Disk utilisation by root image as a percentage of available space.')


StatusColumn()


class Table(object):
    '''Table that is displayed to the user.

    :param qubes.Qubes app: Qubes application object.
    :param list colnames: Names of the columns (need not to be uppercase).
    '''
    def __init__(self, app, colnames, spinner, raw_data=False):
        self.app = app
        self.columns = tuple(Column.columns[col.upper()] for col in colnames)
        self.spinner = spinner
        self.raw_data = raw_data

    def get_head(self):
        '''Get table head data (all column heads).'''
        return [col.ls_head for col in self.columns]

    def get_row(self, vm):
        '''Get single table row data (all columns for one domain).'''
        ret = []
        for col in self.columns:
            ret.append(col.cell(vm))
            self.spinner.update()
        return ret

    def write_table(self, stream=sys.stdout):
        '''Write whole table to file-like object.

        :param file stream: Stream to write the table to.
        '''

        table_data = []
        if not self.raw_data:
            self.spinner.show('please wait...')
            table_data.append(self.get_head())
            self.spinner.update()
            for vm in sorted(self.app.domains):
                table_data.append(self.get_row(vm))
            self.spinner.hide()
            qubesadmin.tools.print_table(table_data, stream=stream)
        else:
            for vm in sorted(self.app.domains):
                stream.write('|'.join(self.get_row(vm)) + '\n')


#: Available formats. Feel free to plug your own one.
formats = {
    'simple': ('name', 'status', 'label', 'template', 'netvm'),
    'network': ('name', 'status', 'netvm', 'ip', 'ipback', 'gateway'),
    'full': ('name', 'status', 'label', 'qid', 'xid', 'uuid'),
#   'perf': ('name', 'status', 'cpu', 'memory'),
    'disk': ('name', 'status', 'disk',
        'priv-curr', 'priv-max', 'priv-used',
        'root-curr', 'root-max', 'root-used'),
}


class _HelpColumnsAction(argparse.Action):
    '''Action for argument parser that displays all columns and exits.'''
    # pylint: disable=redefined-builtin
    def __init__(self,
            option_strings,
            dest=argparse.SUPPRESS,
            default=argparse.SUPPRESS,
            help='list all available columns with short descriptions and exit'):
        super(_HelpColumnsAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        width = max(len(column.ls_head) for column in Column.columns.values())
        wrapper = textwrap.TextWrapper(width=80,
            initial_indent='  ', subsequent_indent=' ' * (width + 6))

        text = 'Available columns:\n' + '\n'.join(
            wrapper.fill('{head:{width}s}  {doc}'.format(
                head=column.ls_head,
                doc=column.__doc__ or '',
                width=width))
            for column in sorted(Column.columns.values()))
        text += '\n\nAdditionally any VM property may be used as a column, ' \
                'see qvm-prefs --help-properties for available values'
        parser.exit(message=text + '\n')


class _HelpFormatsAction(argparse.Action):
    '''Action for argument parser that displays all formats and exits.'''
    # pylint: disable=redefined-builtin
    def __init__(self,
            option_strings,
            dest=argparse.SUPPRESS,
            default=argparse.SUPPRESS,
            help='list all available formats with their definitions and exit'):
        super(_HelpFormatsAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        width = max(len(fmt) for fmt in formats)
        text = 'Available formats:\n' + ''.join(
            '  {fmt:{width}s}  {columns}\n'.format(
                fmt=fmt, columns=','.join(formats[fmt]).upper(), width=width)
            for fmt in sorted(formats))
        parser.exit(message=text)


def get_parser():
    '''Create :py:class:`argparse.ArgumentParser` suitable for
    :program:`qvm-ls`.
    '''
    # parser creation is delayed to get all the columns that are scattered
    # thorough the modules

    wrapper = textwrap.TextWrapper(width=80, break_on_hyphens=False,
        initial_indent='  ', subsequent_indent='  ')

    parser = qubesadmin.tools.QubesArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description='List Qubes domains and their parametres.',
        epilog='available formats (see --help-formats):\n{}\n\n'
               'available columns (see --help-columns):\n{}'.format(
                wrapper.fill(', '.join(sorted(formats.keys()))),
                wrapper.fill(', '.join(sorted(sorted(Column.columns.keys()))))))

    parser.add_argument('--help-columns', action=_HelpColumnsAction)
    parser.add_argument('--help-formats', action=_HelpFormatsAction)


    parser_formats = parser.add_mutually_exclusive_group()

    parser_formats.add_argument('--format', '-o', metavar='FORMAT',
        action='store', choices=formats.keys(), default='simple',
        help='preset format')

    parser_formats.add_argument('--fields', '-O', metavar='FIELD,...',
        action='store',
        help='user specified format (see available columns below)')


    parser.add_argument('--raw-data', action='store_true',
        help='Display specify data of specified VMs. Intended for '
             'bash-parsing.')

    parser.add_argument('--spinner',
        action='store_true', dest='spinner',
        help='reenable spinner')

    parser.add_argument('--no-spinner',
        action='store_false', dest='spinner',
        help='disable spinner')

    parser.set_defaults(spinner=True)

#   parser.add_argument('--conf', '-c',
#       action='store', metavar='CFGFILE',
#       help='Qubes config file')

    return parser


def main(args=None, app=None):
    '''Main routine of :program:`qvm-ls`.

    :param list args: Optional arguments to override those delivered from \
        command line.
    :param app: Operate on given app object instead of instantiating new one.
    '''

    parser = get_parser()
    try:
        args = parser.parse_args(args, app=app)
    except qubesadmin.exc.QubesException as e:
        parser.print_error(str(e))
        return 1

    if args.fields:
        columns = [col.strip() for col in args.fields.split(',')]
    else:
        columns = formats[args.format]

    # assume unknown columns are VM properties
    for col in columns:
        if col.upper() not in Column.columns:
            PropertyColumn(col)

    if args.spinner:
        # we need Enterprise Edition™, since it's the only one that detects TTY
        # and uses dots if we are redirected somewhere else
        spinner = qubesadmin.spinner.QubesSpinnerEnterpriseEdition(sys.stderr)
    else:
        spinner = qubesadmin.spinner.DummySpinner(sys.stderr)

    table = Table(args.app, columns, spinner)
    table.write_table(sys.stdout)

    return 0


if __name__ == '__main__':
    sys.exit(main())
