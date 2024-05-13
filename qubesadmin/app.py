# -*- encoding: utf-8 -*-
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


"""
Main Qubes() class and related classes.
"""
import grp
import os
import shlex
import socket
import shutil
import subprocess
import sys

import logging

import qubesadmin.base
import qubesadmin.exc
import qubesadmin.label
import qubesadmin.storage
import qubesadmin.utils
import qubesadmin.vm
import qubesadmin.config
import qubesadmin.devices

try:
    import qubesdb
    has_qubesdb = True
except ImportError:
    has_qubesdb = False


class VMCollection(object):
    """Collection of VMs objects"""

    def __init__(self, app):
        self.app = app
        self._vm_list = None
        self._vm_objects = {}

    def clear_cache(self, invalidate_name=None):
        """Clear cached list of VMs
        If *invalidate_name* is given, remove that object from cache
        explicitly too.
        """
        self._vm_list = None
        if invalidate_name:
            self._vm_objects.pop(invalidate_name, None)

    def refresh_cache(self, force=False):
        """Refresh cached list of VMs"""
        if not force and self._vm_list is not None:
            return
        vm_list_data = self.app.qubesd_call(
            'dom0',
            'admin.vm.List'
        )
        new_vm_list = {}
        # FIXME: this will probably change
        for vm_data in vm_list_data.splitlines():
            vm_name, props = vm_data.decode('ascii').split(' ', 1)
            vm_name = str(vm_name)
            props = props.split(' ')
            new_vm_list[vm_name] = dict(
                [vm_prop.split('=', 1) for vm_prop in props])
            # if cache not enabled, drop power state
            if not self.app.cache_enabled:
                try:
                    del new_vm_list[vm_name]['state']
                except KeyError:
                    pass

        self._vm_list = new_vm_list
        for name, vm in list(self._vm_objects.items()):
            if vm.name not in self._vm_list:
                # VM no longer exists
                del self._vm_objects[name]
            elif vm.klass != self._vm_list[vm.name]['class']:
                # VM class have changed
                del self._vm_objects[name]
            # TODO: some generation ID, to detect VM re-creation
            elif name != vm.name:
                # renamed
                self._vm_objects[vm.name] = vm
                del self._vm_objects[name]

    def __getitem__(self, item):
        if isinstance(item, qubesadmin.vm.QubesVM):
            item = item.name
        if not self.app.blind_mode and item not in self:
            raise KeyError(item)
        return self.get_blind(item)

    def get_blind(self, item):
        """
        Get a vm without downloading the list
        and checking if exists
        """
        if item not in self._vm_objects:
            cls = qubesadmin.vm.QubesVM
            # provide class name to constructor, if already cached (which can be
            # done by 'item not in self' check above, unless blind_mode is
            # enabled
            klass = None
            power_state = None
            if self._vm_list and item in self._vm_list:
                klass = self._vm_list[item]['class']
                power_state = self._vm_list[item].get('state')
            self._vm_objects[item] = cls(self.app, item, klass=klass,
                                         power_state=power_state)
        return self._vm_objects[item]

    def get(self, item, default=None):
        """
        Get a VM object, or return *default* if it can't be found.
        """
        try:
            return self[item]
        except KeyError:
            return default

    def __contains__(self, item):
        if isinstance(item, qubesadmin.vm.QubesVM):
            item = item.name
        self.refresh_cache()
        return item in self._vm_list

    def __delitem__(self, key):
        self.app.qubesd_call(key, 'admin.vm.Remove')
        self.clear_cache()

    def __iter__(self):
        self.refresh_cache()
        for vm in sorted(self._vm_list):
            yield self[vm]

    def keys(self):
        """Get list of VM names."""
        self.refresh_cache()
        return self._vm_list.keys()

    def values(self):
        """Get list of VM objects."""
        self.refresh_cache()
        return [self[name] for name in self._vm_list]


class QubesBase(qubesadmin.base.PropertyHolder):
    """Main Qubes application.

    This is a base abstract class, don't use it directly. Use specialized
    class in py:class:`qubesadmin.Qubes` instead, which points at
    :py:class:`QubesLocal` or :py:class:`QubesRemote`.
    """

    #: domains (VMs) collection
    domains = None
    #: labels collection
    labels = None
    #: storage pools
    pools = None
    #: type of qubesd connection: either 'socket' or 'qrexec'
    qubesd_connection_type = None
    #: logger
    log = None
    #: do not check for object (VM, label etc) existence before really needed
    blind_mode = False
    #: cache retrieved properties values
    cache_enabled = False

    def __init__(self):
        super().__init__(self, 'admin.property.', 'dom0')
        self.domains = VMCollection(self)
        self.labels = qubesadmin.base.WrapperObjectsCollection(
            self, 'admin.label.List', qubesadmin.label.Label)
        self.pools = qubesadmin.base.WrapperObjectsCollection(
            self, 'admin.pool.List', qubesadmin.storage.Pool)
        #: cache for available storage pool drivers and options to create them
        self._pool_drivers = None
        self.log = logging.getLogger('app')
        self._local_name = None

    def list_vmclass(self):
        """Call Qubesd in order to obtain the vm classes list"""
        vmclass = self.qubesd_call('dom0', 'admin.vmclass.List') \
            .decode().splitlines()
        return sorted(vmclass)

    def list_deviceclass(self):
        """Call Qubesd in order to obtain the device classes list"""
        deviceclasses = self.qubesd_call('dom0', 'admin.deviceclass.List') \
            .decode().splitlines()
        return sorted(deviceclasses)

    def _refresh_pool_drivers(self):
        """
        Refresh cached storage pool drivers and their parameters.

        :return: None
        """
        if self._pool_drivers is None:
            pool_drivers_data = self.qubesd_call(
                'dom0', 'admin.pool.ListDrivers', None, None)
            assert pool_drivers_data.endswith(b'\n')
            pool_drivers = {}
            for driver_line in pool_drivers_data.decode('ascii').splitlines():
                if not driver_line:
                    continue
                driver_name, driver_options = driver_line.split(' ', 1)
                pool_drivers[driver_name] = driver_options.split(' ')
            self._pool_drivers = pool_drivers

    @property
    def pool_drivers(self):
        """ Available storage pool drivers """
        self._refresh_pool_drivers()
        return self._pool_drivers.keys()

    def pool_driver_parameters(self, driver):
        """ Parameters to initialize storage pool using given driver """
        self._refresh_pool_drivers()
        return self._pool_drivers[driver]

    def add_pool(self, name, driver, **kwargs):
        """ Add a storage pool to config

        :param name: name of storage pool to create
        :param driver: driver to use, see :py:meth:`pool_drivers` for
            available drivers
        :param kwargs: configuration parameters for storage pool,
            see :py:meth:`pool_driver_parameters` for a list
        """
        # sort parameters only to ease testing, not required by API
        payload = 'name={}\n'.format(name) + \
                  ''.join('{}={}\n'.format(key, value)
                          for key, value in sorted(kwargs.items()))
        self.qubesd_call('dom0', 'admin.pool.Add', driver,
                         payload.encode('utf-8'))

    def remove_pool(self, name):
        """ Remove a storage pool """
        self.qubesd_call('dom0', 'admin.pool.Remove', name, None)

    @property
    def local_name(self):
        """ Get localhost name """
        if not self._local_name:
            local_name = None
            if has_qubesdb:
                try:
                    local_qdb = qubesdb.QubesDB()
                    local_name_b = local_qdb.read('/name')
                    if local_name_b:
                        local_name = local_name_b.decode()
                except qubesdb.Error:
                    pass
            if local_name is None:
                local_name = os.uname()[1]
            self._local_name = local_name

        return self._local_name

    def get_label(self, label):
        """Get label as identified by index or name

        :throws QubesLabelNotFoundError: when label is not found
        """

        # first search for name, verbatim
        try:
            return self.labels[label]
        except KeyError:
            pass

        # then search for index
        if isinstance(label, int) or label.isdigit():
            for i in self.labels.values():
                if i.index == int(label):
                    return i
        raise qubesadmin.exc.QubesLabelNotFoundError(label)

    @staticmethod
    def get_vm_class(clsname):
        """Find the class for a domain.

        Compatibility function, client tools use str to identify domain classes.

        :param str clsname: name of the class
        :return str: class
        """

        return clsname

    def add_new_vm(self, cls, name, label, template=None, pool=None,
                   pools=None):
        """Create new Virtual Machine

        Example usage with custom storage pools:

        >>> app = qubesadmin.Qubes()
        >>> pools = {'private': 'external'}
        >>> vm = app.add_new_vm('AppVM', 'my-new-vm', 'red',
        >>>    'my-template', pools=pools)
        >>> vm.netvm = app.domains['sys-whonix']

        :param str cls: name of VM class (`AppVM`, `TemplateVM` etc)
        :param str name: name of VM
        :param str label: label color for new VM
        :param str template: template to use (if apply for given VM class),
            can be also VM object; use None for default value
        :param str pool: storage pool to use instead of default one
        :param dict pools: storage pool for specific volumes

        :return new VM object
        """

        if not isinstance(cls, str):
            cls = cls.__name__

        if template is qubesadmin.DEFAULT:
            template = None
        elif template is not None:
            template = str(template)

        if pool and pools:
            raise ValueError('only one of pool= and pools= can be used')

        method_prefix = 'admin.vm.Create.'
        payload = 'name={} label={}'.format(name, label)
        if pool:
            payload += ' pool={}'.format(str(pool))
            method_prefix = 'admin.vm.CreateInPool.'
        if pools:
            payload += ''.join(' pool:{}={}'.format(vol, str(pool))
                               for vol, pool in sorted(pools.items()))
            method_prefix = 'admin.vm.CreateInPool.'

        self.qubesd_call('dom0', method_prefix + cls, template,
                         payload.encode('utf-8'))

        self.domains.clear_cache()
        return self.domains[name]

    def clone_vm(self, src_vm, new_name, new_cls=None, pool=None, pools=None,
                 ignore_errors=False, ignore_volumes=None,
                 ignore_devices=False):
        # pylint: disable=too-many-statements
        """Clone Virtual Machine

        Example usage with custom storage pools:

        >>> app = qubesadmin.Qubes()
        >>> pools = {'private': 'external'}
        >>> src_vm = app.domains['personal']
        >>> vm = app.clone_vm(src_vm, 'my-new-vm', pools=pools)
        >>> vm.label = app.labels['green']

        :param QubesVM or str src_vm: source VM
        :param str new_name: name of new VM
        :param str new_cls: name of VM class (`AppVM`, `TemplateVM` etc) - use
            None to copy it from *src_vm*
        :param str pool: storage pool to use instead of default one
        :param dict pools: storage pool for specific volumes
        :param bool ignore_errors: should errors on meta-data setting be only
            logged, or abort the whole operation?
        :param list ignore_volumes: do not clone volumes on this list,
            like 'private' or 'root'
        :param bool ignore_devices: if True, do not copy device assignments

        :return new VM object
        """

        if pool and pools:
            raise ValueError('only one of pool= and pools= can be used')

        if isinstance(src_vm, str):
            src_vm = self.domains[src_vm]

        if new_cls is None:
            new_cls = src_vm.klass

        template = getattr(src_vm, 'template', None)
        if template is not None:
            template = str(template)

        label = src_vm.label

        if pool is None and pools is None:
            # use the same pools as the source - check if non default is used
            for volume in sorted(src_vm.volumes.values()):
                if volume.snap_on_start or not volume.rw:
                    # also see qubes.vm.qubesvm._patch_pool_config()
                    continue
                if ignore_volumes and volume.name in ignore_volumes:
                    continue
                default_pool = getattr(self.app, 'default_pool_' + volume.name,
                                       volume.pool)
                if default_pool != volume.pool:
                    if pools is None:
                        pools = {}
                    pools[volume.name] = volume.pool

        method_prefix = 'admin.vm.Create.'
        payload = 'name={} label={}'.format(new_name, label)
        if pool:
            payload += ' pool={}'.format(str(pool))
            method_prefix = 'admin.vm.CreateInPool.'
        if pools:
            payload += ''.join(' pool:{}={}'.format(vol, str(pool))
                               for vol, pool in sorted(pools.items()))
            method_prefix = 'admin.vm.CreateInPool.'

        self.qubesd_call('dom0', method_prefix + new_cls, template,
                         payload.encode('utf-8'))

        self.domains.clear_cache()
        dst_vm = self.domains[new_name]
        try:
            assert isinstance(dst_vm, qubesadmin.vm.QubesVM)
            for prop in src_vm.property_list():
                # handled by admin.vm.Create call
                if prop in ('name', 'qid', 'template', 'label', 'uuid',
                            'installed_by_rpm'):
                    continue
                if src_vm.property_is_default(prop):
                    continue
                try:
                    setattr(dst_vm, prop, getattr(src_vm, prop))
                except AttributeError:
                    pass
                except qubesadmin.exc.QubesException as e:
                    dst_vm.log.error(
                        'Failed to set {!s} property: {!s}'.format(prop, e))
                    if not ignore_errors:
                        raise

            for tag in src_vm.tags:
                if tag.startswith('created-by-'):
                    continue
                try:
                    dst_vm.tags.add(tag)
                except qubesadmin.exc.QubesException as e:
                    dst_vm.log.error(
                        'Failed to add {!s} tag: {!s}'.format(tag, e))
                    if not ignore_errors:
                        raise

            for feature, value in src_vm.features.items():
                try:
                    dst_vm.features[feature] = value
                except qubesadmin.exc.QubesException as e:
                    dst_vm.log.error(
                        'Failed to set {!s} feature: {!s}'.format(feature, e))
                    if not ignore_errors:
                        raise

            try:
                dst_vm.firewall.save_rules(src_vm.firewall.rules)
            except qubesadmin.exc.QubesException as e:
                self.log.error('Failed to set firewall: %s', e)
                if not ignore_errors:
                    raise

            try:
                # FIXME: convert to qrexec calls to dom0/GUI VM
                appmenus_cmd = \
                    ['qvm-appmenus', '--init', '--update',
                     '--source', src_vm.name, dst_vm.name]
                runas = []
                if os.getuid() == 0:
                    try:
                        user = self.domains[self.local_name].default_user
                    except (KeyError, qubesadmin.exc.QubesException):
                        try:
                            user = grp.getgrnam('qubes').gr_mem[0]
                        except KeyError:
                            user = None
                    if not user:
                        raise qubesadmin.exc.QubesException(
                            'Failed to find local user account')
                    runas = ['runuser', '-u', user, '--']

                subprocess.check_output(runas + appmenus_cmd,
                    stderr=subprocess.STDOUT)
            except OSError as e:
                # this file needs to be python 2.7 compatible,
                # so no FileNotFoundError
                self.log.error('Failed to clone appmenus, qvm-appmenus missing')
                if not ignore_errors:
                    raise qubesadmin.exc.QubesException(
                        'Failed to clone appmenus') from e
            except subprocess.CalledProcessError as e:
                self.log.error('Failed to clone appmenus: %s',
                               e.output.decode())
                if not ignore_errors:
                    raise qubesadmin.exc.QubesException(
                        'Failed to clone appmenus') from e
            except qubesadmin.exc.QubesException as e:
                self.log.error('Failed to clone appmenus: %s', e)
                if not ignore_errors:
                    raise qubesadmin.exc.QubesException(
                        'Failed to clone appmenus') from e

        except qubesadmin.exc.QubesException:
            if not ignore_errors:
                del self.domains[dst_vm.name]
                raise

        try:
            for dst_volume in sorted(dst_vm.volumes.values()):
                if not dst_volume.save_on_stop:
                    # clone only persistent volumes
                    continue
                if ignore_volumes and dst_volume.name in ignore_volumes:
                    continue
                src_volume = src_vm.volumes[dst_volume.name]
                dst_vm.log.info('Cloning {} volume'.format(dst_volume.name))
                dst_volume.clone(src_volume)

        except qubesadmin.exc.QubesException:
            del self.domains[dst_vm.name]
            raise

        if not ignore_devices:
            try:
                for devclass in src_vm.devices:
                    for assignment in src_vm.devices[devclass].assignments(
                            persistent=True):
                        new_assignment = qubesadmin.devices.DeviceAssignment(
                            backend_domain=assignment.backend_domain,
                            ident=assignment.ident,
                            options=assignment.options,
                            persistent=assignment.persistent)
                        dst_vm.devices[devclass].attach(new_assignment)
            except qubesadmin.exc.QubesException:
                if not ignore_errors:
                    del self.domains[dst_vm.name]
                    raise

        return dst_vm

    def qubesd_call(self, dest, method, arg=None, payload=None,
                    payload_stream=None):
        """
        Execute Admin API method.

        If `payload` and `payload_stream` are both specified, they will be sent
        in that order.

        :param dest: Destination VM name
        :param method: Full API method name ('admin...')
        :param arg: Method argument (if any)
        :param payload: Payload send to the method
        :param payload_stream: file-like object to read payload from
        :return: Data returned by qubesd (string)

        .. warning:: *payload_stream* will get closed by this function
        """
        raise NotImplementedError(
            'qubesd_call not implemented in QubesBase class; use specialized '
            'class: qubesadmin.Qubes()')

    def run_service(self, dest, service, filter_esc=False, user=None,
                    localcmd=None, wait=True, autostart=True, **kwargs):
        """Run qrexec service in a given destination

        *kwargs* are passed verbatim to :py:meth:`subprocess.Popen`.

        :param str dest: Destination - may be a VM name or empty
            string for default (for a given service)
        :param str service: service name
        :param bool filter_esc: filter escape sequences to protect terminal \
            emulator
        :param str user: username to run service as
        :param str localcmd: Command to connect stdin/stdout to
        :param bool wait: Wait service run
        :param bool autostart: Automatically start the target VM
        :rtype: subprocess.Popen
        """
        raise NotImplementedError(
            'run_service not implemented in QubesBase class; use specialized '
            'class: qubesadmin.Qubes()')

    @staticmethod
    def _call_with_stream(command, payload, payload_stream):
        """Helper method to pass data to qubesd. Calls a command with
        payload and payload_stream as input.

        :param command: command to run
        :param payload: Initial payload, or None
        :param payload_stream: File-like object with the rest of data
        :return: (process, stdout, stderr)
        """

        with subprocess.Popen(
                command,
                stdin=(subprocess.PIPE if payload else payload_stream),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE) as proc:
            if payload:
                # It's not strictly correct to write data to stdin in this way,
                # because the process can get blocked on stdout or stderr pipe.
                # However, in practice the output should be always smaller
                # than 4K.
                proc.stdin.write(payload)
                try:
                    shutil.copyfileobj(payload_stream, proc.stdin)
                except BrokenPipeError:
                    # We might receive an error from qubesd before we sent
                    # everything (for instance, because we are sending too much
                    # data).
                    pass
            payload_stream.close()
            stdout, stderr = proc.communicate()
        return proc, stdout, stderr

    def _invalidate_cache(self, subject, event, name, **kwargs):
        """Invalidate cached value of a property.

        This method is designed to be hooked as an event handler for:
        - property-set:*
        - property-del:*

        This is done in :py:class:`qubesadmin.events.EventsDispatcher` class
        directly, before calling other handlers.

        It handles both VM and global properties.
        Note: even if the new value is given in the event arguments, it is
        ignored because it comes without type information.

        :param subject: either VM object or None
        :param event: name of the event
        :param name: name of the property
        :param kwargs: other arguments
        :return: none
        """  # pylint: disable=unused-argument
        if subject is None:
            subject = self

        try:
            # pylint: disable=protected-access
            del subject._properties_cache[name]
        except KeyError:
            pass

    def _update_power_state_cache(self, subject, event, **kwargs):
        """ Update cached VM power state.

        This method is designed to be hooked as an event handler for:
        - domain-pre-start
        - domain-start
        - domain-shutdown
        - domain-paused
        - domain-unpaused
        - domain-start-failed

        This is done in :py:class:`qubesadmin.events.EventsDispatcher` class
        directly, before calling other handlers.

        :param subject: a VM object
        :param event: name of the event
        :param kwargs: other arguments
        :return:
        """  # pylint: disable=unused-argument

        if not self.app.cache_enabled:
            return

        if event == 'domain-pre-start':
            power_state = 'Transient'
        elif event == 'domain-start':
            power_state = 'Running'
        elif event == 'domain-shutdown':
            power_state = 'Halted'
        elif event == 'domain-paused':
            power_state = 'Paused'
        elif event == 'domain-unpaused':
            power_state = 'Running'
        elif event == 'domain-start-failed':
            power_state = 'Halted'
        else:
            # unknown power state change, drop cached power state
            power_state = None

        # pylint: disable=protected-access
        subject._power_state_cache = power_state

    def _invalidate_cache_all(self):
        """ Invalidate all cached data


        This method is designed to be hooked as an event handler
        for 'connection-established' handler. This is done in
        :py:class:`qubesadmin.events.EventsDispatcher` class
        directly, before calling other handlers.

        There is no guarantee about events delivery before this point,
        so anything cached before needs to be discarded.

        :return: none
        """
        # pylint: disable=protected-access
        self.domains.clear_cache()
        for vm in self.domains._vm_objects.values():
            vm._power_state_cache = None
            vm._properties_cache = {}
        self._properties_cache = {}


class QubesLocal(QubesBase):
    """Application object communicating through local socket.

    Used when running in dom0.
    """

    qubesd_connection_type = 'socket'

    def qubesd_call(self, dest, method, arg=None, payload=None,
                    payload_stream=None):
        """
        Execute Admin API method.

        If `payload` and `payload_stream` are both specified, they will be sent
        in that order.

        :param dest: Destination VM name
        :param method: Full API method name ('admin...')
        :param arg: Method argument (if any)
        :param payload: Payload send to the method
        :param payload_stream: file-like object to read payload from
        :return: Data returned by qubesd (string)

        .. warning:: *payload_stream* will get closed by this function
        """
        if payload_stream:
            # payload_stream can be used for large amount of data,
            # so optimize for throughput, not latency: spawn actual qrexec
            # service implementation, which may use some optimization there (
            # see admin.vm.volume.Import - actual data handling is done with dd)
            method_path = os.path.join(
                qubesadmin.config.QREXEC_SERVICES_DIR, method)
            if not os.path.exists(method_path):
                raise qubesadmin.exc.QubesDaemonCommunicationError(
                    '{} not found'.format(method_path))
            command = ['env', 'QREXEC_REMOTE_DOMAIN=dom0',
                       'QREXEC_REQUESTED_TARGET=' + dest, method_path, arg]
            if os.getuid() != 0:
                command.insert(0, 'sudo')
            (_, stdout, _) = self._call_with_stream(
                command, payload, payload_stream)
            return self._parse_qubesd_response(stdout)

        try:
            client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client_socket.connect(qubesadmin.config.QUBESD_SOCKET)
        except (IOError, OSError) as e:
            raise qubesadmin.exc.QubesDaemonCommunicationError(
                'Failed to connect to qubesd service: %s', str(e))

        call_header = '{}+{} dom0 name {}\0'.format(method, arg or '', dest)
        client_socket.sendall(call_header.encode('ascii'))
        if payload is not None:
            client_socket.sendall(payload)

        client_socket.shutdown(socket.SHUT_WR)

        return_data = client_socket.makefile('rb').read()
        client_socket.close()
        return self._parse_qubesd_response(return_data)

    def run_service(self, dest, service, filter_esc=False, user=None,
                    localcmd=None, wait=True, autostart=True, **kwargs):
        """Run qrexec service in a given destination

        :param str dest: Destination - may be a VM name or empty
            string for default (for a given service)
        :param str service: service name
        :param bool filter_esc: filter escape sequences to protect terminal \
            emulator
        :param str user: username to run service as
        :param str localcmd: Command to connect stdin/stdout to
        :param bool wait: wait for remote process to finish
        :rtype: subprocess.Popen
        """

        if not dest:
            raise ValueError('Empty destination name allowed only from a VM')
        if not wait and localcmd:
            raise ValueError('wait=False incompatible with localcmd')
        if autostart:
            try:
                self.qubesd_call(dest, 'admin.vm.Start')
            except qubesadmin.exc.QubesVMNotHaltedError:
                pass
        elif not self.domains.get_blind(dest).is_running():
            raise qubesadmin.exc.QubesVMNotRunningError(
                '%s is not running', dest)
        # pylint: disable=consider-using-with
        if dest == 'dom0':
            # can't make real dom0->dom0 call
            if filter_esc:
                raise NotImplementedError(
                    'filter_esc=True not implemented in dom0->dom0 calls')
            if localcmd:
                raise NotImplementedError(
                    'localcmd not implemented in dom0->dom0 calls')
            if not wait:
                raise NotImplementedError(
                    'wait=False not implemented in dom0->dom0 calls')
            if user is None:
                user = grp.getgrnam('qubes').gr_mem[0]

            kwargs.setdefault('stdin', subprocess.PIPE)
            kwargs.setdefault('stdout', subprocess.PIPE)
            kwargs.setdefault('stderr', subprocess.PIPE)
            # Set default locale to C in order to prevent error msg
            # in subprocess call related to falling back to C locale
            env = os.environ.copy()
            env['LC_ALL'] = 'C'
            cmd = '/etc/qubes-rpc/' + service
            arg = ''
            if not os.path.exists(cmd) and '+' in service:
                cmd, arg = cmd.split('+', 1)
            p = subprocess.Popen(
                ['sudo', '-u', user, cmd, arg],
                **kwargs,
                env=env,
            )
            return p
        qrexec_opts = ['-d', dest]
        if filter_esc:
            qrexec_opts.extend(['-t'])
        if filter_esc or os.isatty(sys.stderr.fileno()):
            qrexec_opts.extend(['-T'])
        if localcmd:
            qrexec_opts.extend(['-l', localcmd])
        if user is None:
            user = 'DEFAULT'
        if not wait:
            qrexec_opts.extend(['-e'])
        if 'connect_timeout' in kwargs:
            qrexec_opts.extend(['-w', str(kwargs.pop('connect_timeout'))])
        kwargs.setdefault('stdin', subprocess.PIPE)
        kwargs.setdefault('stdout', subprocess.PIPE)
        kwargs.setdefault('stderr', subprocess.PIPE)
        proc = subprocess.Popen(
            [qubesadmin.config.QREXEC_CLIENT] + qrexec_opts + [
                '{}:QUBESRPC {} dom0'.format(user, service)], **kwargs)
        return proc


class QubesRemote(QubesBase):
    """Application object communicating through qrexec services.

    Used when running in VM.
    """

    qubesd_connection_type = 'qrexec'

    def qubesd_call(self, dest, method, arg=None, payload=None,
                    payload_stream=None):
        """
        Execute Admin API method.

        If `payload` and `payload_stream` are both specified, they will be sent
        in that order.

        :param dest: Destination VM name
        :param method: Full API method name ('admin...')
        :param arg: Method argument (if any)
        :param payload: Payload send to the method
        :param payload_stream: file-like object to read payload from
        :return: Data returned by qubesd (string)

        .. warning:: *payload_stream* will get closed by this function
        """
        service_name = method
        if arg is not None:
            service_name += '+' + arg
        command = [qubesadmin.config.QREXEC_CLIENT_VM,
                   dest, service_name]
        if payload_stream:
            (p, stdout, stderr) = self._call_with_stream(
                command, payload, payload_stream)
        else:
            with subprocess.Popen(command,
                                  stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE) as p:
                (stdout, stderr) = p.communicate(payload)
        if p.returncode != 0:
            raise qubesadmin.exc.QubesDaemonAccessError(
                'Service call error: %s', stderr.decode())

        return self._parse_qubesd_response(stdout)

    def run_service(self, dest, service, filter_esc=False, user=None,
                    localcmd=None, wait=True, autostart=True, **kwargs):
        """Run qrexec service in a given destination

        :param str dest: Destination - may be a VM name or empty
            string for default (for a given service)
        :param str service: service name
        :param bool filter_esc: filter escape sequences to protect terminal \
            emulator
        :param str user: username to run service as
        :param str localcmd: Command to connect stdin/stdout to
        :param bool wait: wait for process to finish
        :rtype: subprocess.Popen
        """
        if not autostart and not dest:
            raise ValueError(
                'autostart=False makes sense only with a defined target')
        if user:
            raise ValueError(
                'non-default user not possible for calls from VM')
        if not wait and localcmd:
            raise ValueError('wait=False incompatible with localcmd')
        qrexec_opts = []
        if filter_esc:
            qrexec_opts.extend(['-t'])
        if filter_esc or (
                os.isatty(sys.stderr.fileno()) and 'stderr' not in kwargs):
            qrexec_opts.extend(['-T'])
        if not autostart and not self.domains.get_blind(dest).is_running():
            raise qubesadmin.exc.QubesVMNotRunningError(
                '%s is not running', dest)
        if not wait:
            # qrexec-client-vm can only request service calls, which are
            # started using MSG_EXEC_CMDLINE qrexec protocol message; this
            # message means "start the process, pipe its stdin/out/err,
            # and when it terminates, send exit code back".
            # According to the protocol qrexec-client-vm needs to wait for
            # MSG_DATA_EXIT_CODE, so implementing wait=False would require
            # some protocol change (or protocol violation).
            raise NotImplementedError(
                'wait=False not implemented for calls from VM')
        kwargs.setdefault('stdin', subprocess.PIPE)
        kwargs.setdefault('stdout', subprocess.PIPE)
        kwargs.setdefault('stderr', subprocess.PIPE)
        # pylint: disable=consider-using-with
        proc = subprocess.Popen(
            [qubesadmin.config.QREXEC_CLIENT_VM] +
            qrexec_opts +
            [dest or '', service] +
            (shlex.split(localcmd) if localcmd else []),
            **kwargs)
        return proc
