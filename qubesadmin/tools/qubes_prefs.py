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

""" Manipulate global properties."""

from __future__ import print_function

import sys

import qubesadmin
import qubesadmin.tools.qvm_prefs


def get_parser():
    """Prepare argument parser"""
    return qubesadmin.tools.qvm_prefs.get_parser(None)


def main(args=None, app=None):  # pylint: disable=missing-docstring
    parser = get_parser()
    args = parser.parse_args(args, app=app)
    target = args.app
    return qubesadmin.tools.qvm_prefs.process_actions(parser, args, target)


if __name__ == "__main__":
    sys.exit(main())
