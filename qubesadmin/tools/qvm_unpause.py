# encoding=utf-8
#
# The Qubes OS Project, https://www.qubes-os.org/
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

"""qvm-unpause - Unpause a domain"""

import sys
import qubesadmin


parser = qubesadmin.tools.QubesArgumentParser(
    vmname_nargs="+", description="unpause a domain"
)


def main(args=None, app=None):
    """Main routine of :program:`qvm-unpause`.

    :param list args: Optional arguments to override those delivered from \
        command line.
    """

    args = parser.parse_args(args, app=app)
    exit_code = 0
    for domain in args.domains:
        try:
            domain.unpause()
        except (IOError, OSError, qubesadmin.exc.QubesException) as e:
            exit_code = 1
            parser.print_error(str(e))

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
