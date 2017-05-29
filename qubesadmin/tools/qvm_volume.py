# encoding=utf-8
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2016 Bahtiar `kalkin-` Gadimov <bahtiar@gadimov.de>
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


'''Qubes volume management'''

from __future__ import print_function

import sys

import qubesadmin
import qubesadmin.exc
import qubesadmin.tools
import qubesadmin.utils


def prepare_table(vd_list, full=False):
    ''' Converts a list of :py:class:`VolumeData` objects to a list of tupples
        for the :py:func:`qubes.tools.print_table`.

        If :program:`qvm-volume` is running in a TTY, it will ommit duplicate
        data.

        :param list vd_list: List of :py:class:`VolumeData` objects.
        :param bool full:    If set to true duplicate data is printed even when
                             running from TTY.
        :returns: list of tupples
    '''
    output = []
    output += [('POOL:VOLUME', 'VMNAME', 'VOLUME_NAME', 'REVERT_POSSIBLE')]

    for volume in sorted(vd_list):
        if volume.domains:
            vmname, volume_name = volume.domains.pop()
            output += [(str(volume), vmname, volume_name, volume.revisions)]
            for tupple in volume.domains:
                vmname, volume_name = tupple
                if full or not sys.stdout.isatty():
                    output += [(str(volume), vmname, volume_name,
                            volume.revisions)]
                else:
                    output += [('', vmname, volume_name, volume.revisions)]
        else:
            output += [(str(volume), "")]

    return output


class VolumeData(object):
    ''' Wrapper object around :py:class:`qubes.storage.Volume`, mainly to track
        the domains a volume is attached to.
    '''
    # pylint: disable=too-few-public-methods
    def __init__(self, volume):
        self.pool = volume.pool
        self.vid = volume.vid
        if volume.revisions:
            self.revisions = 'Yes'
        else:
            self.revisions = 'No'
        self.domains = []

    def __lt__(self, other):
        return (self.pool, self.vid) < (other.pool, other.vid)

    def __str__(self):
        return "{!s}:{!s}".format(self.pool, self.vid)


def list_volumes(args):
    ''' Called by the parser to execute the qvm-volume list subcommand. '''
    app = args.app

    if hasattr(args, 'domains') and args.domains:
        domains = args.domains
    else:
        domains = app.domains
    volumes = [v for vm in domains for v in vm.volumes.values()]

    if args.pools:
        # only specified pools
        volumes = [v for v in volumes if v.pool in args.pools]

    if not args.internal:  # hide internal volumes
        volumes = [v for v in volumes if not v.internal]

    vd_dict = {}
    for volume in volumes:
        volume_data = VolumeData(volume)
        try:
            vd_dict[volume.pool][volume.vid] = volume_data
        except KeyError:
            vd_dict[volume.pool] = {volume.vid: volume_data}

    for domain in domains:  # gather the domain names
        try:
            for name, volume in domain.volumes.items():
                try:
                    volume_data = vd_dict[volume.pool][volume.vid]
                    volume_data.domains += [(domain.name, name)]
                except KeyError:
                    # Skipping volume
                    continue
        except AttributeError:
            # Skipping domain without volumes
            continue

    if hasattr(args, 'domains') and args.domains:
        result = [x  # reduce to only VolumeData with assigned domains
                  for p in vd_dict.values() for x in p.values()
                  if x.domains]
    else:
        result = [x for p in vd_dict.values() for x in p.values()]
    qubesadmin.tools.print_table(prepare_table(result, full=args.full))


def revert_volume(args):
    ''' Revert volume to previous state '''
    volume = args.volume
    app = args.app
    try:
        pool = app.pools[volume.pool]
        pool.revert(volume)
    except qubesadmin.exc.StoragePoolException as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


def extend_volumes(args):
    ''' Called by the parser to execute the :program:`qvm-block extend`
        subcommand
    '''
    volume = args.volume
    size = qubesadmin.utils.parse_size(args.size)
    volume.resize(size)


def init_list_parser(sub_parsers):
    ''' Configures the parser for the :program:`qvm-block list` subcommand '''
    # pylint: disable=protected-access
    list_parser = sub_parsers.add_parser('list', aliases=('ls', 'l'),
                                         help='list storage volumes')
    list_parser.add_argument('-p', '--pool', dest='pools',
                             action=qubesadmin.tools.PoolsAction)
    list_parser.add_argument('-i', '--internal', action='store_true',
                             help='Show internal volumes')
    list_parser.add_argument(
        '--full', action='store_true',
        help='print full line for each POOL_NAME:VOLUME_ID & vm combination')

    vm_name_group = qubesadmin.tools.VmNameGroup(
        list_parser, required=False, vm_action=qubesadmin.tools.VmNameAction,
        help='list volumes from specified domain(s)')
    list_parser._mutually_exclusive_groups.append(vm_name_group)
    list_parser.set_defaults(func=list_volumes)


def init_revert_parser(sub_parsers):
    ''' Add 'revert' action related options '''
    revert_parser = sub_parsers.add_parser(
        'revert', aliases=('rv', 'r'),
        help='revert volume to previous revision')
    revert_parser.add_argument(metavar='VM:VOLUME', dest='volume',
                               action=qubesadmin.tools.VMVolumeAction)
    revert_parser.set_defaults(func=revert_volume)


def init_extend_parser(sub_parsers):
    ''' Add 'extend' action related options '''
    extend_parser = sub_parsers.add_parser(
        "extend", help="extend volume from domain")
    extend_parser.add_argument(metavar='VM:VOLUME', dest='volume',
                               action=qubesadmin.tools.VMVolumeAction)
    extend_parser.add_argument('size', help='New size in bytes')
    extend_parser.set_defaults(func=extend_volumes)


def get_parser():
    '''Create :py:class:`argparse.ArgumentParser` suitable for
    :program:`qvm-block`.
    '''
    parser = qubesadmin.tools.QubesArgumentParser(description=__doc__,
        want_app=True)
    parser.register('action', 'parsers',
        qubesadmin.tools.AliasedSubParsersAction)
    sub_parsers = parser.add_subparsers(
        title='commands',
        description="For more information see qvm-block command -h",
        dest='command')
    init_extend_parser(sub_parsers)
    init_list_parser(sub_parsers)
    init_revert_parser(sub_parsers)
    # default action
    parser.set_defaults(func=list_volumes)

    return parser


def main(args=None, app=None):
    '''Main routine of :program:`qvm-block`.'''
    parser = get_parser()
    try:
        args = parser.parse_args(args, app=app)
        args.func(args)
    except qubesadmin.exc.QubesException as e:
        parser.print_error(str(e))
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())
