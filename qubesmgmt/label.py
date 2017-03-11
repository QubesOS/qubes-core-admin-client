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

'''VM Labels'''

import qubesmgmt.exc

class Label(object):
    '''Label definition for virtual machines

    Label specifies colour of the padlock displayed next to VM's name.

    :param str color: colour specification as in HTML (``#abcdef``)
    :param str name: label's name like "red" or "green"
    '''

    def __init__(self, app, name):
        self.app = app
        self._name = name
        self._color = None

    @property
    def color(self):
        '''color specification as in HTML (``#abcdef``)'''
        if self._color is None:
            try:
                qubesd_response = self.app.qubesd_call(
                    'dom0', 'mgmt.label.Get', self._name, None)
            except qubesmgmt.exc.QubesDaemonNoResponseError:
                raise AttributeError
            self._color = qubesd_response.decode()
        return self._color

    @property
    def name(self):
        '''label's name like "red" or "green"'''
        return self._name

    def __str__(self):
        return self._name


class LabelsCollection(object):
    '''Collection of VMs objects'''
    def __init__(self, app):
        self.app = app
        self._label_list = None
        self._label_objects = {}

    def clear_cache(self):
        '''Clear cached list of labels'''
        self._label_list = None

    def refresh_cache(self, force=False):
        '''Refresh cached list of VMs'''
        if not force and self._label_list is not None:
            return
        label_list_data = self.app.qubesd_call('dom0', 'mgmt.label.List')
        label_list_data = label_list_data.decode('ascii')
        assert label_list_data[-1] == '\n'
        self._label_list = label_list_data[:-1].splitlines()

        for name, label in list(self._label_objects.items()):
            if label.name not in self._label_list:
                # Label no longer exists
                del self._label_objects[name]

    def __getitem__(self, item):
        if item not in self:
            raise KeyError(item)
        if item not in self._label_objects:
            self._label_objects[item] = Label(self.app, item)
        return self._label_objects[item]

    def __contains__(self, item):
        self.refresh_cache()
        return item in self._label_list

    def __iter__(self):
        self.refresh_cache()
        for vm in self._label_list:
            yield self[vm]

    def keys(self):
        '''Get list of label names.'''
        self.refresh_cache()
        return self._label_list.keys()
