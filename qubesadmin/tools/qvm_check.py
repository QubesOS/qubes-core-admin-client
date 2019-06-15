# pylint: disable=too-few-public-methods

#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2016 Bahtiar `kalkin-` Gadimov <bahtiar@gadimov.de>
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
''' Exits sucessfull if the provided domains exists, else returns failure '''

from __future__ import print_function

import sys

from qubesadmin.toolparsers.qvm_check import get_parser


def print_msg(domains, what_single, what_plural):
    '''Print message in appropriate form about given domain(s)'''
    if not domains:
        print("None of given VM {!s}".format(what_single))
    elif len(domains) == 1:
        print("VM {!s} {!s}".format(domains[0], what_single))
    else:
        txt = ", ".join([vm.name for vm in sorted(domains)])
        print("VMs {!s} {!s}".format(txt, what_plural))


def main(args=None, app=None):
    '''Main function of qvm-check tool'''
    parser = get_parser()
    args = parser.parse_args(args, app=app)
    domains = args.domains
    if args.running:
        running = [vm for vm in domains if vm.is_running()]
        if args.verbose:
            print_msg(running, "is running", "are running")
        return 0 if running else 1
    if args.paused:
        paused = [vm for vm in domains if vm.is_paused()]
        if args.verbose:
            print_msg(paused, "is paused", "are paused")
        return 0 if paused else 1
    if args.template:
        template = [vm for vm in domains if vm.klass == 'TemplateVM']
        if args.verbose:
            print_msg(template, "is a template", "are templates")
        return 0 if template else 1
    if args.verbose:
        print_msg(domains, "exists", "exist")
    return 0 if domains else 1

if __name__ == '__main__':
    sys.exit(main())
