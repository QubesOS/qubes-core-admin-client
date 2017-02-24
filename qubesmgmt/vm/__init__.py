# -*- encoding: utf8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2017 Marek Marczykowski-Górecki
#                               <marmarek@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <http://www.gnu.org/licenses/>.

import qubesmgmt.base


class QubesVM(qubesmgmt.base.PropertyHolder):
    def __init__(self, app, name, vm_class):
        self._class = vm_class
        super(QubesVM, self).__init__(app, 'mgmt.vm.property.', name)

    @property
    def name(self):
        return self._method_dest

    @name.setter
    def name(self, new_value):
        self.qubesd_call(
            self._method_dest,
            self._method_prefix + 'Set',
            'name',
            str(new_value).encode('utf-8'))
        self._method_dest = new_value
        self.app.domains.clear_cache()
