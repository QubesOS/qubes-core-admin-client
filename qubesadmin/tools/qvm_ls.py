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
import collections.abc
import sys
import textwrap

import qubesadmin
import qubesadmin.spinner
import qubesadmin.tools
import qubesadmin.utils
import qubesadmin.vm
import qubesadmin.exc

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
        self.__doc__ = doc

        # intentionally not always do set self._attr,
        # to cause AttributeError in self.format()
        if attr is not None:
            self._attr = attr

        self.__class__.columns[self.ls_head] = self


    def cell(self, vm, insertion=0):
        '''Format one cell.

        .. note::

            This is only for technical formatting (filling with space). If you
            want to subclass the :py:class:`Column` class, you should override
            :py:meth:`Column.format` method instead.

        :param qubes.vm.qubesvm.QubesVM: Domain to get a value from.
        :param int insertion: Intending to shift the value to the right.
        :returns: string to display
        :rtype: str
        '''

        value = self.format(vm) or '-'
        if insertion > 0 and self.ls_head == 'NAME':
            value = '└─' + value
            value = '  ' * (insertion-1) + value
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
                    if hasattr(ret, '__iter__') and not isinstance(ret, str):
                        ret = ','.join(map(str, ret))
            elif isinstance(self._attr, collections.abc.Callable):
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
        super().__init__(head=ls_head, attr=name)

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


class FlagsColumn(Column):
    '''Some fancy flags that describe general status of the domain.'''

    def __init__(self):
        super().__init__(head='FLAGS', doc=self.__class__.__doc__)


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

        type_codes = {
            'AdminVM': '0',
            'TemplateVM': 't',
            'AppVM': 'a',
            'StandaloneVM': 's',
            'DispVM': 'd',
        }
        ret = type_codes.get(vm.klass, None)
        if ret == '0':
            return ret

        if ret is not None:
            if getattr(vm, 'virt_mode', 'pv') == 'hvm':
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
        if state in ('running', 'transient', 'paused', 'suspended',
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
    return '{}%'.format(usage * 100 // size)


# todo maxmem

Column('STATE',
    attr=(lambda vm: vm.get_power_state()),
    doc='Current power state.')

Column('CLASS',
    attr=(lambda vm: vm.klass),
    doc='Class of the qube.')


Column('GATEWAY',
    attr='netvm.gateway',
    doc='Network gateway.')

Column('MEMORY',
    attr=(lambda vm: vm.get_mem() // 1024 if vm.is_running() else None),
    doc='Memory currently used by VM')

Column('DISK',
    attr=(lambda vm: vm.get_disk_utilization() // 1024 // 1024),
    doc='Total disk utilisation.')


Column('PRIV-CURR',
    attr=(lambda vm: calc_usage(vm, 'private')),
    doc='Disk utilisation by private image (/home, /usr/local).')

Column('PRIV-MAX',
    attr=(lambda vm: calc_size(vm, 'private')),
    doc='Maximum available space for private image.')

Column('PRIV-POOL',
    attr=(lambda vm: vm.volumes['private'].pool
          if 'private' in vm.volumes.keys() else '-'),
    doc='Storage pool of private volume.')

Column('PRIV-USED',
    attr=(lambda vm: calc_used(vm, 'private')),
    doc='Disk utilisation by private image as a percentage of available space.')


Column('ROOT-CURR',
    attr=(lambda vm: calc_usage(vm, 'root')),
    doc='Disk utilisation by root image (/usr, /lib, /etc, ...).')

Column('ROOT-MAX',
    attr=(lambda vm: calc_size(vm, 'root')),
    doc='Maximum available space for root image.')

Column('ROOT-POOL',
    attr=(lambda vm: vm.volumes['root'].pool
          if 'root' in vm.volumes.keys() else '-'),
    doc='Storage pool of root volume.')

Column('ROOT-USED',
    attr=(lambda vm: calc_used(vm, 'root')),
    doc='Disk utilisation by root image as a percentage of available space.')


FlagsColumn()

# Sorting columns based on numeric or string (default) values
SORT_NUMERIC = ['MEMORY', 'DISK', 'PRIV-CURR', 'PRIV-MAX', 'ROOT-CURR', 'XID', \
                'ROOT-MAX', 'MAXMEM', 'QREXEC-TIMEOUT', 'SHUTDOWN-TIMEOUT', \
                'VCPUS', 'PRIV-USED', 'ROOT-USED']

class Table(object):
    '''Table that is displayed to the user.

    :param domains: Domains to include in the table.
    :param list colnames: Names of the columns (need not to be uppercase).
    '''
    def __init__(self, domains, colnames, spinner, *, raw_data=False,
                tree_sorted=False, sort_order='NAME', reverse_sort=False,
                ignore_case=False):
        self.domains = domains
        self.columns = tuple(Column.columns[col.upper().replace('_', '-')]
                for col in colnames)
        self.spinner = spinner
        self.raw_data = raw_data
        self.tree_sorted = tree_sorted
        self.sort_order = sort_order
        self.reverse_sort = reverse_sort
        self.ignore_case = ignore_case

    def get_head(self):
        '''Get table head data (all column heads).'''
        return [col.ls_head for col in self.columns]

    def get_row(self, vm, insertion=0):
        '''Get single table row data (all columns for one domain).'''
        ret = []
        for col in self.columns:
            if self.tree_sorted and col.ls_head == 'NAME':
                ret.append(col.cell(vm, insertion))
            else:
                ret.append(col.cell(vm))
            self.spinner.update()
        return ret

    def tree_append_child(self, parent, level):
        '''Concatenate the network children of the vm to a list.

        :param qubes.vm.qubesvm.QubesVM: Parent vm of the children VMs
        '''
        childs = []
        for child in parent.connected_vms:
            if child.provides_network and child in self.domains:
                childs.append((level, child))
                childs += self.tree_append_child(child, level+1)
            elif child in self.domains:
                childs.append((level, child))
        return childs

    def sort_to_tree(self, domains):
        '''Sort the domains as a network tree. It returns a list of sets. Each
        tuple stores the insertion of the cell name and the vm object.

        :param list() domains: The domains which will be sorted
        :return list(tuple()) tree: returns a list of tuple(insertion, vm)
        '''
        tree = []
        # We need a copy of domains, because domains.remove() is not allowed
        # while iterating over it. Besides, the domains should be sorted anyway.
        sorted_doms = sorted(domains)
        for dom in sorted_doms:
            try:
                if dom.netvm is None and not dom.provides_network:
                    tree.append((0, dom))
                    domains.remove(dom)
            # dom0 and eventually others have no netvm attribute
            except (qubesadmin.exc.QubesNoSuchPropertyError, AttributeError):
                tree.append((0, dom))
                domains.remove(dom)

        for dom in sorted(domains):
            if dom.netvm is None and dom.provides_network:
                tree.append((0, dom))
                domains.remove(dom)
                tree += self.tree_append_child(dom, 1)

        return tree

    def write_table(self, stream=sys.stdout):
        '''Sort & write whole table to file-like object.

        :param file stream: Stream to write the table to.
        '''

        def sort_string(field: str) -> str:
            return field.upper() if self.ignore_case else field

        def sort_numeric(field: str) -> int:
            try:
                return int(field[:-1] if field.endswith('%') else field)
            except ValueError:
                return 0

        table_data = []
        if not self.raw_data:
            self.spinner.show('please wait...')
            table_data.append(self.get_head())
            self.spinner.update()
            if self.tree_sorted:
                #FIXME: handle qubesadmin.exc.QubesVMNotFoundError
                #       (see QubesOS/qubes-issues#5105)
                insertion_vm_list = self.sort_to_tree(self.domains)
                for insertion, vm in insertion_vm_list:
                    table_data.append(self.get_row(vm, insertion))
            else:
                for vm in sorted(self.domains):
                    try:
                        table_data.append(self.get_row(vm))
                    except qubesadmin.exc.QubesVMNotFoundError:
                        continue

                if self.sort_order in SORT_NUMERIC:
                    sort_key = sort_numeric
                else:
                    sort_key = sort_string

                titles = self.get_head()
                if self.sort_order in titles:
                    # Sorting is currently possible if key is in actual output
                    col_index = titles.index(self.sort_order)
                    table_data[1:] = sorted(table_data[1:], key=lambda \
                            row: sort_key(row[col_index]),
                            reverse=self.reverse_sort)
            self.spinner.hide()
            qubesadmin.tools.print_table(table_data, stream=stream)
        else:
            for vm in sorted(self.domains):
                try:
                    stream.write('|'.join(self.get_row(vm)) + '\n')
                except qubesadmin.exc.QubesVMNotFoundError:
                    continue


#: Available formats. Feel free to plug your own one.
formats = {
    'simple': ('name', 'state', 'class', 'label', 'template', 'netvm'),
    'network': ('name', 'state', 'netvm', 'ip', 'ipback', 'gateway'),
    'kernel': ('name', 'state', 'class', 'template', 'kernel', 'kernelopts'),
    'full': ('name', 'state', 'class', 'label', 'qid', 'xid', 'uuid'),
#   'perf': ('name', 'state', 'cpu', 'memory'),
    'prefs': ('name', 'label', 'template', 'netvm',
        'vcpus', 'initialmem', 'maxmem', 'virt_mode'),
    'disk': ('name', 'state', 'disk',
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
        super().__init__(
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
        print(text + '\n')
        sys.exit(0)


class _HelpFormatsAction(argparse.Action):
    '''Action for argument parser that displays all formats and exits.'''
    # pylint: disable=redefined-builtin
    def __init__(self,
            option_strings,
            dest=argparse.SUPPRESS,
            default=argparse.SUPPRESS,
            help='list all available formats with their definitions and exit'):
        super().__init__(
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
        print(text)
        sys.exit(0)



# common VM power states for easy command-line filtering
DOMAIN_POWER_STATES = ['running', 'paused', 'halted']


def matches_power_states(domain, **states):
    '''Filter domains by their power state'''
    # if all values are False (default) => return match on every VM
    if not states or set(states.values()) == {False}:
        return True

    # otherwise => only VMs matching True states
    requested_states = [state for state, active in states.items() if active]
    return domain.get_power_state().lower() in requested_states


def get_parser():
    '''Create :py:class:`argparse.ArgumentParser` suitable for
    :program:`qvm-ls`.
    '''
    # parser creation is delayed to get all the columns that are scattered
    # thorough the modules

    wrapper = textwrap.TextWrapper(width=80, break_on_hyphens=False,
        initial_indent='  ', subsequent_indent='  ')

    parser = qubesadmin.tools.QubesArgumentParser(
        vmname_nargs=argparse.ZERO_OR_MORE,
        formatter_class=argparse.RawTextHelpFormatter,
        description='List Qubes domains and their parameters.',
        epilog='available formats (see --help-formats):\n{}\n\n'
               'available columns (see --help-columns):\n{}'.format(
                wrapper.fill(', '.join(sorted(formats.keys()))),
                wrapper.fill(', '.join(sorted(sorted(Column.columns.keys()))))))

    parser_format = parser.add_argument_group(title='formatting options')
    parser_format_exclusive = parser_format.add_mutually_exclusive_group()

    parser_format_exclusive.add_argument('--format', '-o', metavar='FORMAT',
        action='store', choices=formats.keys(), default='simple',
        help='preset format')

    parser_format_exclusive.add_argument('--fields', '-O', metavar='FIELD,...',
        action='store',
        help='user specified format (see available columns below)')

    parser_format.add_argument('--tree', '-t',
        action='store_const', const='tree',
        help='sort domain list as network tree')

    parser_format.add_argument('--raw-data', action='store_true',
        help='Display specify data of specified VMs. Intended for '
             'bash-parsing.')

    # shortcuts, compatibility with Qubes 3.2
    parser_format.add_argument('--raw-list', action='store_true',
        help='Same as --raw-data --fields=name')

    parser_format_exclusive.add_argument('--disk', '-d',
        action='store_const', dest='format', const='disk',
        help='Same as --format=disk')

    parser_format_exclusive.add_argument('--network', '-n',
        action='store_const', dest='format', const='network',
        help='Same as --format=network')

    parser_format_exclusive.add_argument('--kernel', '-k',
        action='store_const', dest='format', const='kernel',
        help='Same as --format=kernel')

    parser_format.add_argument('--help-formats', action=_HelpFormatsAction)
    parser_format.add_argument('--help-columns', action=_HelpColumnsAction)

    parser_filter = parser.add_argument_group(title='filtering options')

    parser_filter.add_argument('--class', nargs='+', metavar='CLASS',
        dest='klass', action='store',
        help='show only qubes of specific class(es)')

    parser_filter.add_argument('--label', nargs='+', metavar='LABEL',
        action='store',
        help='show only qubes with specific label(s)')

    parser_filter.add_argument('--tags', nargs='+', metavar='TAG',
        help='show only qubes having specific tag(s)')

    parser_filter.add_argument('--exclude-tags', nargs='+', metavar='TAG',
        help='exclude qubes having specific tag(s)')

    for pwstate in DOMAIN_POWER_STATES:
        parser_filter.add_argument('--{}'.format(pwstate), action='store_true',
        help='show {} VMs'.format(pwstate))

    parser_filter.add_argument('--template-source', nargs='+',
        metavar='TEMPLATE', action='store',
        help='filter results to the qubes based on the TEMPLATE. '
             '"" means None')

    parser_filter.add_argument('--netvm-is', nargs='+',
        metavar='NETVM', action='store',
        help='filter results to the qubes connecting via NETVM')

    parser_filter.add_argument('--internal', metavar='<y|n>',
        default='both', action='store', choices=['y', 'yes', 'n', 'no'],
        help='show only internal qubes or option to hide them')

    parser_filter.add_argument('--servicevm', metavar='<y|n>',
        default='both', action='store', choices=['y', 'yes', 'n', 'no'],
        help='show only ServiceVMs or option to hide them')

    parser_filter.add_argument('--pending-update', action='store_true',
        help='filter results to qubes pending for update')

    parser_filter.add_argument('--features', nargs='+', metavar='FEATURE=VALUE',
        action='store',
        help='filter results to qubes that matches all specified features. '
            'omitted VALUE means None (unset). Empty value means "" (blank)')

    parser_filter.add_argument('--prefs', nargs='+', metavar='PREFERENCE=VALUE',
        action='store',
        help='filter results to qubes that matches all specified preferences. '
            'omitted VALUE means None (unset). Empty value means "" (blank)')

    parser_sort = parser.add_argument_group(title='sorting options')

    parser_sort.add_argument('--sort', metavar='COLUMN', action='store',
        default='NAME', help='sort based on provided column rather than NAME')

    parser_sort.add_argument('--reverse', action='store_true', default=False,
        help='reverse sort')

    parser_sort.add_argument('--ignore-case', action='store_true',
        default=False, help='ignore case distinctions when sorting')

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

    # fetch all the properties with one Admin API call, instead of issuing
    # one call per property
    args.app.cache_enabled = True

    if args.raw_list:
        args.raw_data = True
        args.fields = 'name'

    if args.fields:
        columns = [col.strip() for col in args.fields.split(',')]
    else:
        columns = formats[args.format]

    # assume unknown columns are VM properties
    for col in columns:
        if col.upper() not in Column.columns:
            PropertyColumn(col.lower())

    if args.spinner and not args.raw_data:
        # we need Enterprise Edition™, since it's the only one that detects TTY
        # and uses dots if we are redirected somewhere else
        spinner = qubesadmin.spinner.QubesSpinnerEnterpriseEdition(sys.stderr)
    else:
        spinner = qubesadmin.spinner.DummySpinner(sys.stderr)

    if args.domains:
        domains = args.domains
    else:
        domains = args.app.domains

    if args.all_domains:
        # Normally, --all means "all domains except for AdminVM".
        # However, in the case of qvm-ls it does not make sense to exclude
        # AdminVMs, so we override the list from parser.
        domains = [
            vm for vm in args.app.domains if vm.name not in args.exclude
        ]

    if args.klass:
        # filter only qubes to specific class(es)
        domains = [d for d in domains if d.klass in args.klass]

    if args.label:
        # filter only qubes with specific label(s)
        domains_labeled = []
        spinner.show('Filtering based on labels...')
        for dom in domains:
            if dom.label.name in args.label:
                domains_labeled.append(dom)
            spinner.update()
        domains = domains_labeled
        spinner.hide()

    if args.tags:
        # filter only qubes having at least one of the specified tags
        domains = [dom for dom in domains
                   if set(dom.tags).intersection(set(args.tags))]

    if args.exclude_tags:
        # exclude qubes having at least one of the specified tags
        domains = [dom for dom in domains
                   if not set(dom.tags).intersection(set(args.exclude_tags))]

    if args.template_source:
        # Filter only qubes based on specific TemplateVM
        domains_template = []
        spinner.show('Filtering results to qubes based on their templates...')
        for dom in domains:
            if getattr(dom, 'template', '') in args.template_source:
                domains_template.append(dom)
            spinner.update()
        domains = domains_template
        spinner.hide()

    if args.netvm_is:
        # Filter only qubes connecting with specific netvm
        domains_netvm = []
        spinner.show('Filtering results to qubes based on their netvm...')
        for dom in domains:
            if getattr(dom, 'netvm', '') in args.netvm_is:
                domains_netvm.append(dom)
            spinner.update()
        domains = domains_netvm
        spinner.hide()

    if args.internal in ['y', 'yes']:
        domains = [d for d in domains if d.features.get('internal', None)
                   in ['1', 'true', 'True']]
    elif args.internal in ['n', 'no']:
        domains = [d for d in domains if not d.features.get('internal', None)
                   in ['1', 'true', 'True']]

    if args.servicevm in ['y', 'yes']:
        domains = [d for d in domains if d.features.get('servicevm', None)
                   in ['1', 'true', 'True']]
    elif args.servicevm in ['n', 'no']:
        domains = [d for d in domains if not d.features.get('servicevm', None)
                   in ['1', 'true', 'True']]

    if args.pending_update:
        domains = [d for d in domains if
                   d.features.get('updates-available', None)]

    if args.features:
        # Filter only qubes with specified features
        for feature in args.features:
            try:
                key, value = feature.split('=', 1)
            except ValueError:
                parser.error("Invalid argument: --features {}".format(feature))
            if not key:
                parser.error("Invalid argument: --features {}".format(feature))
            if value == '':
                value = None
            elif value in ['\'\'', '""']:
                value = ''
            domains = [d for d in domains if d.features.get(key, None) == value]

    if args.prefs:
        # Filter only qubes with specified preferences
        for pref in args.prefs:
            try:
                key, value = pref.split('=', 1)
            except ValueError:
                parser.error("Invalid argument: --prefs {}".format(pref))
            if not key:
                parser.error("Invalid argument: --prefs {}".format(pref))
            if value == '':
                value = None
            elif value in ['\'\'', '""']:
                value = ''
            domains = [d for d in domains
                       if str(getattr(d, key, None)) == value]

    pwrstates = {state: getattr(args, state) for state in DOMAIN_POWER_STATES}
    domains = [d for d in domains
               if matches_power_states(d, **pwrstates)]

    table = Table(domains=domains, colnames=columns, spinner=spinner,
        raw_data=args.raw_data, tree_sorted=args.tree,
        sort_order=args.sort.upper(), reverse_sort=args.reverse,
        ignore_case=args.ignore_case)
    table.write_table(sys.stdout)

    return 0


if __name__ == '__main__':
    sys.exit(main())
