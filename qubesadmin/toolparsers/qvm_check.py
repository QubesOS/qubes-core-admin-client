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
'''Parser for qvm-check'''

from __future__ import print_function

import qubesadmin.toolparsers

def get_parser():
    parser = qubesadmin.toolparsers.QubesArgumentParser(description=__doc__,
        vmname_nargs='+')
    parser.add_argument("--running", action="store_true", dest="running",
        default=False, help="Determine if (any of given) VM is running")
    parser.add_argument("--paused", action="store_true", dest="paused",
        default=False, help="Determine if (any of given) VM is paused")
    parser.add_argument("--template", action="store_true", dest="template",
        default=False, help="Determine if (any of given) VM is a template")
    return parser
