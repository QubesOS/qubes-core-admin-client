#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2023 Marta Marczykowska-Górecka
#                               <marmarta@invisiblethingslab.com>
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

# pylint: disable=missing-docstring

"""
Mock Qubes object for testing programs without using a running Qubes OS
instance (allows testing packages in VMs).
How to use:
- When providing a Qubes object to your program, use one of the MockQubes
objects from this file.
- if the program also uses events, this cannot be easily mocked (yet), so
you can use MockDispatcher that does nothing.

Example: to run qui-domains widget in a qube using MockQubes,
replace it's main with the following:


>>> def main():
... ''' main function '''
... # qapp = qubesadmin.Qubes()
... # dispatcher = qubesadmin.events.EventsDispatcher(qapp)
... # stats_dispatcher = qubesadmin.events.EventsDispatcher(
... #    qapp, api_method='admin.vm.Stats'
... # )
...
>>> import qubesadmin.tests.mock_app as mock_app
... qapp = mock_app.MockQubesComplete()
... dispatcher = mock_app.MockDispatcher(qapp)
... stats_dispatcher = mock_app.MockDispatcher(
...     qapp, api_method='admin.vm.Stats')
...
>>> # continues as normal

To run a mocked program, remember to extend PYTHONPATH appropriately, z.B.:
    PYTHONPATH=../core-admin-client:. python3 qui/tray/domains.py

To collect information to modify this script, you can use the wrapper function
to wrap and output all qubesd calls used by a program running on a live qubes
instance.
    qapp = qubesadmin.Qubes()
    import qubesadmin.tests.mock_app as mock_app
    qapp.qubesd_call = mock_app.wrapper(qapp.qubesd_call)
    qapp._parse_qubesd_response = mock_app.wrapper(qapp._parse_qubesd_response)

"""
import asyncio
from unittest import mock
from copy import deepcopy

from typing import Any

import qubesadmin.events
from qubesadmin.tests import QubesTest
from qubesadmin.tests.tools import MockEventsReader


# Helper methods


def wrapper(method):
    """Very simple wrapper that prints arguments with which the wrapped method
    was called. Used to wrap qubesd calls to extend this library."""

    def _wrapped_method(*args, **kwargs):
        if kwargs:
            print(args, kwargs)
        else:
            print(args)
        return_val = method(*args, **kwargs)
        return return_val

    return _wrapped_method


class Property:
    """
    Qubes property; holds information on property type and if it's the default.
    """

    def __init__(self, value: str, prop_type: str = str, default: bool = False):
        """
        :param value: property value as string
        :param prop_type: type ('int', 'bool', 'str', 'vm', 'label')
        :param default: is the property the default value?
        """
        self.value = value
        self.type = prop_type
        self.default = default

    def __str__(self):
        return f"default={self.default} type={self.type} {self.value}"

    def default_string(self):
        return f"type={self.type} {self.value}"


DEFAULT_VM_PROPERTIES = {
    "appvm_default_bootmode": Property("default", "str", True),
    "audiovm": Property("dom0", "vm", True),
    "auto_cleanup": Property("False", "bool", True),
    "autostart": Property("False", "bool", True),
    "backup_timestamp": Property("", "int", True),
    "bootmode": Property("default", "str", True),
    "debug": Property("False", "bool", True),
    "default_dispvm": Property("default-dvm", "vm", False),
    "default_user": Property("user", "str", True),
    "devices_denied": Property("", "str", True),
    "dns": Property("10.139.1.1 10.139.1.2", "str", True),
    "gateway": Property("", "str", True),
    "gateway6": Property("", "str", True),
    "guivm": Property("dom0", "vm", True),
    "icon": Property("appvm-green", "str", True),
    "include_in_backups": Property("True", "bool", True),
    "installed_by_rpm": Property("False", "bool", True),
    "ip": Property("10.137.0.2", "str", True),
    "ip6": Property("", "str", True),
    "is_preload": Property("False", "bool", True),
    "kernel": Property("5.15.52-1.fc32", "str", True),
    "kernelopts": Property("", "str", True),
    "keyboard_layout": Property("us++", "str", True),
    "klass": Property("AppVM", "str", True),
    "label": Property("green", "label", False),
    "mac": Property("00:16:3e:5e:6c:00", "str", True),
    "management_dispvm": Property("default-mgmt-dvm", "vm", True),
    "maxmem": Property("4000", "int", True),
    "memory": Property("400", "int", True),
    "name": Property("testvm", "str", False),
    "netvm": Property("sys-firewall", "vm", False),
    "provides_network": Property("False", "bool", True),
    "qid": Property("2", "int", False),
    "qrexec_timeout": Property("60", "int", True),
    "shutdown_timeout": Property("60", "int", True),
    "start_time": Property("", "str", True),
    "stubdom_mem": Property("", "int", True),
    "stubdom_xid": Property("-1", "str", True),
    "template": Property("fedora-36", "vm", False),
    "template_for_dispvms": Property("False", "bool", True),
    "updateable": Property("False", "bool", True),
    "uuid": Property("8fd73e95-a74b-4bf0-a87d-9978dbd1d8a4", "str", False),
    "vcpus": Property("2", "int", True),
    "virt_mode": Property("pvh", "str", True),
    "visible_gateway": Property("10.137.0.1", "str", True),
    "visible_gateway6": Property("", "str", True),
    "visible_ip": Property("10.137.0.2", "str", True),
    "visible_ip6": Property("", "str", True),
    "visible_netmask": Property("255.255.255.255", "str", True),
    "xid": Property("2", "str", True),
}

DEFAULT_DOM0_PROPERTIES = {
    "default_dispvm": Property("", "vm", False),
    "icon": Property("adminvm-black", "str", True),
    "include_in_backups": Property("True", "bool", True),
    "keyboard_layout": Property("us++", "str", True),
    "klass": Property("AdminVM", "str", True),
    "label": Property("black", "label", False),
    "name": Property("dom0", "str", True),
    "qid": Property("0", "int", True),
    "updateable": Property("True", "bool", True),
    "uuid": Property("00000000-0000-0000-0000-000000000000", "str", True),
}

DEFAULT_DOM0_FEATURES = {
    "config-usbvm-name": None,
    "config.default.qubes-update-check": None,
    "gui-default-allow-fullscreen": "",
    "gui-default-allow-utf8-titles": "",
    "gui-default-secure-copy-sequence": "Ctrl-c",
    "gui-default-secure-paste-sequence": "Ctrl-v",
    "gui-default-trayicon-mode": "",
    "service.qubes-update-check": 1,
}

GLOBAL_PROPERTIES = {
    "clockvm": Property("", "vm", False),
    "default_audiovm": Property("", "vm", False),
    "default_dispvm": Property("", "vm", False),
    "default_kernel": Property("1.1", "str", True),
    "default_netvm": Property("", "vm", False),
    "default_pool": Property("file", "str", True),
    "default_pool_private": Property("vm-pool", "str", True),
    "default_pool_volatile": Property("file", "str", True),
    "default_guivm": Property("", "vm", False),
    "default_template": Property("", "vm", False),
    "updatevm": Property("", "vm", False),
    "management_dispvm": Property("", "vm", False),
}

ALL_KNOWN_FEATURES = [
    "updates-available",
    "internal",
    "servicevm",
    "appmenus-dispvm",
    "os-eol",
    "supported-service.shutdown-idle",
    "os",
    "gui-allow-fullscreen",
    "gui-allow-utf8-titles",
    "qubes-firewall",
    "service.shutdown-idle",
    "supported-service.qubes-updates-proxy",
    "service.clocksync",
    "supported-service.clocksync",
    "skip-update",
    "boot-mode.active",
    "boot-mode.appvm-default",
    "boot-mode.name.default",
    "boot-mode.kernelopts.mode1",
    "boot-mode.kernelopts.mode2",
    "boot-mode.name.mode1",
    "boot-mode.name.mode2",
    "service.updates-proxy-setup",
    "qubes-vm-update-update-if-stale",
    "restart-after-update",
    "qubes-vm-update-hide-skipped",
    "template-name",
    "last-updates-check",
    "last-update",
    "prohibit-start",
    "preload-dispvm-max",
    "preload-dispvm-threshold",
    "preload-dispvm",
    "preload-dispvm-in-progress",
    "preload-dispvm-completed",
    "qubes-vm-update-hide-updated",
    "qubes-vm-update-restart-servicevms",
    "qubes-vm-update-restart-system",
    "qubes-vm-update-restart-other",
    "qubes-vm-update-max-concurrency",
    "supported-rpc.qubes.TemplateDownload",
    "supported-rpc.qubes.Gpg",
    "service.audiovm",
    "service.guivm",
]

POSSIBLE_TAGS = ["whonix-updatevm", "anon-gateway", "anon-vm"]


class VolumeInfo:
    """Class that handles the qubesdb VolumeInfo string."""

    # TODO: enhancements: obsolete volumes
    def __init__(
        self,
        qube_name: str,
        volume_type: str,
        outdated: bool = False,
        usage_perc: float | None = 0.0,
        save_on_stop: bool = False,
    ):
        """
        :param qube_name: name of the associated qube
        :param volume_type: one of the following:
         root, private, volatile, kernel
         :param usage_perc: optional (how much disk space is in use)
         :param save_on_stop: optional, overwrite save_on_stop for volume
         types other than private
        """
        self.qube_name = qube_name
        self.volume_type = volume_type
        self.outdated = outdated
        self.size = 2**30
        self.usage = int(self.size * usage_perc)
        self.save_on_stop = save_on_stop

    def response_string(self):
        """The complete response string."""
        return b"0\x00" + str(self).encode()

    def __str__(self):
        if self.volume_type == "kernel":
            result = "pool=linux-kernel\n"
            result += "vid=1.1\n"
            result += "size=0\n"
            result += "usage=0\n"
            result += "rw=False\n"
        else:
            result = "pool=vm-pool\n"
            result += f"vid=qubes_dom0/vm-{self.qube_name}-{self.volume_type}\n"
            result += f"size={self.size}\n"
            result += f"usage={self.usage}\n"
            result += "rw=True\n"

        if self.volume_type == "root":
            result += "source=qubes_dom0/vm-template-root\n"
        else:
            result += "source=\n"

        if self.volume_type == "kernel":
            result += "path=/var/lib/qubes/vm-kernels/1.1/modules.img\n"
        else:
            name = self.qube_name.replace("-", "--")
            result += (
                f"path=/dev/mapper/"
                f"qubes_dom0-vm--{name}--{self.volume_type}\n"
            )

        if self.volume_type == "private":
            result += "save_on_stop=True\n"
        else:
            result += f"save_on_stop={self.save_on_stop}\n"

        if self.volume_type == "root":
            result += "snap_on_start=True\n"
        else:
            result += "snap_on_start=False\n"

        result += "revisions_to_keep=2\n"
        result += "ephemeral=False\n"
        result += f"is_outdated={self.outdated}\n"

        return result


class MockQube:
    """Object that helps generate qube-related calls. Initializing the object
    already adds all relevant calls to the qapp object. If changes were made,
    run update_calls to notify the qapp object of them."""

    def __init__(
        self,
        name: str,
        qapp: QubesTest,
        klass: str = "AppVM",
        running: bool = False,
        features: dict | None = None,
        usage: float | None = 0.0,
        tags: list | None = None,
        firewall_rules: list[dict[str, str]] | None = None,
        override_default_props: dict | None = None,
        **kwargs,
    ):
        """
        Creates a mock qube object and updates all relevant calls.
        :param name: qube name
        :param qapp: Mock qubes object
        :param klass:  qube class
        :param running: is the qube running?
        :param features: qube features, provided as a dict of
        feature name: value
        :param tags: list of tags as strings
        :param kwargs: any other parameters, given as keyword arguments;
        if parameter default-ness is important, provide it as
        a (value, is_default) tuple
        """
        # pylint: disable=too-many-positional-arguments
        if override_default_props:
            self.properties = deepcopy(override_default_props)
        else:
            self.properties = deepcopy(DEFAULT_VM_PROPERTIES)

        self.qapp = qapp
        self.name = name
        self.klass = klass
        self.running = running
        self.usage = usage
        self.features = features if features else {}
        self.firewall_rules = (
            firewall_rules if firewall_rules else [{"action": "accept"}]
        )
        self.tags = tags if tags else []

        self._add_to_vm_list(name, klass)

        if self.klass == "AdminVM":
            self.properties["icon"].value = "adminvm-black"
        elif (
            self.klass == "AppVM"
            and str(kwargs.get("template_for_dispvms", "False")) == "True"
        ):
            self.properties["icon"].value = (
                "templatevm-" + self.properties["label"].value
            )
        else:
            self.properties["icon"].value = (
                self.klass.lower() + "-" + self.properties["label"].value
            )

        for prop, value in kwargs.items():
            if prop in self.properties:
                if isinstance(value, tuple):
                    val, is_default = value
                    self.properties[prop].value = val
                    self.properties[prop].default = is_default
                else:
                    self.properties[prop].value = str(value)
                    self.properties[prop].default = (
                        str(value) == DEFAULT_VM_PROPERTIES.get(prop).default
                    )

        self.update_calls()

    def __setattr__(self, key, value):
        if key != "properties" and key in self.properties:
            self.properties[key].value = str(value)
            self.properties[key].default = False
        else:
            return super().__setattr__(key, value)

    def __getattr__(self, item):
        if item in self.properties:
            return self.properties[item].value

    def set_property_default(self, prop, value):
        """Set a property as default."""
        if prop in self.properties:
            self.properties[prop].value = value
            self.properties[prop].default = True
        else:
            raise AttributeError

    def _add_to_vm_list(self, name: str, klass: str):
        """Modify existing VM list call to add this qube.
        Should not be called twice."""
        state = "Running" if self.running else "Halted"

        vm_list_call = ("dom0", "admin.vm.List", None, None)
        vm_list = b"0\x00"
        if vm_list_call in self.qapp.expected_calls:
            vm_list = self.qapp.expected_calls[vm_list_call]
        list_call = f"{name} class={klass} state={state}\n".encode()
        vm_list += list_call
        self.qapp.expected_calls[vm_list_call] = vm_list

    def update_calls(self):
        """
        Update all qapp calls related to this qube.
        """
        properties_getall = b"0\x00"

        # create power state call
        if self.running:
            response = b"0\x00power_state=Running"
        else:
            response = b"0\x00power_state=Halted"
        self.qapp.expected_calls[
            (self.name, "admin.vm.CurrentState", None, None)
        ] = response

        # create all propertyget calls
        for prop, value in self.properties.items():
            if (
                (prop == "template")
                and self.klass in ("TemplateVM", "StandaloneVM")
            ) or (
                (prop == "appvm_default_bootmode") and self.klass in ("AppVM",)
            ):
                self.qapp.expected_calls[
                    (self.name, "admin.vm.property.Get", prop, None)
                ] = b"2\x00QubesNoSuchPropertyError\x00\x00No such property\x00"
                self.qapp.expected_calls[
                    (self.name, "admin.vm.property.GetDefault", prop, None)
                ] = b"2\x00QubesNoSuchPropertyError\x00\x00No such property\x00"
                continue
            properties_getall += f"{prop} {value}\n".encode()
            self.qapp.expected_calls[
                (self.name, "admin.vm.property.Get", prop, None)
            ] = (b"0\x00" + str(value).encode())
            if prop in DEFAULT_VM_PROPERTIES:
                default_value = DEFAULT_VM_PROPERTIES[prop]
                self.qapp.expected_calls[
                    (self.name, "admin.vm.property.GetDefault", prop, None)
                ] = (b"0\x00" + default_value.default_string().encode())

        # the property.GetAll call is optional, but let's have it, why not
        self.qapp.expected_calls[
            (self.name, "admin.vm.property.GetAll", None, None)
        ] = properties_getall

        # features: we add both feature.Get and feature.CheckWithTemplate, with
        # the same resulting value
        # important: if a feature is provided with value 'None', it will be
        # treated as an absent feature (for compatibility with existing tests)
        for feature_name, value in self.features.items():
            if value is not None:
                self.qapp.expected_calls[
                    (self.name, "admin.vm.feature.Get", feature_name, None)
                ] = (b"0\x00" + str(value).encode())
                self.qapp.expected_calls[
                    (
                        self.name,
                        "admin.vm.feature.CheckWithTemplate",
                        feature_name,
                        None,
                    )
                ] = (
                    b"0\x00" + str(value).encode()
                )
            else:
                self.qapp.expected_calls[
                    (self.name, "admin.vm.feature.Get", feature_name, None)
                ] = (
                    b"2\x00QubesFeatureNotFoundError\x00\x00"
                    + str(feature_name).encode()
                    + b"\x00"
                )
                self.qapp.expected_calls[
                    (
                        self.name,
                        "admin.vm.feature.CheckWithTemplate",
                        feature_name,
                        None,
                    )
                ] = (
                    b"2\x00QubesFeatureNotFoundError\x00\x00"
                    + str(feature_name).encode()
                    + b"\x00"
                )

        # list all features correctly
        self.qapp.expected_calls[
            (self.name, "admin.vm.feature.List", None, None)
        ] = (
            "0\x00" + "".join(f"{feature}\n" for feature in self.features)
        ).encode()

        # setup all volumeInfo related calls
        self.setup_volume_calls()

        # tags
        for tag in POSSIBLE_TAGS:
            if self.tags and tag in self.tags:
                continue
            self.qapp.expected_calls[
                (self.name, "admin.vm.tag.Get", tag, None)
            ] = b"0\x000"

        if self.tags:
            self.qapp.expected_calls[
                (self.name, "admin.vm.tag.List", None, None)
            ] = (b"0\x00" + ("".join(f"{tag}\n" for tag in self.tags)).encode())
            for tag in self.tags:
                self.qapp.expected_calls[
                    (self.name, "admin.vm.tag.Get", tag, None)
                ] = b"0\0001"
        else:
            self.qapp.expected_calls[
                (self.name, "admin.vm.tag.List", None, None)
            ] = "0\x00".encode()

        self.setup_device_calls()
        self.setup_firewall_rules(self.firewall_rules)

        # pylint: disable=protected-access
        self.qapp._invalidate_cache_all()

    def setup_volume_calls(self):
        self.qapp.expected_calls[
            (self.name, "admin.vm.volume.List", None, None)
        ] = b"0\x00root\nprivate\nvolatile\nkernel\n"
        self.qapp.expected_calls[
            (self.name, "admin.vm.volume.Info", "root", None)
        ] = VolumeInfo(
            self.name,
            "root",
            usage_perc=self.usage,
            save_on_stop=self.klass in ["TemplateVM", "StandaloneVM"],
        ).response_string()
        self.qapp.expected_calls[
            (self.name, "admin.vm.volume.Info", "private", None)
        ] = VolumeInfo(
            self.name, "private", usage_perc=self.usage
        ).response_string()
        self.qapp.expected_calls[
            (self.name, "admin.vm.volume.Info", "volatile", None)
        ] = VolumeInfo(
            self.name, "volatile", usage_perc=self.usage
        ).response_string()
        self.qapp.expected_calls[
            (self.name, "admin.vm.volume.Info", "kernel", None)
        ] = VolumeInfo(self.name, "kernel").response_string()

    def setup_device_calls(self):
        # all devices
        self.qapp.expected_calls[
            (self.name, "admin.vm.device.pci.List", None, None)
        ] = b"0\x00"
        self.qapp.expected_calls[
            (self.name, "admin.vm.device.block.List", None, None)
        ] = b"0\x00"
        self.qapp.expected_calls[
            (self.name, "admin.vm.device.usb.List", None, None)
        ] = b"0\x00"
        self.qapp.expected_calls[
            (self.name, "admin.vm.device.mic.List", None, None)
        ] = b"0\x00"

        # available devices
        self.qapp.expected_calls[
            (self.name, "admin.vm.device.pci.Available", None, None)
        ] = b"0\x00"
        self.qapp.expected_calls[
            (self.name, "admin.vm.device.block.Available", None, None)
        ] = b"0\x00"
        self.qapp.expected_calls[
            (self.name, "admin.vm.device.usb.Available", None, None)
        ] = b"0\x00"
        self.qapp.expected_calls[
            (self.name, "admin.vm.device.mic.Available", None, None)
        ] = b"0\x00"

        # assigned devices
        self.qapp.expected_calls[
            (self.name, "admin.vm.device.pci.Assigned", None, None)
        ] = b"0\x00"
        self.qapp.expected_calls[
            (self.name, "admin.vm.device.block.Assigned", None, None)
        ] = b"0\x00"
        self.qapp.expected_calls[
            (self.name, "admin.vm.device.usb.Assigned", None, None)
        ] = b"0\x00"
        self.qapp.expected_calls[
            (self.name, "admin.vm.device.mic.Assigned", None, None)
        ] = b"0\x00"

        # currently attached devices
        self.qapp.expected_calls[
            (self.name, "admin.vm.device.pci.Attached", None, None)
        ] = b"0\x00"
        self.qapp.expected_calls[
            (self.name, "admin.vm.device.block.Attached", None, None)
        ] = b"0\x00"
        self.qapp.expected_calls[
            (self.name, "admin.vm.device.usb.Attached", None, None)
        ] = b"0\x00"
        self.qapp.expected_calls[
            (self.name, "admin.vm.device.mic.Attached", None, None)
        ] = b"0\x00"

    def setup_firewall_rules(self, rule_list: list[dict[str, str]]):
        """setup firewall with provided rules: rules should be provided as
        list of dictionaries. Typical keys are action, proto, dsthost,
        dstports, icmptype, specialtarget, expire and comment"""
        rules = b"0\x00"

        for rule_dict in rule_list:
            rules += (
                " ".join(f"{key}={value}" for key, value in rule_dict.items())
                + "\n"
            ).encode()
        self.qapp.expected_calls[
            (self.name, "admin.vm.firewall.Get", None, None)
        ] = rules


class MockAdminVM(MockQube):
    def __init__(self, qapp):
        super().__init__(
            "dom0",
            qapp,
            klass="AdminVM",
            running=True,
            features=DEFAULT_DOM0_FEATURES.copy(),
            override_default_props=DEFAULT_DOM0_PROPERTIES.copy(),
        )
        # make all properties that are unknown give an 'unknown property' error
        for property_name in DEFAULT_VM_PROPERTIES:
            if property_name not in self.properties:
                self.qapp.expected_calls[
                    (self.name, "admin.vm.property.Get", property_name, None)
                ] = b"2\x00QubesNoSuchPropertyError\x00\x00No such property\x00"
                continue


# pylint: disable=too-many-positional-arguments
class MockDevice:
    """helper for adding a device to a qubes test instance"""

    def __init__(
        self,
        qapp: QubesTest,
        dev_class: str,
        device_id: str,
        backend_vm: str,
        port: str,
        product: str,
        vendor: str,
        attached: str | None = None,
        assigned: list[tuple[str, str, list[Any] | None]] | None = None,
    ):
        """
        :param qapp: QubesTest object
        :param dev_class: block / mic / usb
        :param device_id: device_id
        :param port: port
        :param backend_vm: name of the vm providing this device
        :param attached: name of the qube to which the device is
        currently attached,
        :param assigned: list of the qubes to which the device is currently
        assigned, tupled with mode ('ask-to-attach' or 'auto-attach')
        """
        self.qapp = qapp
        self.dev_class = dev_class
        self.device_id = device_id
        self.port = port
        self.backend_vm = backend_vm
        self.attached = attached
        self.assigned = assigned
        self.product = product
        self.vendor = vendor

        self.interface = self.device_id.split(":")[-1]

        self.update_calls()

    def device_string(self):
        return (
            f"{self.port} device_id='{self.device_id}' "
            f"port_id='{self.port}' devclass='{self.dev_class}' "
            f"product='{self.product}' vendor='{self.vendor}' "
            f"interfaces='{self.interface}' "
            f"backend_domain='{self.backend_vm}'\n"
        )

    def attachment_string(self):
        string = (
            f"{self.backend_vm}+{self.port} "
            f"port_id='{self.port}' devclass='{self.dev_class}' "
            f"backend_domain='{self.backend_vm}' mode='manual' "
            f"frontend_domain='{self.attached}'"
        )
        string += "\n"
        return string

    def assignment_string(self, vm, mode, opts):
        string = (
            f"{self.backend_vm}+{self.port} device_id='"
            f"{self.device_id}' "
            f"port_id='{self.port}' devclass='{self.dev_class}' "
            f"backend_domain='{self.backend_vm}' mode='{mode}' "
            f"frontend_domain='{vm}'"
        )
        if opts:
            for opt in opts:
                string += f" _{opt}='True'"
        string += "\n"
        return string

    def update_calls(self):
        # modify call
        current_response = self.qapp.expected_calls[
            (
                self.backend_vm,
                f"admin.vm.device.{self.dev_class}.Available",
                None,
                None,
            )
        ]

        self.qapp.expected_calls[
            (
                self.backend_vm,
                f"admin.vm.device.{self.dev_class}.Available",
                None,
                None,
            )
        ] = (
            current_response + self.device_string().encode()
        )

        if self.attached:
            current_response = self.qapp.expected_calls[
                (
                    self.attached,
                    f"admin.vm.device.{self.dev_class}.Attached",
                    None,
                    None,
                )
            ]
            self.qapp.expected_calls[
                (
                    self.attached,
                    f"admin.vm.device.{self.dev_class}.Attached",
                    None,
                    None,
                )
            ] = (
                current_response + self.attachment_string().encode()
            )

        if self.assigned:
            for vm, mode, opts in self.assigned:
                current_response = self.qapp.expected_calls[
                    (
                        vm,
                        f"admin.vm.device.{self.dev_class}.Assigned",
                        None,
                        None,
                    )
                ]
                self.qapp.expected_calls[
                    (
                        vm,
                        f"admin.vm.device.{self.dev_class}.Assigned",
                        None,
                        None,
                    )
                ] = (
                    current_response
                    + self.assignment_string(vm, mode, opts).encode()
                )


class QubesTestWrapper(QubesTest):
    def __init__(self):
        super().__init__()
        self._local_name = "dom0"  # pylint: disable=protected-access
        self._devices = []
        self.app.qubesd_connection_type = "qrexec"

        self._qubes: dict[str, MockQube] = {"dom0": MockAdminVM(self)}

        labels = [
            "red",
            "orange",
            "yellow",
            "green",
            "gray",
            "blue",
            "purple",
            "black",
        ]
        # setup labels
        self.expected_calls[("dom0", "admin.label.List", None, None)] = (
            b"0\x00" + "\n".join(labels).encode() + b"\n"
        )
        for i, label in enumerate(labels):
            self.expected_calls[("dom0", "admin.label.Index", label, None)] = (
                b"0\x00" + str(i).encode()
            )

        # setup pools:
        pools = ["linux-kernel", "lvm", "file", "vm-pool"]
        self.expected_calls[("dom0", "admin.pool.List", None, None)] = (
            b"0\x00" + "\n".join(pools).encode() + b"\n"
        )
        self.expected_calls[
            ("dom0", "admin.pool.volume.List", "linux-kernel", None)
        ] = b"0\x001.1\nmisc\n4.2\n"

        for pool in pools:
            self.app.expected_calls[
                ("dom0", "admin.pool.UsageDetails", pool, None)
            ] = (
                b"0\x00data_size=1099511627776\n"
                b"data_usage=102400\n"
                b"metadata_size=1024\n"
                b"metadata_usage=50\n"
            )

        self.populate_feature_calls()

    def update_vm_calls(self):
        """Update all qube calls. Must be called if changes are made."""
        for qid, qube in enumerate(self._qubes.values()):
            qube.qid = qid
            qube.update_calls()
        for dev in self._devices:
            dev.update_calls()
        self.populate_feature_calls()

    def populate_feature_calls(self):
        """Make sure that asking qubes for features they don't have results
        in correct FeatureNotFound error"""
        known_features = set(ALL_KNOWN_FEATURES)
        for qube in self._qubes.values():
            for feature in qube.features.keys():
                known_features.add(feature)

        for qube in self._qubes.values():
            for feature in known_features:
                calls = [
                    (qube.name, "admin.vm.feature.Get", feature, None),
                    (
                        qube.name,
                        "admin.vm.feature.CheckWithTemplate",
                        feature,
                        None,
                    ),
                ]
                for call in calls:
                    if call in self.expected_calls:
                        continue
                    self.expected_calls[call] = (
                        b"2\x00QubesFeatureNotFoundError\x00\x00"
                        + str(feature).encode()
                        + b"\x00"
                    )

    def set_global_property(self, property_name: str, value: str | None):
        self._global_properties[property_name].value = value

    def update_global_properties(self):
        properties_getall = b"0\x00"

        for property_name, value in self._global_properties.items():
            self.app.expected_calls[
                ("dom0", "admin.property.Get", property_name, None)
            ] = (b"0\x00" + str(value).encode())
            properties_getall += f"{property_name} {value}\n".encode()
        self.app.expected_calls[
            ("dom0", "admin.property.GetAll", None, None)
        ] = properties_getall


class MockQubes(QubesTestWrapper):
    """
    Bare-bones Qubes testing instance, with just the dom0, sys-net,
    one template (fedora-36).
    Available pools: linux-kernel, lvm and file.
    Available linux kernels: 1.1, misc and 4.2
    """

    def __init__(self):
        super().__init__()
        self._qubes["sys-net"] = MockQube(
            name="sys-net",
            qapp=self,
            running=True,
            template="fedora-36",
            provides_network=True,
            features={
                "service.qubes-updates-proxy": "1",
                "servicevm": "1",
                "supported-service.qubes-updates-proxy": "1",
            },
        )
        self._qubes["fedora-36"] = MockQube(
            name="fedora-36",
            qapp=self,
            klass="TemplateVM",
            netvm="",
            features={"service.updates-proxy-setup": 1},
        )

        self._global_properties = GLOBAL_PROPERTIES.copy()

        self.set_global_property("clockvm", "sys-net")
        self.set_global_property("default_dispvm", "fedora-36")
        self.set_global_property("default_netvm", "sys-net")
        self.set_global_property("default_template", "fedora-36")
        self.set_global_property("updatevm", "sys-net")

        self.update_global_properties()
        self.update_vm_calls()


class MockQubesComplete(MockQubes):
    """
    A complex Qubes setup, with multiple qubes.
    """

    def __init__(self):
        super().__init__()
        self._qubes["sys-firewall"] = MockQube(
            name="sys-firewall",
            qapp=self,
            netvm="sys-net",
            provides_network=True,
            features={
                "servicevm": "1",
                "qubes-firewall": 1,
                "supported-rpc.qubes.TemplateDownload": 1,
            },
        )

        self._qubes["sys-usb"] = MockQube(
            name="sys-usb",
            qapp=self,
            running=True,
            features={
                "supported-service.qubes-u2f-proxy": "1",
                "servicevm": "1",
            },
        )

        self._qubes["fedora-35"] = MockQube(
            name="fedora-35",
            qapp=self,
            klass="TemplateVM",
            netvm="",
            installed_by_rpm=True,
            features={
                "supported-service.qubes-u2f-proxy": "1",
                "service.qubes-update-check": "1",
                "updates-available": 1,
                "service.updates-proxy-setup": 1,
            },
        )

        self._qubes["default-mgmt-dvm"] = MockQube(
            name="default-mgmt-dvm",
            qapp=self,
            klass="AppVM",
            template_for_dispvms=True,
            template="fedora-36",
            features={"internal": "1"},
        )

        self._qubes["disp-mgmt"] = MockQube(
            name="disp-mgmt",
            qapp=self,
            klass="DispVM",
            template="default-mgmt-dvm",
            features={"internal": "1"},
        )

        self._qubes["default-dvm"] = MockQube(
            name="default-dvm",
            qapp=self,
            klass="AppVM",
            template_for_dispvms=True,
            template="fedora-36",
            features={"appmenus-dispvm": "1"},
        )

        self._qubes["test-disp"] = MockQube(
            name="test-disp",
            qapp=self,
            klass="DispVM",
            template="default-dvm",
        )

        self._qubes["test-alt-dvm"] = MockQube(
            name="test-alt-dvm",
            qapp=self,
            klass="AppVM",
            template_for_dispvms=True,
            template="fedora-36",
            features={"appmenus-dispvm": "1"},
        )

        self._qubes["test-alt-disp"] = MockQube(
            name="test-alt-disp",
            qapp=self,
            klass="DispVM",
            template="test-alt-dvm",
        )

        self._qubes["test-alt-dvm-running"] = MockQube(
            name="test-alt-dvm-running",
            qapp=self,
            klass="AppVM",
            template_for_dispvms=True,
            template="fedora-36",
            features={"appmenus-dispvm": "1"},
            running=True,
        )

        self._qubes["test-vm"] = MockQube(
            name="test-vm",
            qapp=self,
            features={
                "service.qubes-u2f-proxy": "1",
                "supported-service.qubes-u2f-proxy": "1",
            },
        )

        self._qubes["test-blue"] = MockQube(
            name="test-blue",
            running=True,
            qapp=self,
            label="blue",
            features={
                "supported-service.qubes-u2f-proxy": "1",
            },
        )

        self._qubes["test-red"] = MockQube(
            name="test-red", qapp=self, label="red"
        )

        self._qubes["test-old"] = MockQube(
            name="test-old", qapp=self, label="orange", template="fedora-35"
        )
        self._qubes["test-old"].set_property_default("netvm", "sys-firewall")

        self._qubes["test-standalone"] = MockQube(
            name="test-standalone",
            qapp=self,
            klass="StandaloneVM",
            label="green",
        )

        self._qubes["vault"] = MockQube(name="vault", qapp=self, netvm="")

        # # this system has some reasonable defaults
        self._qubes["dom0"].default_dispvm = "default-dvm"

        # also add a bunch of devices
        self._devices = [
            MockDevice(
                self,
                dev_class="mic",
                device_id="dom0:mic::m000000",
                backend_vm="dom0",
                port="mic",
                product="Internal Mic",
                vendor="ACME",
                attached="test-blue",
            ),
            # the usb stick appears as multiple devices, as they are wont to
            MockDevice(
                self,
                dev_class="usb",
                device_id="1d6b:0104:CAFEBABE:u030101u300000",
                backend_vm="sys-usb",
                port="2-1",
                product="My USB Drive",
                vendor="SCP Foundation",
            ),
            MockDevice(
                self,
                dev_class="block",
                device_id="1d6b:0104:CAFEBABE:b123456",
                backend_vm="sys-usb",
                port="sda",
                product="(USB)",
                vendor="SCP Foundation",
            ),
            MockDevice(
                self,
                dev_class="block",
                device_id="1d6b:0104:CAFEBABE:b123456",
                backend_vm="sys-usb",
                port="sda",
                product="()",
                vendor="SCP Foundation",
            ),
            MockDevice(
                self,
                dev_class="usb",
                device_id="04f2:b684:01.00.00:u0e0101u0e0201",
                backend_vm="sys-usb",
                port="2-7",
                product="Internal Camera",
                vendor="Saruman Industries",
            ),
            MockDevice(
                self,
                dev_class="pci",
                device_id="0x8086:0x4621::p060000",
                backend_vm="dom0",
                port="00_00.0",
                product="PCI Bridge",
                vendor="Unnamed Industries",
            ),
            MockDevice(
                self,
                dev_class="pci",
                device_id="0x8086:0x51e9::p0c8000",
                backend_vm="dom0",
                port="00_02.0",
                product="I2C Controller",
                vendor="Unnamed Industries",
            ),
            MockDevice(
                self,
                dev_class="pci",
                device_id="0x8086:0x461e::p0c0330",
                backend_vm="dom0",
                port="00_03.0",
                product="I2C Controller",
                vendor="Unnamed Industries",
            ),
        ]

        self.update_vm_calls()


class MockQubesWhonix(MockQubesComplete):
    """Complete Qubes system, with additional whonix qubes."""

    def __init__(self):
        super().__init__()

        self._qubes["sys-whonix"] = MockQube(
            name="sys-whonix",
            qapp=self,
            template="whonix-gw-15",
            features={
                "service.qubes-updates-proxy": "1",
                "supported-service.qubes-updates-proxy": "1",
            },
            tags=["anon-gateway"],
        )

        self._qubes["anon-whonix"] = MockQube(
            name="anon-whonix",
            qapp=self,
            template="whonix-gw-15",
            tags=["anon-gateway"],
        )

        self._qubes["whonix-gw-15"] = MockQube(
            name="whonix-gw-15",
            qapp=self,
            klass="TemplateVM",
            netvm="",
            tags=["whonix-updatevm"],
        )

        self._qubes["whonix-gw-14"] = MockQube(
            name="whonix-gw-14",
            qapp=self,
            klass="TemplateVM",
            netvm="",
            tags=["whonix-updatevm"],
        )

        self.update_vm_calls()


# Mock Stats Dispatcher object


async def noop_coro(*_args):
    """A very simple do-nothing coroutine, used to mock qubes events."""
    while True:
        await asyncio.sleep(5)


class MockDispatcher(qubesadmin.events.EventsDispatcher):
    """Create a mock EventsDispatcher object that does not actually dispatch
    events"""

    def __init__(self, qapp, **kwargs):
        super().__init__(qapp, **kwargs)
        self._listen_for_events = noop_coro


class MockEvent:
    """Helper class for event handling."""

    def __init__(
        self,
        event_subject: str,
        event_name: str,
        additional_keys: list[tuple[str, str]] | None = None,
    ):
        """
        event subject - the name of the object that fired the event
        event name - the name of the event
        additional keys: list of str, str tuples representing any additional
        event keys and values
        """
        self.event_string = "1\0" + event_subject + "\0" + event_name + "\0"
        if additional_keys:
            for key, value in additional_keys:
                self.event_string += key + "\0" + value + "\0"
        self.event_string += "\0"
        self.event_encoded = self.event_string.encode()

    def get_event_line(self):
        return self.event_encoded


class MockAsyncDispatcher(qubesadmin.events.EventsDispatcher):
    """Working mock events dispatcher. Events must be initialized with
    initialize_events."""

    def __init__(self, qapp, **kwargs):
        super().__init__(qapp, **kwargs)
        self.mock_events = mock.AsyncMock()
        self._get_events_reader = self.mock_events
        self.events = []

        connection_established_event = MockEvent("", "connection_established")
        self.events.append(connection_established_event.get_event_line())
        self.mock_events.side_effect = MockEventsReader(self.events)

    def add_expected_event(self, event: MockEvent):
        """
        add an event to events fired automatically when the object is
        initialized.
        """
        self.events.append(event.get_event_line())
