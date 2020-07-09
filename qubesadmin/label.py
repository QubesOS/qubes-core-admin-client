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

import qubesadmin.exc


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
        self._index = None

    @property
    def color(self):
        '''color specification as in HTML (``#abcdef``)'''
        if self._color is None:
            try:
                qubesd_response = self.app.qubesd_call(
                    'dom0', 'admin.label.Get', self._name, None)
            except qubesadmin.exc.QubesDaemonNoResponseError:
                raise AttributeError
            self._color = qubesd_response.decode()
        return self._color

    @property
    def name(self):
        '''label's name like "red" or "green"'''
        return self._name

    @property
    def icon(self):
        '''freedesktop icon name, suitable for use in
        :py:meth:`PyQt4.QtGui.QIcon.fromTheme`'''
        return 'appvm-' + self.name

    @property
    def index(self):
        '''color specification as in HTML (``#abcdef``)'''
        if self._index is None:
            try:
                qubesd_response = self.app.qubesd_call(
                    'dom0', 'admin.label.Index', self._name, None)
            except qubesadmin.exc.QubesDaemonNoResponseError:
                raise AttributeError
            self._index = int(qubesd_response.decode())
        return self._index

    def __str__(self):
        return self._name

    def __eq__(self, other):
        if isinstance(other, Label):
            return self.name == other.name
        return NotImplemented
