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
        '''Domain name'''
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

    def start(self):
        '''
        Start domain.

        :return:
        '''
        self.qubesd_call(self._method_dest, 'mgmt.vm.Start')

    def shutdown(self):
        '''
        Shutdown domain.

        :return:
        '''
        # TODO: force parameter
        # TODO: wait parameter (using event?)
        self.qubesd_call(self._method_dest, 'mgmt.vm.Shutdown')

    def kill(self):
        '''
        Kill domain (forcefuly shutdown).

        :return:
        '''
        self.qubesd_call(self._method_dest, 'mgmt.vm.Kill')

    def pause(self):
        '''
        Pause domain.

        Pause its execution without any prior notification.

        :return:
        '''
        self.qubesd_call(self._method_dest, 'mgmt.vm.Pause')

    def unpause(self):
        '''
        Unpause domain.

        Opposite to :py:meth:`pause`.

        :return:
        '''
        self.qubesd_call(self._method_dest, 'mgmt.vm.Unpause')

    def suspend(self):
        '''
        Suspend domain.

        Give domain a chance to prepare for suspend - for example suspend
        used PCI devices.

        :return:
        '''
        raise NotImplementedError
        #self.qubesd_call(self._method_dest, 'mgmt.vm.Suspend')

    def resume(self):
        '''
        Resume domain.

        Opposite to :py:meth:`suspend`.

        :return:
        '''
        raise NotImplementedError
        #self.qubesd_call(self._method_dest, 'mgmt.vm.Resume')
