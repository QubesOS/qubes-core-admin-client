# encoding=utf-8
#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2010-2015  Joanna Rutkowska <joanna@invisiblethingslab.com>
# Copyright (C) 2013-2015  Marek Marczykowski-Górecki
#                              <marmarek@invisiblethingslab.com>
# Copyright (C) 2014-2015  Wojtek Porczyk <woju@invisiblethingslab.com>
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

"""Various utility functions."""

from __future__ import annotations

import fcntl
import os
import re
import typing
from collections.abc import Iterable

import qubesadmin.exc
from qubesadmin.exc import QubesValueError

if typing.TYPE_CHECKING:
    from qubesadmin.app import QubesBase
    from qubesadmin.vm import QubesVM


def parse_size(size: str) -> int:
    """Parse human readable size into bytes."""
    units = [
        ('K', 1000), ('KB', 1000),
        ('M', 1000 * 1000), ('MB', 1000 * 1000),
        ('G', 1000 * 1000 * 1000), ('GB', 1000 * 1000 * 1000),
        ('Ki', 1024), ('KiB', 1024),
        ('Mi', 1024 * 1024), ('MiB', 1024 * 1024),
        ('Gi', 1024 * 1024 * 1024), ('GiB', 1024 * 1024 * 1024),
    ]

    size = size.strip().upper()
    if size.isdigit():
        return int(size)

    for unit, multiplier in units:
        if size.endswith(unit.upper()):
            size = size[:-len(unit)].strip()
            return int(size) * multiplier

    raise qubesadmin.exc.QubesException("Invalid size: {0}.".format(size))


def mbytes_to_kmg(size: float | int) -> str:
    """Convert mbytes to human readable format."""
    if size > 1024:
        return "%d GiB" % (size / 1024)
    return "%d MiB" % size


def kbytes_to_kmg(size: float | int) -> str:
    """Convert kbytes to human readable format."""
    if size > 1024:
        return mbytes_to_kmg(size / 1024)
    return "%d KiB" % size


def bytes_to_kmg(size: int) -> str:
    """Convert bytes to human readable format."""
    if size > 1024:
        return kbytes_to_kmg(size / 1024)
    return "%d B" % size


def size_to_human(size: int) -> str:
    """Humane readable size, with 1/10 precision"""
    if size < 1024:
        return str(size)
    if size < 1024 * 1024:
        return str(round(size / 1024.0, 1)) + ' KiB'
    if size < 1024 * 1024 * 1024:
        return str(round(size / (1024.0 * 1024), 1)) + ' MiB'
    return str(round(size / (1024.0 * 1024 * 1024), 1)) + ' GiB'


UPDATES_DEFAULT_VM_DISABLE_FLAG = \
    '/var/lib/qubes/updates/vm-default-disable-updates'


def updates_vms_status(qvm_collection: QubesBase) -> bool | None:
    """Check whether all VMs have the same check-updates value;
    if yes, return it; otherwise, return None
    """
    # default value:
    status = not os.path.exists(UPDATES_DEFAULT_VM_DISABLE_FLAG)
    # check if all the VMs uses the default value
    for vm in qvm_collection.domains:
        if vm.qid == 0:
            continue
        if vm.features.get('check-updates', True) != status:
            # "mixed"
            return None
    return status


def vm_dependencies(app: QubesBase, reference_vm: QubesVM)\
        -> list[tuple[QubesVM | None, str]]:
    """Helper function that returns a list of all the places a given VM is used
    in. Output is a list of tuples (property_holder, property_name), with None
    as property_holder for global properties
    """

    result = []

    global_properties = ['default_dispvm', 'default_netvm', 'default_guivm',
                         'default_audiovm', 'default_template', 'clockvm',
                         'updatevm', 'management_dispvm']

    for prop in global_properties:
        if reference_vm == getattr(app, prop, None):
            result.append((None, prop))

    vm_properties = ['template', 'netvm', 'guivm', 'audiovm',
                     'default_dispvm', 'management_dispvm']

    for vm in app.domains:
        if vm == reference_vm:
            continue
        is_preload = getattr(vm, "is_preload", False)
        for prop in vm_properties:
            if not hasattr(vm, prop):
                continue
            try:
                is_prop_default = vm.property_is_default(prop)
            except qubesadmin.exc.QubesPropertyAccessError:
                is_prop_default = False
            if (
                reference_vm == getattr(vm, prop, None)
                and not is_prop_default
                and not (
                    is_preload
                    and prop == "template"
                    or (
                        prop == "default_dispvm"
                        and getattr(vm, "template", None) == vm
                    )
                )
            ):
                result.append((vm, prop))

    return result


def encode_for_vmexec(args: Iterable[str]) -> str:
    """
    Encode an argument list for qubes.VMExec call.
    """

    def encode(part: re.Match) -> bytes:
        if part.group(0) == b'-':
            return b'--'
        return '-{:02X}'.format(ord(part.group(0))).encode('ascii')

    parts = []
    for arg in args:
        part = re.sub(br'[^a-zA-Z0-9_.]', encode, arg.encode('utf-8'))
        parts.append(part)
    return b'+'.join(parts).decode('ascii')

class LockFile:
    """Simple locking context manager. It opens a file with an advisory lock
    taken (fcntl.lockf)"""
    def __init__(self, path: str, nonblock: bool=False):
        """Open the file. Call *acquire* or enter the context to lock
        the file"""
        # pylint: disable=consider-using-with
        self.file = open(path, "w", encoding='ascii')
        self.nonblock = nonblock

    def __enter__(self, *args, **kwargs) -> LockFile:
        self.acquire()
        return self

    def acquire(self) -> None:
        """Lock the opened file"""
        fcntl.lockf(self.file,
                    fcntl.LOCK_EX | (fcntl.LOCK_NB if self.nonblock else 0))

    def __exit__(self, exc_type: object | None = None,
                 exc_value: object | None = None,
                 traceback: object | None = None) -> None:
        self.release()

    def release(self) -> None:
        """Unlock the file and close the file object"""
        fcntl.lockf(self.file, fcntl.LOCK_UN)
        self.file.close()


def qbool(value: str | int | bool) -> bool:
    """
    Property setter for boolean properties.

    It accepts (case-insensitive) ``'0'``, ``'no'`` and ``false`` as
    :py:obj:`False` and ``'1'``, ``'yes'`` and ``'true'`` as
    :py:obj:`True`.
    """

    if isinstance(value, str):
        lcvalue = value.lower()
        if lcvalue in ("0", "no", "false", "off"):
            return False
        if lcvalue in ("1", "yes", "true", "on"):
            return True
        raise QubesValueError(
            "Invalid literal for boolean property: {!r}".format(value)
        )

    return bool(value)
