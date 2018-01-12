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

'''Qubes VM objects.'''

import logging

import subprocess

import qubesadmin.base
import qubesadmin.exc
import qubesadmin.storage
import qubesadmin.features
import qubesadmin.devices
import qubesadmin.firewall
import qubesadmin.tags


class QubesVM(qubesadmin.base.PropertyHolder):
    '''Qubes domain.'''

    log = None

    tags = None

    features = None

    devices = None

    firewall = None

    def __init__(self, app, name, klass=None):
        super(QubesVM, self).__init__(app, 'admin.vm.property.', name)
        self._volumes = None
        self._klass = klass
        self.log = logging.getLogger(name)
        self.tags = qubesadmin.tags.Tags(self)
        self.features = qubesadmin.features.Features(self)
        self.devices = qubesadmin.devices.DeviceManager(self)
        self.firewall = qubesadmin.firewall.Firewall(self)

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
        self._volumes = None
        self.app.domains.clear_cache()

    def __str__(self):
        return self._method_dest

    def __lt__(self, other):
        if isinstance(other, QubesVM):
            return self.name < other.name
        return NotImplemented

    def __eq__(self, other):
        if isinstance(other, QubesVM):
            return self.name == other.name
        elif isinstance(other, str):
            return self.name == other
        return NotImplemented

    def __hash__(self):
        return hash(self.name)

    def start(self):
        '''
        Start domain.

        :return:
        '''
        self.qubesd_call(self._method_dest, 'admin.vm.Start')

    def shutdown(self, force=False):
        '''
        Shutdown domain.

        :return:
        '''
        # TODO: force parameter
        # TODO: wait parameter (using event?)
        if force:
            raise NotImplementedError
        self.qubesd_call(self._method_dest, 'admin.vm.Shutdown')

    def kill(self):
        '''
        Kill domain (forcefuly shutdown).

        :return:
        '''
        self.qubesd_call(self._method_dest, 'admin.vm.Kill')

    def pause(self):
        '''
        Pause domain.

        Pause its execution without any prior notification.

        :return:
        '''
        self.qubesd_call(self._method_dest, 'admin.vm.Pause')

    def unpause(self):
        '''
        Unpause domain.

        Opposite to :py:meth:`pause`.

        :return:
        '''
        self.qubesd_call(self._method_dest, 'admin.vm.Unpause')

    def get_power_state(self):
        '''Return power state description string.

        Return value may be one of those:

        =============== ========================================================
        return value    meaning
        =============== ========================================================
        ``'Halted'``    Machine is not active.
        ``'Transient'`` Machine is running, but does not have :program:`guid`
                        or :program:`qrexec` available.
        ``'Running'``   Machine is ready and running.
        ``'Paused'``    Machine is paused.
        ``'Suspended'`` Machine is S3-suspended.
        ``'Halting'``   Machine is in process of shutting down (OS shutdown).
        ``'Dying'``     Machine is in process of shutting down (cleanup).
        ``'Crashed'``   Machine crashed and is unusable.
        ``'NA'``        Machine is in unknown state.
        =============== ========================================================

        .. seealso::

            http://wiki.libvirt.org/page/VM_lifecycle
                Description of VM life cycle from the point of view of libvirt.

            https://libvirt.org/html/libvirt-libvirt-domain.html#virDomainState
                Libvirt's enum describing precise state of a domain.

        '''

        try:
            vm_list_info = [line
                for line in self.qubesd_call(
                    self._method_dest, 'admin.vm.List', None, None
                ).decode('ascii').split('\n')
                if line.startswith(self._method_dest+' ')]
        except qubesadmin.exc.QubesDaemonNoResponseError:
            return 'NA'
        assert len(vm_list_info) == 1
        #  name class=... state=... other=...
        # NOTE: when querying dom0, we get whole list
        vm_state = vm_list_info[0].strip().partition('state=')[2].split(' ')[0]
        return vm_state


    def is_halted(self):
        ''' Check whether this domain's state is 'Halted'
            :returns: :py:obj:`True` if this domain is halted, \
                :py:obj:`False` otherwise.
            :rtype: bool
        '''
        return self.get_power_state() == 'Halted'

    def is_paused(self):
        '''Check whether this domain is paused.

        :returns: :py:obj:`True` if this domain is paused, \
            :py:obj:`False` otherwise.
        :rtype: bool
        '''

        return self.get_power_state() == 'Paused'

    def is_running(self):
        '''Check whether this domain is running.

        :returns: :py:obj:`True` if this domain is started, \
            :py:obj:`False` otherwise.
        :rtype: bool
        '''

        return self.get_power_state() not in ('Halted', 'NA')

    def is_networked(self):
        '''Check whether this VM can reach network (firewall notwithstanding).

        :returns: :py:obj:`True` if is machine can reach network, \
            :py:obj:`False` otherwise.
        :rtype: bool
        '''

        if self.provides_network:
            return True

        return self.netvm is not None

    @property
    def volumes(self):
        '''VM disk volumes'''
        if self._volumes is None:
            volumes_list = self.qubesd_call(
                self._method_dest, 'admin.vm.volume.List')
            self._volumes = {}
            for volname in volumes_list.decode('ascii').splitlines():
                if not volname:
                    continue
                self._volumes[volname] = qubesadmin.storage.Volume(self.app,
                    vm=self.name, vm_name=volname)
        return self._volumes

    def get_disk_utilization(self):
        '''Get total disk usage of the VM'''
        return sum(vol.usage for vol in self.volumes.values())

    def run_service(self, service, **kwargs):
        '''Run service on this VM

        :param str service: service name
        :rtype: subprocess.Popen
        '''
        return self.app.run_service(self._method_dest, service, **kwargs)

    def run_service_for_stdio(self, service, input=None, **kwargs):
        '''Run a service, pass an optional input and return (stdout, stderr).

        Raises an exception if return code != 0.

        *args* and *kwargs* are passed verbatim to :py:meth:`run_service`.

        .. warning::
            There are some combinations if stdio-related *kwargs*, which are
            not filtered for problems originating between the keyboard and the
            chair.
        '''  # pylint: disable=redefined-builtin
        p = self.run_service(service, **kwargs)

        # this one is actually a tuple, but there is no need to unpack it
        stdouterr = p.communicate(input=input)

        if p.returncode:
            exc = subprocess.CalledProcessError(p.returncode, service)
            # Python < 3.5 didn't have those
            exc.output, exc.stderr = stdouterr
            raise exc

        return stdouterr

    @staticmethod
    def prepare_input_for_vmshell(command, input=None):
        '''Prepare shell input for the given command and optional (real) input
        '''  # pylint: disable=redefined-builtin
        if input is None:
            input = b''
        return b''.join((command.rstrip('\n').encode('utf-8'),
            b'; exit\n', input))

    def run(self, command, input=None, **kwargs):
        '''Run a shell command inside the domain using qubes.VMShell qrexec.

        '''  # pylint: disable=redefined-builtin
        try:
            return self.run_service_for_stdio('qubes.VMShell',
                input=self.prepare_input_for_vmshell(command, input), **kwargs)
        except subprocess.CalledProcessError as e:
            e.cmd = command
            raise e

    @property
    def appvms(self):
        ''' Returns a generator containing all domains based on the current
            TemplateVM.

            Do not check vm type of self, core (including its extentions) have
            ultimate control what can be a template of what.
        '''
        for vm in self.app.domains:
            try:
                if vm.template == self:
                    yield vm
            except AttributeError:
                pass

    @property
    def connected_vms(self):
        ''' Return a generator containing all domains connected to the current
            NetVM.
        '''
        for vm in self.app.domains:
            try:
                if vm.netvm == self:
                    yield vm
            except AttributeError:
                pass

    @property
    def klass(self):
        ''' Qube class '''
        # use cached value if available
        if self._klass is None:
            # pylint: disable=no-member
            self._klass = super(QubesVM, self).klass
        return self._klass

class DispVMWrapper(QubesVM):
    '''Wrapper class for new DispVM, supporting only service call

    Note that when running in dom0, one need to manually kill the DispVM after
    service call ends.
    '''

    def run_service(self, service, **kwargs):
        if self.app.qubesd_connection_type == 'socket':
            # create dispvm at service call
            if self._method_dest.startswith('$dispvm'):
                if self._method_dest.startswith('$dispvm:'):
                    method_dest = self._method_dest[len('$dispvm:'):]
                else:
                    method_dest = 'dom0'
                dispvm = self.app.qubesd_call(method_dest,
                    'admin.vm.CreateDisposable')
                dispvm = dispvm.decode('ascii')
                self._method_dest = dispvm
                # Service call may wait for session start, give it more time
                # than default 5s
                kwargs['connect_timeout'] = self.qrexec_timeout
        return super(DispVMWrapper, self).run_service(service, **kwargs)

    def cleanup(self):
        '''Cleanup after DispVM usage'''
        # in 'remote' case nothing is needed, as DispVM is cleaned up
        # automatically
        if self.app.qubesd_connection_type == 'socket' and \
                not self._method_dest.startswith('$dispvm'):
            try:
                self.kill()
            except qubesadmin.exc.QubesVMNotRunningError:
                pass


class DispVM(QubesVM):
    '''Disposable VM'''

    @classmethod
    def from_appvm(cls, app, appvm):
        '''Returns a wrapper for calling service in a new DispVM based on given
        AppVM. If *appvm* is none, use default DispVM template'''

        if appvm:
            method_dest = '$dispvm:' + str(appvm)
        else:
            method_dest = '$dispvm'

        wrapper = DispVMWrapper(app, method_dest)
        return wrapper
