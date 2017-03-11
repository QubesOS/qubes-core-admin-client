# encoding=utf-8
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2010-2015  Joanna Rutkowska <joanna@invisiblethingslab.com>
# Copyright (C) 2015       Wojtek Porczyk <woju@invisiblethingslab.com>
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

''' Manipulate VM properties.'''
# TODO list only non-default properties

from __future__ import print_function

import sys
import textwrap

import qubesmgmt
import qubesmgmt.tools
import qubesmgmt.utils
import qubesmgmt.vm


def get_parser(vmname_nargs=1):
    '''Return argument parser for generic property-related tool'''
    parser = qubesmgmt.tools.QubesArgumentParser(
        vmname_nargs=vmname_nargs)

    parser.add_argument('--help-properties',
        action='store_true',
        help='list all available properties with short descriptions and exit')

    parser.add_argument('--get', '-g',
        action='store_true',
        help='Ignored; for compatibility with older scripts.')

    parser.add_argument('--set', '-s',
        action='store_true',
        help='Ignored; for compatibility with older scripts.')

    parser.add_argument('property', metavar='PROPERTY',
        nargs='?',
        help='name of the property to show or change')

    parser_value = parser.add_mutually_exclusive_group()

    parser_value.add_argument('value', metavar='VALUE',
        nargs='?',
        help='new value of the property')

    parser.add_argument('--unset', '--default', '--delete', '-D',
        dest='delete',
        action='store_true',
        help='unset the property; '
             'if property has default value, it will be used instead')

    return parser


def process_actions(parser, args, target):
    '''Handle actions for generic property-related tool

    :param parser: argument parser used to produce args
    :param args: arguments to handle
    :param target: object on which actions should be performed
    '''
    if args.help_properties:
        properties = target.property_list()
        width = max(len(prop) for prop in properties)
        wrapper = textwrap.TextWrapper(width=80,
            initial_indent='  ', subsequent_indent=' ' * (width + 6))

        for prop in sorted(properties):
            help_text = target.property_help(prop)

            print(wrapper.fill('{name:{width}s}  {help_text!s}'.format(
                name=prop, width=width, help_text=help_text)))

        return 0

    if args.property is None:
        properties = target.property_list()
        width = max(len(prop) for prop in properties)

        for prop in sorted(properties):
            try:
                value = getattr(target, prop)
            except AttributeError:
                print('{name:{width}s}  U'.format(
                    name=prop, width=width))
                continue

            if target.property_is_default(prop):
                print('{name:{width}s}  D  {value!s}'.format(
                    name=prop, width=width, value=value))
            else:
                print('{name:{width}s}  -  {value!s}'.format(
                    name=prop, width=width, value=value))

        return 0
    else:
        args.property = args.property.replace('-', '_')

    if args.value is not None:
        try:
            setattr(target, args.property, args.value)
        except AttributeError:
            parser.error('no such property: {!r}'.format(args.property))
        return 0

    if args.delete:
        try:
            delattr(target, args.property)
        except AttributeError:
            parser.error('no such property: {!r}'.format(args.property))
        return 0

    try:
        print(str(getattr(target, args.property)))
    except AttributeError:
        parser.error('no such property: {!r}'.format(args.property))

    return 0


def main(args=None, app=None):  # pylint: disable=missing-docstring
    parser = get_parser(1)
    args = parser.parse_args(args, app=app)
    target = args.domains.pop()
    return process_actions(parser, args, target)


if __name__ == '__main__':
    sys.exit(main())
