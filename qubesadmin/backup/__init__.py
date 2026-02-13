# -*- encoding: utf8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
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

'''Qubes backup'''
import collections
import io

from qubesadmin.vm import QubesVM


class BackupApp(object):
    '''Interface for backup collection'''
    # pylint: disable=too-few-public-methods
    def __init__(self, qubes_xml: str | None):
        '''Initialize BackupApp object and load qubes.xml into it'''
        self.store = qubes_xml
        self.domains = {}
        self.globals = {}
        self.load()

    def load(self) -> bool | None:
        '''Load qubes.xml'''
        raise NotImplementedError

class BackupVM(object):
    '''Interface for a single VM in the backup'''
    # pylint: disable=too-few-public-methods
    def __init__(self) -> None:
        '''Initialize empty BackupVM object'''
        #: VM class
        self.klass = 'AppVM'
        #: VM name
        self.name = None
        #: VM template
        self.template = None
        #: VM label
        self.label = None
        #: VM properties
        self.properties = {}
        #: VM features (key/value), aka services in core2
        self.features = {}
        #: VM tags
        self.tags = set()
        #: VM devices - dict with key=devtype, value=dict of devices (
        # key=ident, value=options)
        self.devices = collections.defaultdict(dict)
        #: VM path in the backup
        self.backup_path = None
        #: size of the VM
        self.size = 0

    @property
    def included_in_backup(self) -> bool:
        '''Report whether a VM is included in the backup'''
        return False

    def handle_firewall_xml(self, vm: QubesVM, stream: io.BytesIO) -> None:
        '''Import appropriate format of firewall.xml'''
        raise NotImplementedError

    def handle_notes_txt(self, vm: QubesVM, stream: io.BytesIO) -> None:
        '''Import qubes notes.txt'''
        raise NotImplementedError  # pragma: no cover
