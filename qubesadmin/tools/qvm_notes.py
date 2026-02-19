#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2025 Marek Marczykowski-Górecki
#                               <marmarek@invisiblethingslab.com>
# Copyright (C) 2025 Ali Mirjamali <ali@mirjamali.com>
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

""" Qube notes manipulation tool """


import logging
import os
import subprocess
import sys
import tempfile

import qubesadmin
import qubesadmin.exc
import qubesadmin.tools


class ConfirmAction:
    """Confirmation for set, delete and import actions"""

    use_the_force = False

    def __init__(self, message: str) -> None:
        if self.use_the_force:
            return
        print(message)
        if input("Are you certain? [y/N]").upper() != "Y":
            sys.exit(2)


def get_parser():
    """Create :py:class:`argparse.ArgumentParser` suitable for
    :program:`qvm-notes`.
    """
    parser = qubesadmin.tools.QubesArgumentParser(
        description="Manipulate qube notes",
        vmname_nargs=1,
        epilog=(
            "Each qube notes is limited to 256KB of clear-text. "
            "See program manpage for more information on other limitations."
        ),
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Do not prompt for confirmation; assume `yes`",
    )
    action_group = parser.add_argument_group(
        title="Notes action options",
        description="note: `--edit` is the default action for qube notes.",
    )
    group = action_group.add_mutually_exclusive_group()
    group.add_argument(
        "--edit",
        "-e",
        action="store_const",
        dest="action",
        const="edit",
        help="Edit qube notes in $EDITOR (default text editor)",
    )
    group.add_argument(
        "--print",
        "-p",
        action="store_const",
        dest="action",
        const="print",
        help="Print qube notes",
    )
    group.add_argument(
        "--import",
        "-i",
        dest="filename",
        metavar="FILENAME",
        help="Import qube notes from file",
    )
    group.add_argument(
        "--set",
        "-s",
        dest="notes",
        metavar="'NOTES'",
        help="Set qube notes from provided string",
    )
    group.add_argument(
        "--append",
        dest="append",
        metavar="'NOTES'",
        help="Append the provided string to qube notes",
    )
    group.add_argument(
        "--delete",
        "-d",
        action="store_const",
        dest="action",
        const="delete",
        help="Delete qube notes",
    )

    # Setting notes editing as default preferred action
    parser.set_defaults(action="edit")
    return parser


def main(args=None, app=None):
    """Main function of Program:`qvm-notes`."""
    app = app or qubesadmin.Qubes()
    parser = get_parser()
    args = parser.parse_args(args, app=app)
    qube = args.domains.pop()

    ConfirmAction.use_the_force = args.force

    if args.filename:
        args.action = "import"
    if args.notes:
        args.action = "set"
    if args.append:
        args.action = "append"

    exit_code: int = 0

    match args.action:
        case "edit":
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w+",
                    prefix=qube.name + "_qube_",
                    suffix="_notes.txt",
                    delete_on_close=False,
                ) as temp:
                    temp.write(qube.get_notes())
                    temp.close()
                    last_modified = os.path.getmtime(temp.name)
                    edit_cmd = "${VISUAL:-${EDITOR:-vi}} " + temp.name
                    subprocess.run(edit_cmd, shell=True, check=True)
                    if last_modified != os.path.getmtime(temp.name):
                        with open(temp.name, encoding="utf-8") as notes_file:
                            qube.set_notes(notes_file.read())
                    # os.unlink(temp.name)
            except qubesadmin.exc.QubesException as e:
                logging.error("Failed to edit qube notes: %s", str(e))
                exit_code = 1
        case "print":
            try:
                print(qube.get_notes())
            except qubesadmin.exc.QubesException as e:
                logging.error("Unable to get qube notes: %s", str(e))
                exit_code = 1
        case "set":
            try:
                qube.set_notes(args.notes)
            except qubesadmin.exc.QubesException as e:
                logging.error("Unable to set qube notes: %s", str(e))
                exit_code = 1
        case "import":
            try:
                with open(args.filename, encoding="utf-8") as notes_file:
                    notes = notes_file.read()
                qube.set_notes(notes)
            except qubesadmin.exc.QubesException as e:
                logging.error("Unable to import notes file: %s", str(e))
                exit_code = 1
        case "append":
            try:
                notes = qube.get_notes()
                if notes.split("\n")[-1]:
                    notes += "\n"
                qube.set_notes(notes + args.append)
            except qubesadmin.exc.QubesException as e:
                logging.error("Unable to append qube notes: %s", str(e))
                exit_code = 1
        case "delete":
            try:
                ConfirmAction("You are about to delete existing qube notes")
                qube.set_notes("")
            except qubesadmin.exc.QubesException as e:
                logging.error("Unable to delete qube notes: %s", str(e))
                exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
