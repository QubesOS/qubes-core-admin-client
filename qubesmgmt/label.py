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
