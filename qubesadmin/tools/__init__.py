# encoding=utf-8
#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2015  Joanna Rutkowska <joanna@invisiblethingslab.com>
# Copyright (C) 2015  Wojtek Porczyk <woju@invisiblethingslab.com>
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

"""Qubes' command line tools
"""

from __future__ import print_function

import argparse
import importlib
import logging
import os
import subprocess
import sys
import textwrap

import qubesadmin.log
import qubesadmin.exc
import qubesadmin.vm

#: constant returned when some action should be performed on all qubes
VM_ALL = object()


class QubesAction(argparse.Action):
    """Interface providing a convinience method to be called, after
    `namespace.app` is instantiated.
    """

    # pylint: disable=too-few-public-methods
    def parse_qubes_app(self, parser, namespace):
        """This method is called by :py:class:`qubes.tools.QubesArgumentParser`
        after the `namespace.app` is instantiated. Oerwrite this method when
        extending :py:class:`qubes.tools.QubesAction` to initialized values
        based on the `namespace.app`
        """
        raise NotImplementedError


class PropertyAction(argparse.Action):
    """Action for argument parser that stores a property."""

    # pylint: disable=redefined-builtin,too-few-public-methods
    def __init__(
        self,
        option_strings,
        dest,
        metavar="NAME=VALUE",
        required=False,
        help="set property to a value",
    ):
        super().__init__(
            option_strings, "properties", metavar=metavar, default={}, help=help
        )

    def __call__(self, parser, namespace, values, option_string=None):
        try:
            prop, value = values.split("=", 1)
        except ValueError:
            parser.error("invalid property token: {!r}".format(values))

        properties = getattr(namespace, self.dest)
        # copy it, to not modify _mutable_ self.default
        if not properties:
            properties = properties.copy()
        properties[prop] = value
        setattr(namespace, self.dest, properties)


class SinglePropertyAction(argparse.Action):
    """Action for argument parser that stores a property."""

    # pylint: disable=redefined-builtin,too-few-public-methods
    def __init__(
        self,
        option_strings,
        dest,
        metavar="VALUE",
        const=None,
        nargs=None,
        required=False,
        help=None,
    ):
        if help is None:
            help = "set {!r} property to a value".format(dest)
            if const is not None:
                help += " {!r}".format(const)

        if const is not None:
            nargs = 0

        super().__init__(
            option_strings,
            "properties",
            metavar=metavar,
            help=help,
            default={},
            const=const,
            nargs=nargs,
        )

        self.name = dest

    def __call__(self, parser, namespace, values, option_string=None):
        if values is self.default and self.default == {}:
            return

        properties = getattr(namespace, self.dest)
        # copy it, to not modify _mutable_ self.default
        if not properties:
            properties = properties.copy()
        properties[self.name] = values if self.const is None else self.const
        setattr(namespace, self.dest, properties)


class VmNameAction(QubesAction):
    """Action for parsing one ore multiple domains from provided VMNAMEs"""

    # pylint: disable=too-few-public-methods,redefined-builtin
    def __init__(
        self, option_strings, nargs=1, dest="vmnames", help=None, **kwargs
    ):
        if help is None:
            if nargs == argparse.OPTIONAL:
                help = "at most one domain name"
            elif nargs == 1:
                help = "a domain name"
            elif nargs == argparse.ZERO_OR_MORE:
                help = "zero or more domain names"
            elif nargs == argparse.ONE_OR_MORE:
                help = "one or more domain names"
            elif nargs > 1:
                help = "%s domain names" % nargs
            else:
                raise argparse.ArgumentError(
                    nargs,
                    "Passed unexpected value {!s} as {!s} nargs ".format(
                        nargs, dest
                    ),
                )

        super().__init__(
            option_strings, dest=dest, help=help, nargs=nargs, **kwargs
        )

    def __call__(self, parser, namespace, values, option_string=None):
        """Set ``namespace.vmname`` to ``values``"""
        setattr(namespace, self.dest, values)

    def parse_qubes_app(self, parser, namespace):
        assert hasattr(namespace, "app")
        setattr(namespace, "domains", [])
        app = namespace.app
        if hasattr(namespace, "all_domains") and namespace.all_domains:
            namespace.domains = [
                vm
                for vm in app.domains
                if not vm.klass == "AdminVM"
                and vm.name not in namespace.exclude
            ]
        else:
            if hasattr(namespace, "exclude") and namespace.exclude:
                parser.error("--exclude can only be used with --all")

            if self.nargs == argparse.OPTIONAL:
                if getattr(namespace, "dispvm", None) is not None:
                    return
                vm_name = getattr(namespace, self.dest, None)
                if vm_name is not None:
                    try:
                        namespace.domains += [app.domains[vm_name]]
                    except KeyError:
                        parser.error("no such domain: {!r}".format(vm_name))
            else:
                for vm_name in getattr(namespace, self.dest):
                    try:
                        namespace.domains += [app.domains[vm_name]]
                    except KeyError:
                        parser.error("no such domain: {!r}".format(vm_name))


class RunningVmNameAction(VmNameAction):
    """Action for argument parser that gets a running domain from VMNAME"""

    # pylint: disable=too-few-public-methods

    def __init__(
        self, option_strings, nargs=1, dest="vmnames", help=None, **kwargs
    ):
        # pylint: disable=redefined-builtin
        if help is None:
            if nargs == argparse.OPTIONAL:
                help = "at most one running domain"
            elif nargs == 1:
                help = "running domain name"
            elif nargs == argparse.ZERO_OR_MORE:
                help = "zero or more running domains"
            elif nargs == argparse.ONE_OR_MORE:
                help = "one or more running domains"
            elif nargs > 1:
                help = "%s running domains" % nargs
            else:
                raise argparse.ArgumentError(
                    nargs,
                    "Passed unexpected value {!s} as {!s} nargs ".format(
                        nargs, dest
                    ),
                )
        super().__init__(
            option_strings, dest=dest, help=help, nargs=nargs, **kwargs
        )

    def parse_qubes_app(self, parser, namespace):
        super().parse_qubes_app(parser, namespace)
        for vm in namespace.domains:
            if not vm.is_running():
                parser.error_runtime(
                    "domain {!r} is not running".format(vm.name)
                )


class VolumeAction(QubesAction):
    """Action for argument parser that gets the
    :py:class:``qubes.storage.Volume`` from a POOL_NAME:VOLUME_ID string.
    """

    # pylint: disable=too-few-public-methods

    def __init__(
        self, help="A pool & volume id combination", required=True, **kwargs
    ):
        # pylint: disable=redefined-builtin
        super().__init__(help=help, required=required, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        """Set ``namespace.vmname`` to ``values``"""
        setattr(namespace, self.dest, values)

    def parse_qubes_app(self, parser, namespace):
        """Acquire the :py:class:``qubes.storage.Volume`` object from
        ``namespace.app``.
        """
        assert hasattr(namespace, "app")
        app = namespace.app

        try:
            pool_name, vid = getattr(namespace, self.dest).split(":")
            try:
                pool = app.pools[pool_name]
                volume = [v for v in pool.volumes if v.vid == vid]
                assert volume > 1, "Duplicate vids in pool %s" % pool_name
                if not volume:
                    parser.error_runtime(
                        "no volume with id {!r} pool: {!r}".format(
                            vid, pool_name
                        )
                    )
                else:
                    setattr(namespace, self.dest, volume[0])
            except KeyError:
                parser.error_runtime("no pool {!r}".format(pool_name))
        except ValueError:
            parser.error("expected a pool & volume id combination like foo:bar")


class VMVolumeAction(QubesAction):
    """Action for argument parser that gets the
    :py:class:``qubes.storage.Volume`` from a VM:VOLUME string.
    """

    # pylint: disable=too-few-public-methods

    def __init__(
        self, help="A pool & volume id combination", required=True, **kwargs
    ):
        # pylint: disable=redefined-builtin
        super().__init__(help=help, required=required, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        """Set ``namespace.vmname`` to ``values``"""
        setattr(namespace, self.dest, values)

    def parse_qubes_app(self, parser, namespace):
        """Acquire the :py:class:``qubes.storage.Volume`` object from
        ``namespace.app``.
        """
        assert hasattr(namespace, "app")
        app = namespace.app

        try:
            vm_name, vol_name = getattr(namespace, self.dest).split(":")
            try:
                vm = app.domains[vm_name]
                try:
                    volume = vm.volumes[vol_name]
                    setattr(namespace, self.dest, volume)
                except KeyError:
                    parser.error_runtime(
                        "vm {!r} has no volume {!r}".format(vm_name, vol_name)
                    )
            except KeyError:
                parser.error_runtime("no vm {!r}".format(vm_name))
        except ValueError:
            parser.error("expected a vm & volume combination like foo:bar")


class PoolsAction(QubesAction):
    """Action for argument parser to gather multiple pools"""

    # pylint: disable=too-few-public-methods

    def __call__(self, parser, namespace, values, option_string=None):
        """Set ``namespace.vmname`` to ``values``"""
        if hasattr(namespace, self.dest) and getattr(namespace, self.dest):
            names = getattr(namespace, self.dest)
        else:
            names = []
        names += [values]
        setattr(namespace, self.dest, names)

    def parse_qubes_app(self, parser, namespace):
        app = namespace.app
        pool_names = getattr(namespace, self.dest)
        if pool_names:
            try:
                pools = [app.pools[name] for name in pool_names]
                setattr(namespace, self.dest, pools)
            except qubesadmin.exc.QubesException as e:
                parser.error(str(e))
                sys.exit(2)
            except KeyError:
                parser.error("No such pools: %s" % pool_names)
                sys.exit(2)


class QubesArgumentParser(argparse.ArgumentParser):
    """Parser preconfigured for use in most of the Qubes command-line tools.

    :param mixed vmname_nargs: The number of ``VMNAME`` arguments that should be
        consumed. Values include:
        * N (an integer) consumes N arguments (and produces a list)
        * '?' consumes zero or one arguments
        * '*' consumes zero or more arguments (and produces a list)
        * '+' consumes one or more arguments (and produces a list)

    :param show_forceroot: don't hide --force-root parameter, prevent running
        as root unless it is given

    *kwargs* are passed to :py:class:`argparser.ArgumentParser`.

    Currenty supported options:
        ``--force-root`` (optional, ignored, help is suppressed)
        ``--offline-mode`` do not talk to hypervisor (help is suppressed)
        ``--verbose`` and ``--quiet``
    """

    def __init__(self, vmname_nargs=None, show_forceroot=False, **kwargs):

        super().__init__(add_help=False, **kwargs)

        self._vmname_nargs = vmname_nargs

        self.add_argument(
            "--verbose", "-v", action="count", help="increase verbosity"
        )

        self.add_argument(
            "--quiet", "-q", action="count", help="decrease verbosity"
        )

        if show_forceroot:
            self.add_argument(
                "--force-root",
                action="store_true",
                default=False,
                help="Force running the tool even if called as root",
            )
        else:
            self.add_argument(
                "--force-root",
                action="store_true",
                default=False,
                help=argparse.SUPPRESS,
            )
        self._complain_if_root = show_forceroot

        self.add_argument(
            "--help",
            "-h",
            action=SubParsersHelpAction,
            help="show this help message and exit",
        )

        if self._vmname_nargs in [argparse.ZERO_OR_MORE, argparse.ONE_OR_MORE]:
            vm_name_group = VmNameGroup(
                self,
                required=(
                    self._vmname_nargs
                    not in [argparse.ZERO_OR_MORE, argparse.OPTIONAL]
                ),
            )
            self._mutually_exclusive_groups.append(vm_name_group)
        elif self._vmname_nargs is not None:
            self.add_argument(
                "VMNAME", nargs=self._vmname_nargs, action=VmNameAction
            )

        self.set_defaults(verbose=1, quiet=0)

    def parse_args(self, *args, **kwargs):
        # pylint: disable=arguments-differ,signature-differs
        # hack for tests
        app = kwargs.pop("app", None)
        namespace = super().parse_args(*args, **kwargs)

        if (
            self._complain_if_root
            and os.getuid() == 0
            and not namespace.force_root
        ):
            self.error("refusing to run as root; add --force-root to override")

        self.set_qubes_verbosity(namespace)
        if app is not None:
            namespace.app = app
        else:
            namespace.app = qubesadmin.Qubes()

        for action in self._actions:
            # pylint: disable=protected-access
            if issubclass(action.__class__, QubesAction):
                action.parse_qubes_app(self, namespace)
            elif issubclass(
                action.__class__, argparse._SubParsersAction
            ):  # pylint: disable=no-member
                assert hasattr(namespace, "command")
                command = namespace.command
                if command is None:
                    continue
                subparser = action._name_parser_map[command]
                for subaction in subparser._actions:
                    if issubclass(subaction.__class__, QubesAction):
                        subaction.parse_qubes_app(self, namespace)

        return namespace

    def error_runtime(self, message, exit_code=1):
        """Runtime error, without showing usage.

        :param str message: message to show
        """
        self.exit(exit_code, "{}: error: {}\n".format(self.prog, message))

    @staticmethod
    def get_loglevel_from_verbosity(namespace):
        """Return loglevel calculated from quiet and verbose arguments"""
        return (namespace.quiet - namespace.verbose) * 10 + logging.WARNING

    @staticmethod
    def set_qubes_verbosity(namespace):
        """Apply a verbosity setting.

        This is done by configuring global logging.
        :param argparse.Namespace args: args as parsed by parser
        """

        verbose = namespace.verbose - namespace.quiet

        if verbose >= 2:
            qubesadmin.log.enable_debug()
        elif verbose >= 1:
            qubesadmin.log.enable()

    def print_error(self, *args, **kwargs):
        """Print to ``sys.stderr``"""
        print(*args, file=sys.stderr, **kwargs)


class SubParsersHelpAction(argparse._HelpAction):
    """Print help for all options and all subparsers"""

    # source https://stackoverflow.com/a/24122778
    # pylint: disable=protected-access,too-few-public-methods

    @staticmethod
    def _indent(indent, text):
        """Indent *text* by *indent* spaces"""
        return "\n".join((" " * indent) + l for l in text.splitlines())

    def __call__(self, parser, namespace, values, option_string=None):
        parser.print_help()

        # retrieve subparsers from parser
        subparsers_actions = [
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        ]
        # there will probably only be one subparser_action,
        # but better save than sorry
        for subparsers_action in subparsers_actions:
            # get all subparsers and print help
            for pseudo_action in subparsers_action._choices_actions:
                choice = pseudo_action.dest.split(" ", 1)[0]
                subparser = subparsers_action.choices[choice]
                print("\nCommand '{}':".format(choice))
                choice_help = subparser.format_usage()
                choice_help = self._indent(2, choice_help)
                print(choice_help)
        parser.exit()


class AliasedSubParsersAction(argparse._SubParsersAction):
    """SubParser with support for action aliases"""

    # source https://gist.github.com/sampsyo/471779
    # pylint: disable=protected-access,too-few-public-methods,missing-docstring
    class _AliasedPseudoAction(argparse.Action):
        # pylint: disable=redefined-builtin
        def __init__(self, name, aliases, help):
            dest = name
            if aliases:
                dest += " (%s)" % ",".join(aliases)
            super().__init__(option_strings=[], dest=dest, help=help)

        def __call__(self, parser, namespace, values, option_string=None):
            pass

    def add_parser(self, name, **kwargs):
        if "aliases" in kwargs:
            aliases = kwargs["aliases"]
            del kwargs["aliases"]
        else:
            aliases = []

        local_parser = super().add_parser(name, **kwargs)

        # Make the aliases work.
        for alias in aliases:
            self._name_parser_map[alias] = local_parser
        # Make the help text reflect them, first removing old help entry.
        if "help" in kwargs:
            self._choices_actions.pop()
            pseudo_action = self._AliasedPseudoAction(
                name, aliases, kwargs.pop("help")
            )
            self._choices_actions.append(pseudo_action)

        return local_parser


def get_parser_for_command(command):
    """Get parser for given qvm-tool.

    :param str command: command name
    :rtype: argparse.ArgumentParser
    :raises ImportError: when command's module is not found
    :raises AttributeError: when parser was not found
    """

    module = importlib.import_module(
        "." + command.replace("-", "_"), "qubesadmin.tools"
    )

    try:
        parser = module.parser
    except AttributeError:
        try:
            parser = module.get_parser()
        except AttributeError:
            raise AttributeError("cannot find parser in module")

    return parser


# pylint: disable=protected-access
class VmNameGroup(argparse._MutuallyExclusiveGroup):
    """Adds an a VMNAME, --all & --exclude parameters to a
    :py:class:``argparse.ArgumentParser```.
    """

    def __init__(self, container, required, vm_action=VmNameAction, help=None):
        # pylint: disable=redefined-builtin
        super().__init__(container, required=required)
        if not help:
            help = "perform the action on all qubes"
        self.add_argument(
            "--all", action="store_true", dest="all_domains", help=help
        )
        container.add_argument(
            "--exclude",
            action="append",
            default=[],
            help="exclude the qube from --all",
        )

        #  ⚠ the default parameter below is important! ⚠
        #  See https://stackoverflow.com/questions/35044288 and
        #  `argparse.ArgumentParser.parse_args()` implementation
        self.add_argument("VMNAME", action=vm_action, nargs="*", default=[])


def print_table(table, stream=None):
    """Uses the unix column command to print pretty table.

    :param str text: list of lists/sets
    """
    unit_separator = chr(31)
    cmd = ["column", "-t", "-s", unit_separator]
    text_table = "\n".join([unit_separator.join(row) for row in table])
    text_table += "\n"

    if stream is None:
        stream = sys.stdout

    # for tests...
    if stream != sys.__stdout__:
        with subprocess.Popen(
            cmd + ["-c", "88"], stdin=subprocess.PIPE, stdout=subprocess.PIPE
        ) as p:
            p.stdin.write(text_table.encode())
            (out, _) = p.communicate()
        stream.write(str(out.decode()))
    else:
        with subprocess.Popen(cmd, stdin=subprocess.PIPE) as p:
            p.communicate(text_table.encode())
