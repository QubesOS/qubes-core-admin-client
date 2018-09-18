# -*- encoding: utf8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2015-2016  Wojtek Porczyk <woju@invisiblethingslab.com>
# Copyright (C) 2016       Bahtiar `kalkin-` Gadimov <bahtiar@gadimov.de>
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

'''API for various types of devices.

Main concept is that some domain main
expose (potentially multiple) devices, which can be attached to other domains.
Devices can be of different classes (like 'pci', 'usb', etc). Each device
class is implemented by an extension.

Devices are identified by pair of (backend domain, `ident`), where `ident` is
:py:class:`str`.
'''

class DeviceAssignment(object):  # pylint: disable=too-few-public-methods
    ''' Maps a device to a frontend_domain. '''

    def __init__(self, backend_domain, ident, options=None,
            persistent=False, frontend_domain=None, devclass=None):
        self.backend_domain = backend_domain
        self.ident = ident
        self.devclass = devclass
        self.options = options or {}
        self.persistent = persistent
        self.frontend_domain = frontend_domain

    def __repr__(self):
        return "[%s]:%s" % (self.backend_domain, self.ident)

    def __hash__(self):
        return hash((self.backend_domain, self.ident))

    def __eq__(self, other):
        if not isinstance(self, other.__class__):
            return NotImplemented

        return self.backend_domain == other.backend_domain \
            and self.ident == other.ident

    def clone(self):
        '''Clone object instance'''
        return self.__class__(
            self.backend_domain,
            self.ident,
            self.options,
            self.persistent,
            self.frontend_domain,
            self.devclass,
        )

    @property
    def device(self):
        '''Get DeviceInfo object corresponding to this DeviceAssignment'''
        return self.backend_domain.devices[self.devclass][self.ident]


class DeviceInfo(object):
    ''' Holds all information about a device '''
    # pylint: disable=too-few-public-methods
    def __init__(self, backend_domain, devclass, ident, description=None,
                 **kwargs):
        #: domain providing this device
        self.backend_domain = backend_domain
        #: device class
        self.devclass = devclass
        #: device identifier (unique for given domain and device type)
        self.ident = ident
        #: human readable description/name of the device
        self.description = description
        self.data = kwargs

    def __hash__(self):
        return hash((str(self.backend_domain), self.ident))

    def __eq__(self, other):
        try:
            return (
                self.backend_domain == other.backend_domain and
                self.ident == other.ident
            )
        except AttributeError:
            return False

    def __str__(self):
        return '{!s}:{!s}'.format(self.backend_domain, self.ident)


class UnknownDevice(DeviceInfo):
    # pylint: disable=too-few-public-methods
    '''Unknown device - for example exposed by domain not running currently'''

    def __init__(self, backend_domain, devclass, ident, description=None,
            **kwargs):
        if description is None:
            description = "Unknown device"
        super(UnknownDevice, self).__init__(backend_domain, devclass, ident,
            description, **kwargs)


class DeviceCollection(object):
    '''Bag for devices.

    Used as default value for :py:meth:`DeviceManager.__missing__` factory.

    :param vm: VM for which we manage devices
    :param class_: device class

    '''
    def __init__(self, vm, class_):
        self._vm = vm
        self._class = class_
        self._dev_cache = {}

    def attach(self, device_assignment):
        '''Attach (add) device to domain.

        :param DeviceAssignment device_assignment: device object
        '''

        if not device_assignment.frontend_domain:
            device_assignment.frontend_domain = self._vm
        else:
            assert device_assignment.frontend_domain == self._vm, \
                "Trying to attach DeviceAssignment belonging to other domain"
        if device_assignment.devclass is None:
            device_assignment.devclass = self._class
        else:
            assert device_assignment.devclass == self._class

        options = device_assignment.options.copy()
        if device_assignment.persistent:
            options['persistent'] = 'True'
        options_str = ' '.join('{}={}'.format(opt,
            val) for opt, val in sorted(options.items()))
        self._vm.qubesd_call(None,
            'admin.vm.device.{}.Attach'.format(self._class),
            '{!s}+{!s}'.format(device_assignment.backend_domain,
                device_assignment.ident),
            options_str.encode('utf-8'))

    def detach(self, device_assignment):
        '''Detach (remove) device from domain.

        :param DeviceAssignment device_assignment: device to detach
        (obtained from :py:meth:`assignments`)
        '''
        if not device_assignment.frontend_domain:
            device_assignment.frontend_domain = self._vm
        else:
            assert device_assignment.frontend_domain == self._vm, \
                "Trying to detach DeviceAssignment belonging to other domain"
        if device_assignment.devclass is None:
            device_assignment.devclass = self._class
        else:
            assert device_assignment.devclass == self._class

        self._vm.qubesd_call(None,
            'admin.vm.device.{}.Detach'.format(self._class),
            '{!s}+{!s}'.format(device_assignment.backend_domain,
                device_assignment.ident))

    def assignments(self, persistent=None):
        '''List assignments for devices which are (or may be) attached to the
           vm.

        Devices may be attached persistently (so they are included in
        :file:`qubes.xml`) or not. Device can also be in :file:`qubes.xml`,
        but be temporarily detached.

        :param bool persistent: only include devices which are or are not
        attached persistently.
        '''

        assignments_str = self._vm.qubesd_call(None,
            'admin.vm.device.{}.List'.format(self._class)).decode()
        for assignment_str in assignments_str.splitlines():
            device, _, options_all = assignment_str.partition(' ')
            backend_domain, ident = device.split('+', 1)
            options = dict(opt_single.split('=', 1)
                for opt_single in options_all.split(' ') if opt_single)
            dev_persistent = (options.pop('persistent', False) in
                 ['True', 'yes', True])
            if persistent is not None and dev_persistent != persistent:
                continue
            backend_domain = self._vm.app.domains[backend_domain]
            yield DeviceAssignment(backend_domain, ident, options,
                persistent=dev_persistent, frontend_domain=self._vm,
                devclass=self._class)

    def attached(self):
        '''List devices which are (or may be) attached to this vm '''

        for assignment in self.assignments():
            yield assignment.device

    def persistent(self):
        ''' Devices persistently attached and safe to access before libvirt
            bootstrap.
        '''

        for assignment in self.assignments(True):
            yield assignment.device

    def available(self):
        '''List devices exposed by this vm'''
        devices_str = self._vm.qubesd_call(None,
            'admin.vm.device.{}.Available'.format(self._class)).decode()
        for dev_str in devices_str.splitlines():
            ident, _, info = dev_str.partition(' ')
            # description is special that it can contain spaces
            info, _, description = info.partition('description=')
            info_dict = dict(info_single.split('=', 1)
                for info_single in info.split(' ') if info_single)
            yield DeviceInfo(self._vm, self._class, ident,
                description=description,
                **info_dict)

    def update_persistent(self, device, persistent):
        '''Update `persistent` flag of already attached device.

        :param DeviceInfo device: device for which change persistent flag
        :param bool persistent: new persistent flag
        '''

        self._vm.qubesd_call(None,
            'admin.vm.device.{}.Set.persistent'.format(self._class),
            '{!s}+{!s}'.format(device.backend_domain,
                device.ident),
            str(persistent).encode('utf-8'))

    __iter__ = available

    def clear_cache(self):
        '''Clear cache of available devices'''
        self._dev_cache.clear()

    def __getitem__(self, item):
        '''Get device object with given ident.

        :returns: py:class:`DeviceInfo`

        If domain isn't running, it is impossible to check device validity,
        so return UnknownDevice object. Also do the same for non-existing
        devices - otherwise it will be impossible to detach already
        disconnected device.
        '''
        # fist, check if we have cached device info
        if item in self._dev_cache:
            return self._dev_cache[item]
        # then look for available devices
        for dev in self.available():
            if dev.ident == item:
                self._dev_cache[item] = dev
                return dev
        # if still nothing, return UnknownDevice instance for the reason
        # explained in docstring, but don't cache it
        return UnknownDevice(self._vm, self._class, item)



class DeviceManager(dict):
    '''Device manager that hold all devices by their classess.

    :param vm: VM for which we manage devices
    '''

    def __init__(self, vm):
        super(DeviceManager, self).__init__()
        self._vm = vm

    def __missing__(self, key):
        self[key] = DeviceCollection(self._vm, key)
        return self[key]
