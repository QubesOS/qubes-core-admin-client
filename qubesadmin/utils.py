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

'''Various utility functions.'''
import os

import pkg_resources

import qubesadmin.exc


def parse_size(size):
    '''Parse human readable size into bytes.'''
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


def mbytes_to_kmg(size):
    '''Convert mbytes to human readable format.'''
    if size > 1024:
        return "%d GiB" % (size / 1024)
    return "%d MiB" % size


def kbytes_to_kmg(size):
    '''Convert kbytes to human readable format.'''
    if size > 1024:
        return mbytes_to_kmg(size / 1024)
    return "%d KiB" % size


def bytes_to_kmg(size):
    '''Convert bytes to human readable format.'''
    if size > 1024:
        return kbytes_to_kmg(size / 1024)
    return "%d B" % size


def size_to_human(size):
    """Humane readable size, with 1/10 precision"""
    if size < 1024:
        return str(size)
    elif size < 1024 * 1024:
        return str(round(size / 1024.0, 1)) + ' KiB'
    elif size < 1024 * 1024 * 1024:
        return str(round(size / (1024.0 * 1024), 1)) + ' MiB'
    return str(round(size / (1024.0 * 1024 * 1024), 1)) + ' GiB'


def get_entry_point_one(group, name):
    '''Get a single entry point of given type,
    raise TypeError when there are multiple.
    '''
    epoints = tuple(pkg_resources.iter_entry_points(group, name))
    if not epoints:
        raise KeyError(name)
    elif len(epoints) > 1:
        raise TypeError(
            'more than 1 implementation of {!r} found: {}'.format(name,
                ', '.join('{}.{}'.format(ep.module_name, '.'.join(ep.attrs))
                    for ep in epoints)))
    return epoints[0].load()

UPDATES_DEFAULT_VM_DISABLE_FLAG = \
    '/var/lib/qubes/updates/vm-default-disable-updates'

def updates_vms_status(qvm_collection):
    '''Check whether all VMs have the same check-updates value;
    if yes, return it; otherwise, return None
    '''
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
