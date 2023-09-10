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


"""Qubes volume management"""

from __future__ import print_function

import argparse
import os
import sys

import collections

import qubesadmin
import qubesadmin.exc
import qubesadmin.tools
import qubesadmin.utils


def prepare_table(vd_list, full=False):
    """ Converts a list of :py:class:`VolumeData` objects to a list of tupples
        for the :py:func:`qubes.tools.print_table`.

        If :program:`qvm-volume` is running in a TTY, it will ommit duplicate
        data.

        :param list vd_list: List of :py:class:`VolumeData` objects.
        :param bool full:    If set to true duplicate data is printed even when
                             running from TTY.
        :returns: list of tupples
    """
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
    """ Wrapper object around :py:class:`qubes.storage.Volume`, mainly to track
        the domains a volume is attached to.
    """
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


def info_volume(args):
    """ Show info about selected volume """
    volume = args.volume
    info_items = (
        'pool', 'vid', 'rw', 'source', 'save_on_stop',
        'snap_on_start', 'size', 'usage', 'revisions_to_keep', 'ephemeral')
    if args.property:
        if args.property == 'revisions':
            for rev in volume.revisions:
                print(rev)
        elif args.property == 'is_outdated':
            print(volume.is_outdated())
        elif args.property in info_items:
            value = getattr(volume, args.property)
            if value is None:
                value = ''
            print(value)
        else:
            raise qubesadmin.exc.StoragePoolException(
                'No such property: {}'.format(args.property))
    else:
        info = collections.OrderedDict()
        for item in info_items:
            value = getattr(volume, item)
            if value is None:
                value = ''
            info[item] = str(value)
        info['is_outdated'] = str(volume.is_outdated())

        qubesadmin.tools.print_table(info.items())
        revisions = volume.revisions
        if revisions:
            print('List of available revisions (for revert):')
            for rev in revisions:
                print('  ' + rev)
        else:
            print('List of available revisions (for revert): none')


def config_volume(args):
    """ Change property of selected volume """
    volume = args.volume
    if args.property not in ('rw', 'revisions_to_keep', 'ephemeral'):
        raise qubesadmin.exc.QubesNoSuchPropertyError(
            'Invalid property: {}'.format(args.property))
    setattr(volume, args.property, args.value)


def import_volume(args):
    """ Import a file into volume """

    volume = args.volume
    input_path = args.input_path
    if input_path == '-':
        input_file = sys.stdin.buffer
    else:
        # pylint: disable=consider-using-with
        input_file = open(input_path, 'rb')
    try:
        if args.no_resize:
            volume.import_data(stream=input_file)
        else:
            if args.size:
                size = args.size
            else:
                try:
                    size = os.stat(input_file.fileno()).st_size
                except OSError as e:
                    raise qubesadmin.exc.QubesException(
                        'Failed to get %s file size, '
                        'specify it explicitly with --size, '
                        'or use --no-resize option', str(e))
            volume.import_data_with_size(stream=input_file, size=size)
    finally:
        if input_path != '-':
            input_file.close()


def list_volumes(args):
    """ Called by the parser to execute the qvm-volume list subcommand. """
    app = args.app

    if hasattr(args, 'domains') and args.domains:
        domains = args.domains
    else:
        domains = app.domains
    volumes = [v for vm in domains for v in vm.volumes.values()]

    if getattr(args, 'pools', None):
        # only specified pools
        volumes = [v for v in volumes if v.pool in args.pools]

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

    qubesadmin.tools.print_table(
        prepare_table(result, full=getattr(args, 'full', False)))


def revert_volume(args):
    """ Revert volume to previous state """
    volume = args.volume
    if args.revision:
        revision = args.revision
    else:
        revisions = volume.revisions
        if not revisions:
            raise qubesadmin.exc.StoragePoolException(
                'No snapshots available')
        revision = volume.revisions[-1]

    volume.revert(revision)


def extend_volumes(args):
    """ Called by the parser to execute the :program:`qvm-volume extend`
        subcommand
    """
    volume = args.volume
    size = qubesadmin.utils.parse_size(args.size)
    if not args.force and size < volume.size:
        raise qubesadmin.exc.StoragePoolException(
            'For your own safety, shrinking of %s is'
            ' disabled (%d < %d). If you really know what you'
            ' are doing, resize filesystem manually first, then use `-f` '
            'option.' %
            (volume.name, size, volume.size))
    volume.resize(size)


def init_list_parser(sub_parsers):
    """ Configures the parser for the :program:`qvm-volume list` subcommand """
    # pylint: disable=protected-access
    list_parser = sub_parsers.add_parser('list', aliases=('ls', 'l'),
                                         help='list storage volumes')
    list_parser.add_argument('-p', '--pool', metavar="POOL_NAME",
                             dest='pools', action=qubesadmin.tools.PoolsAction)
    list_parser.add_argument(
        '--full', action='store_true',
        help='print full line for each POOL_NAME:VOLUME_ID & vm combination')

    vm_name_group = qubesadmin.tools.VmNameGroup(
        list_parser, required=False, vm_action=qubesadmin.tools.VmNameAction,
        help='list volumes from specified domain(s)')
    list_parser._mutually_exclusive_groups.append(vm_name_group)
    list_parser.set_defaults(func=list_volumes)


def init_revert_parser(sub_parsers):
    """ Add 'revert' action related options """
    revert_parser = sub_parsers.add_parser(
        'revert', aliases=('rv', 'r'),
        help='revert volume to previous revision')
    revert_parser.add_argument(metavar='VM:VOLUME', dest='volume',
                               action=qubesadmin.tools.VMVolumeAction)
    revert_parser.add_argument(
        metavar='REVISION', dest='revision',
        help='Optional revision to revert to; '
             'if not specified, latest one is assumed',
        action='store', nargs='?')
    revert_parser.set_defaults(func=revert_volume)


def init_extend_parser(sub_parsers):
    """ Add 'extend' action related options """
    extend_parser = sub_parsers.add_parser(
        "resize", aliases=('extend', ), help="resize volume for domain")
    extend_parser.add_argument(metavar='VM:VOLUME', dest='volume',
                               action=qubesadmin.tools.VMVolumeAction)
    extend_parser.add_argument('size', help='New size in bytes')
    extend_parser.add_argument(
        '--force', '-f', action='store_true',
        help='Force operation, even if new size is smaller than the current '
             'one')
    extend_parser.set_defaults(func=extend_volumes)


def init_info_parser(sub_parsers):
    """ Add 'info' action related options """
    info_parser = sub_parsers.add_parser(
        'info', aliases=('i',), help='info about volume')
    info_parser.add_argument(metavar='VM:VOLUME', dest='volume',
                             action=qubesadmin.tools.VMVolumeAction)
    info_parser.add_argument(
        dest='property', action='store',
        nargs=argparse.OPTIONAL,
        help='Show only this property instead of all of them; use '
             '\'revisions\' to list available revisions')
    info_parser.set_defaults(func=info_volume)


def init_config_parser(sub_parsers):
    """ Add 'info' action related options """
    info_parser = sub_parsers.add_parser(
        'config', aliases=('c', 'set', 's'),
        help='set config option for a volume')
    info_parser.add_argument(metavar='VM:VOLUME', dest='volume',
                             action=qubesadmin.tools.VMVolumeAction)
    info_parser.add_argument(dest='property', action='store')
    info_parser.add_argument(dest='value', action='store')
    info_parser.set_defaults(func=config_volume)


def init_import_parser(sub_parsers):
    """ Add 'import' action related options """
    import_parser = sub_parsers.add_parser(
        'import', help='import volume data')
    import_parser.add_argument(metavar='VM:VOLUME', dest='volume',
                               action=qubesadmin.tools.VMVolumeAction)
    import_parser.add_argument('input_path', metavar='PATH',
        help='File path to import, use \'-\' for standard input')
    import_parser.add_argument('--size', action='store', type=int,
        help='Set volume size to this value in bytes')
    import_parser.add_argument('--no-resize', action='store_true',
        help='Do not resize volume before importing data')
    import_parser.set_defaults(func=import_volume)


def get_parser():
    """Create :py:class:`argparse.ArgumentParser` suitable for
    :program:`qvm-volume`.
    """
    parser = qubesadmin.tools.QubesArgumentParser(description=__doc__)
    parser.register(
        'action', 'parsers',
        qubesadmin.tools.AliasedSubParsersAction)
    sub_parsers = parser.add_subparsers(
        title='commands',
        description="For more information see qvm-volume command -h",
        dest='command')
    init_info_parser(sub_parsers)
    init_config_parser(sub_parsers)
    init_extend_parser(sub_parsers)
    init_list_parser(sub_parsers)
    init_revert_parser(sub_parsers)
    init_import_parser(sub_parsers)
    # default action
    parser.set_defaults(func=list_volumes)

    return parser


def main(args=None, app=None):
    """Main routine of :program:`qvm-volume`."""
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
