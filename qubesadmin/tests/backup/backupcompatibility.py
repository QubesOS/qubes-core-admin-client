# -*- encoding: utf8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2014 Marek Marczykowski-Górecki <marmarek@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public License
# as published by the Free Software Foundation; either version 2.1
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
import functools
import shutil
import tempfile
import unittest
from distutils import spawn
from multiprocessing import Queue

import os
import subprocess

import logging

import time

import contextlib

try:
    import unittest.mock as mock
except ImportError:
    import mock
import re

import multiprocessing
import importlib.resources
import sys

import qubesadmin.backup.core2
import qubesadmin.backup.core3
import qubesadmin.exc
import qubesadmin.firewall
import qubesadmin.storage
import qubesadmin.tests
import qubesadmin.tests.backup


MANGLED_SUBDIRS_R2 = {
    "test-work": "vm5",
    "test-template-clone": "vm9",
    "test-custom-template-appvm": "vm10",
    "test-standalonevm": "vm11",
    "test-testproxy": "vm12",
    "test-testhvm": "vm14",
    "test-net": "vm16",
}
MANGLED_SUBDIRS_R4 = {
    "test-work": "vm3",
    "test-fedora-25-clone": "vm7",
    "test-custom-template-appvm": "vm31",
    "test-standalonevm": "vm4",
    "test-proxy": "vm30",
    "test-hvm": "vm9",
    "test-net": "vm6",
    "test-d8test": "vm20",
}

APPTEMPLATE_R2B2 = '''
[Desktop Entry]
Name=%VMNAME%: {name}
GenericName=%VMNAME%: {name}
GenericName[ca]=%VMNAME%: Navegador web
GenericName[cs]=%VMNAME%: Webový prohlížeč
GenericName[es]=%VMNAME%: Navegador web
GenericName[fa]=%VMNAME%: مرورر اینترنتی
GenericName[fi]=%VMNAME%: WWW-selain
GenericName[fr]=%VMNAME%: Navigateur Web
GenericName[hu]=%VMNAME%: Webböngésző
GenericName[it]=%VMNAME%: Browser Web
GenericName[ja]=%VMNAME%: ウェブ・ブラウザ
GenericName[ko]=%VMNAME%: 웹 브라우저
GenericName[nb]=%VMNAME%: Nettleser
GenericName[nl]=%VMNAME%: Webbrowser
GenericName[nn]=%VMNAME%: Nettlesar
GenericName[no]=%VMNAME%: Nettleser
GenericName[pl]=%VMNAME%: Przeglądarka WWW
GenericName[pt]=%VMNAME%: Navegador Web
GenericName[pt_BR]=%VMNAME%: Navegador Web
GenericName[sk]=%VMNAME%: Internetový prehliadač
GenericName[sv]=%VMNAME%: Webbläsare
Comment={comment}
Comment[ca]=Navegueu per el web
Comment[cs]=Prohlížení stránek World Wide Webu
Comment[de]=Im Internet surfen
Comment[es]=Navegue por la web
Comment[fa]=صفحات شبه جهانی اینترنت را مرور نمایید
Comment[fi]=Selaa Internetin WWW-sivuja
Comment[fr]=Navigue sur Internet
Comment[hu]=A világháló böngészése
Comment[it]=Esplora il web
Comment[ja]=ウェブを閲覧します
Comment[ko]=웹을 돌아 다닙니다
Comment[nb]=Surf på nettet
Comment[nl]=Verken het internet
Comment[nn]=Surf på nettet
Comment[no]=Surf på nettet
Comment[pl]=Przeglądanie stron WWW
Comment[pt]=Navegue na Internet
Comment[pt_BR]=Navegue na Internet
Comment[sk]=Prehliadanie internetu
Comment[sv]=Surfa på webben
Exec=qvm-run -q --tray -a %VMNAME% '{command} %u'
Categories=Network;WebBrowser;
X-Qubes-VmName=%VMNAME%
Icon=%VMDIR%/icon.png
'''

QUBESXML_R1 = '''<?xml version='1.0' encoding='UTF-8'?>
<QubesVmCollection clockvm="2" default_fw_netvm="2" default_kernel="3.2.7-10" default_netvm="3" default_template="1" updatevm="3"><QubesTemplateVm conf_file="fedora-17-x64.conf" debug="False" default_user="user" dir_path="/var/lib/qubes/vm-templates/fedora-17-x64" include_in_backups="True" installed_by_rpm="True" internal="False" kernel="3.2.7-10" kernelopts="" label="gray" maxmem="4063" memory="400" name="fedora-17-x64" netvm_qid="3" pcidevs="[]" private_img="private.img" qid="1" root_img="root.img" services="{&apos;meminfo-writer&apos;: True}" template_qid="none" uses_default_kernel="True" uses_default_kernelopts="True" uses_default_netvm="True" vcpus="2" volatile_img="volatile.img" /><QubesNetVm conf_file="netvm.conf" debug="False" default_user="user" dir_path="/var/lib/qubes/servicevms/netvm" include_in_backups="True" installed_by_rpm="False" internal="False" kernel="3.2.7-10" kernelopts="iommu=soft swiotlb=2048" label="red" maxmem="4063" memory="200" name="netvm" netid="1" pcidevs="[&apos;00:19.0&apos;, &apos;03:00.0&apos;]" private_img="private.img" qid="2" root_img="root.img" services="{&apos;ntpd&apos;: False, &apos;meminfo-writer&apos;: False}" template_qid="1" uses_default_kernel="True" uses_default_kernelopts="True" vcpus="2" volatile_img="volatile.img" /><QubesProxyVm conf_file="firewallvm.conf" debug="False" default_user="user" dir_path="/var/lib/qubes/servicevms/firewallvm" include_in_backups="True" installed_by_rpm="False" internal="False" kernel="3.2.7-10" kernelopts="" label="green" maxmem="4063" memory="200" name="firewallvm" netid="2" netvm_qid="2" pcidevs="[]" private_img="private.img" qid="3" root_img="root.img" services="{&apos;meminfo-writer&apos;: True}" template_qid="1" uses_default_kernel="True" uses_default_kernelopts="True" vcpus="2" volatile_img="volatile.img" /><QubesAppVm conf_file="fedora-17-x64-dvm.conf" debug="False" default_user="user" dir_path="/var/lib/qubes/appvms/fedora-17-x64-dvm" include_in_backups="True" installed_by_rpm="False" internal="True" kernel="3.2.7-10" kernelopts="" label="gray" maxmem="4063" memory="400" name="fedora-17-x64-dvm" netvm_qid="3" pcidevs="[]" private_img="private.img" qid="4" root_img="root.img" services="{&apos;meminfo-writer&apos;: True}" template_qid="1" uses_default_kernel="True" uses_default_kernelopts="True" uses_default_netvm="True" vcpus="1" volatile_img="volatile.img" /><QubesAppVm conf_file="test-work.conf" debug="False" default_user="user" dir_path="/var/lib/qubes/appvms/test-work" include_in_backups="True" installed_by_rpm="False" internal="False" kernel="3.2.7-10" kernelopts="" label="green" maxmem="4063" memory="400" name="test-work" netvm_qid="3" pcidevs="[]" private_img="private.img" qid="5" root_img="root.img" services="{&apos;meminfo-writer&apos;: True}" template_qid="1" uses_default_kernel="True" uses_default_kernelopts="True" uses_default_netvm="True" vcpus="2" volatile_img="volatile.img" /><QubesAppVm conf_file="personal.conf" debug="False" default_user="user" dir_path="/var/lib/qubes/appvms/personal" include_in_backups="True" installed_by_rpm="False" internal="False" kernel="3.2.7-10" kernelopts="" label="yellow" maxmem="4063" memory="400" name="personal" netvm_qid="3" pcidevs="[]" private_img="private.img" qid="6" root_img="root.img" services="{&apos;meminfo-writer&apos;: True}" template_qid="1" uses_default_kernel="True" uses_default_kernelopts="True" uses_default_netvm="True" vcpus="2" volatile_img="volatile.img" /><QubesAppVm conf_file="banking.conf" debug="False" default_user="user" dir_path="/var/lib/qubes/appvms/banking" include_in_backups="True" installed_by_rpm="False" internal="False" kernel="3.2.7-10" kernelopts="" label="green" maxmem="4063" memory="400" name="banking" netvm_qid="3" pcidevs="[]" private_img="private.img" qid="7" root_img="root.img" services="{&apos;meminfo-writer&apos;: True}" template_qid="1" uses_default_kernel="True" uses_default_kernelopts="True" uses_default_netvm="True" vcpus="2" volatile_img="volatile.img" /><QubesAppVm conf_file="untrusted.conf" debug="False" default_user="user" dir_path="/var/lib/qubes/appvms/untrusted" include_in_backups="True" installed_by_rpm="False" internal="False" kernel="3.2.7-10" kernelopts="" label="red" maxmem="4063" memory="400" name="untrusted" netvm_qid="3" pcidevs="[]" private_img="private.img" qid="8" root_img="root.img" services="{&apos;meminfo-writer&apos;: True}" template_qid="1" uses_default_kernel="True" uses_default_kernelopts="True" uses_default_netvm="True" vcpus="2" volatile_img="volatile.img" /><QubesAppVm conf_file="test-standalonevm.conf" debug="False" default_user="user" dir_path="/var/lib/qubes/appvms/test-standalonevm" include_in_backups="True" installed_by_rpm="False" internal="False" kernel="None" kernelopts="" label="red" maxmem="4063" memory="400" name="test-standalonevm" netvm_qid="3" pcidevs="[]" private_img="private.img" qid="9" root_img="root.img" services="{&apos;meminfo-writer&apos;: True}" template_qid="none" uses_default_kernel="False" uses_default_kernelopts="True" uses_default_netvm="True" vcpus="2" volatile_img="volatile.img" /><QubesAppVm conf_file="test-testvm.conf" debug="False" default_user="user" dir_path="/var/lib/qubes/appvms/test-testvm" include_in_backups="True" installed_by_rpm="False" internal="False" kernel="3.2.7-10" kernelopts="" label="red" mac="00:16:3E:5E:6C:55" maxmem="4063" memory="400" name="test-testvm" netvm_qid="3" pcidevs="[]" private_img="private.img" qid="10" root_img="root.img" services="{&apos;meminfo-writer&apos;: True}" template_qid="1" uses_default_kernel="True" uses_default_kernelopts="True" uses_default_netvm="True" vcpus="2" volatile_img="volatile.img" /><QubesTemplateVm conf_file="test-template-clone.conf" debug="False" default_user="user" dir_path="/var/lib/qubes/vm-templates/test-template-clone" include_in_backups="True" installed_by_rpm="False" internal="False" kernel="3.2.7-10" kernelopts="" label="gray" maxmem="4063" memory="400" name="test-template-clone" netvm_qid="3" pcidevs="[]" private_img="private.img" qid="11" root_img="root.img" services="{&apos;meminfo-writer&apos;: True}" template_qid="none" uses_default_kernel="True" uses_default_kernelopts="True" uses_default_netvm="True" vcpus="2" volatile_img="volatile.img" /><QubesAppVm conf_file="test-custom-template-appvm.conf" debug="False" default_user="user" dir_path="/var/lib/qubes/appvms/test-custom-template-appvm" include_in_backups="True" installed_by_rpm="False" internal="False" kernel="3.2.7-10" kernelopts="" label="yellow" maxmem="4063" memory="400" name="test-custom-template-appvm" netvm_qid="3" pcidevs="[]" private_img="private.img" qid="12" root_img="root.img" services="{&apos;meminfo-writer&apos;: True}" template_qid="11" uses_default_kernel="True" uses_default_kernelopts="True" uses_default_netvm="True" vcpus="2" volatile_img="volatile.img" /><QubesProxyVm conf_file="test-testproxy.conf" debug="False" default_user="user" dir_path="/var/lib/qubes/servicevms/test-testproxy" include_in_backups="True" installed_by_rpm="False" internal="False" kernel="3.2.7-10" kernelopts="" label="yellow" maxmem="4063" memory="200" name="test-testproxy" netid="3" netvm_qid="2" pcidevs="[]" private_img="private.img" qid="13" root_img="root.img" services="{&apos;meminfo-writer&apos;: True}" template_qid="1" uses_default_kernel="True" uses_default_kernelopts="True" vcpus="2" volatile_img="volatile.img" /></QubesVmCollection>
'''

BACKUP_HEADER_R2 = '''version=3
hmac-algorithm=SHA512
crypto-algorithm=aes-256-cbc
encrypted={encrypted}
compressed={compressed}
compression-filter=gzip
'''

BACKUP_HEADER_R4 = '''version=4
hmac-algorithm=scrypt
encrypted=True
compressed={compressed}
compression-filter={compression_filter}
backup-id=20161020T123455-1234
'''

parsed_qubes_xml_r2 = {
    'domains': {
        'dom0': {
            'klass': 'AdminVM',
            'label': 'black',
            'properties': {},
            'devices': {},
            'tags': set(),
            'features': {},
            'template': None,
            'backup_path': 'dom0-home/user',
            'included_in_backup': True,
        },
        'fedora-20-x64': {
            'klass': 'TemplateVM',
            'label': 'black',
            'properties': {
                'maxmem': '1535',
            },
            'devices': {},
            'tags': set(),
            'features': {
                'service.meminfo-writer': True,
                'qrexec': True,
                'gui': True,
            },
            'template': None,
            'backup_path': None,
            'included_in_backup': False,
        },
        'netvm': {
            'klass': 'AppVM',
            'label': 'red',
            'properties': {
                'maxmem': '1535',
                'memory': '200',
                'netvm': None,
                'default_dispvm': 'disp-no-netvm',
                'provides_network': True},
            'devices': {
                'pci': {
                    ('dom0', '02_00.0'): {},
                    ('dom0', '03_00.0'): {},
                }
            },
            'tags': set(),
            'features': {
                'service.ntpd': False,
                'service.meminfo-writer': False
            },
            'template': 'fedora-20-x64',
            'backup_path': None,
            'included_in_backup': False,
        },
        'firewallvm': {
            'klass': 'AppVM',
            'label': 'green',
            'properties': {
                'maxmem': '1535',
                'memory': '200',
                'provides_network': True
            },
            'devices': {},
            'tags': set(),
            'features': {'service.meminfo-writer': True},
            'template': 'fedora-20-x64',
            'backup_path': None,
            'included_in_backup': False,
        },
        'fedora-20-x64-dvm': {
            'klass': 'AppVM',
            'label': 'gray',
            'properties': {
                'maxmem': '1535',
                'vcpus': '1'
            },
            'devices': {},
            'tags': set(),
            'features': {
                'internal': True, 'service.meminfo-writer': True},
            'template': 'fedora-20-x64',
            'backup_path': None,
            'included_in_backup': False,
        },
        'banking': {
            'klass': 'AppVM',
            'label': 'green',
            'properties': {'maxmem': '1535'},
            'devices': {},
            'tags': set(),
            'features': {'service.meminfo-writer': True},
            'template': 'fedora-20-x64',
            'backup_path': None,
            'included_in_backup': False,
        },
        'personal': {
            'klass': 'AppVM',
            'label': 'yellow',
            'properties': {'maxmem': '1535'},
            'devices': {},
            'tags': set(),
            'features': {'service.meminfo-writer': True},
            'template': 'fedora-20-x64',
            'backup_path': None,
            'included_in_backup': False,
        },
        'untrusted': {
            'klass': 'AppVM',
            'label': 'red',
            'properties': {
                'maxmem': '1535',
                'netvm': 'test-testproxy',
                'default_dispvm': 'disp-test-testproxy',
            },
            'devices': {},
            'tags': set(),
            'features': {'service.meminfo-writer': True},
            'template': 'fedora-20-x64',
            'backup_path': None,
            'included_in_backup': False,
        },
        'testproxy2': {
            'klass': 'AppVM',
            'label': 'red',
            'properties': {
                'maxmem': '1535',
                'memory': '200',
                'provides_network': True},
            'devices': {},
            'tags': set(),
            'features': {'service.meminfo-writer': True},
            'template': 'test-template-clone',
            'backup_path': None,
            'included_in_backup': False,
        },
        'test-testproxy': {
            'klass': 'AppVM',
            'label': 'red',
            'properties': {
                'maxmem': '1535',
                'memory': '200',
                'provides_network': True},
            'devices': {},
            'tags': set(),
            'features': {'service.meminfo-writer': True},
            'template': 'fedora-20-x64',
            'backup_path': 'servicevms/test-testproxy',
            'included_in_backup': True,
        },
        'test-testhvm': {
            'klass': 'StandaloneVM',
            'label': 'purple',
            'properties': {'kernel': '', 'virt_mode': 'hvm', 'memory': '512'},
            'devices': {},
            'tags': set(),
            'features': {
                'service.meminfo-writer': False,
                'linux-stubdom': False},
            'template': None,
            'backup_path': 'appvms/test-testhvm',
            'included_in_backup': True,
            'root_size': 2097664,
        },
        'test-work': {
            'klass': 'AppVM',
            'label': 'green',
            'properties': {'maxmem': '1535'},
            'devices': {},
            'tags': set(),
            'features': {'service.meminfo-writer': True},
            'template': 'fedora-20-x64',
            'backup_path': 'appvms/test-work',
            'included_in_backup': True,
        },
        'test-template-clone': {
            'klass': 'TemplateVM',
            'label': 'green',
            'properties': {'maxmem': '1535'},
            'devices': {},
            'tags': set(),
            'features': {
                'service.meminfo-writer': True,
                'qrexec': True,
                'gui': True,
            },
            'template': None,
            'backup_path': 'vm-templates/test-template-clone',
            'included_in_backup': True,
            'root_size': 209715712,
        },
        'test-custom-template-appvm': {
            'klass': 'AppVM',
            'label': 'yellow',
            'properties': {'maxmem': '1535'},
            'devices': {},
            'tags': set(),
            'features': {'service.meminfo-writer': True},
            'template': 'test-template-clone',
            'backup_path': 'appvms/test-custom-template-appvm',
            'included_in_backup': True,
        },
        'test-standalonevm': {
            'klass': 'StandaloneVM',
            'label': 'blue',
            'properties': {'maxmem': '1535'},
            'devices': {},
            'tags': set(),
            'features': {
                'service.meminfo-writer': True,
                'qrexec': True,
                'gui': True,
            },
            'template': None,
            'backup_path': 'appvms/test-standalonevm',
            'included_in_backup': True,
            'root_size': 2097664,
        },
        'test-net': {
            'klass': 'AppVM',
            'label': 'red',
            'properties': {
                'maxmem': '1535',
                'memory': '200',
                'netvm': None,
                'default_dispvm': 'disp-no-netvm',
                'provides_network': True},
            'devices': {
                'pci': {
                    ('dom0', '02_00.0'): {},
                    ('dom0', '03_00.0'): {},
                }
            },
            'tags': set(),
            'features': {
                'service.ntpd': False,
                'service.meminfo-writer': False
            },
            'template': 'fedora-20-x64',
            'backup_path': 'servicevms/test-net',
            'included_in_backup': True,
        },
        'disp-no-netvm': {
            'klass': 'AppVM',
            'label': 'red',
            'properties': {
                'netvm': None,
                'template_for_dispvms': True,
            },
            'devices': {},
            'features': {},
            'tags': set(),
            'template': None,  # default
            'backup_path': None,
            'included_in_backup': True,
        },
        'disp-test-testproxy': {
            'klass': 'AppVM',
            'label': 'red',
            'properties': {
                'netvm': 'test-testproxy',
                'template_for_dispvms': True,
            },
            'devices': {},
            'features': {},
            'tags': set(),
            'template': None,  # default
            'backup_path': None,
            'included_in_backup': True,
        },
    },
    'globals': {
        'default_template': 'fedora-20-x64',
        'default_kernel': '3.7.6-2',
        'default_netvm': 'firewallvm',
        'clockvm': 'netvm',
        'updatevm': 'firewallvm'
    },
}

parsed_qubes_xml_v4 = {
    'domains': {
        'dom0': {
            'klass': 'AdminVM',
            'label': 'black',
            'properties': {},
            'devices': {},
            'tags': set(),
            'features': {},
            'template': None,
            'backup_path': 'dom0-home/user',
            'included_in_backup': True,
        },
        'fedora-25': {
            'klass': 'TemplateVM',
            'label': 'black',
            'properties': {},
            'devices': {},
            'tags': {'created-by-test-work'},
            'features': {
                'gui': '1',
                'qrexec': 'True',
                'updates-available': False
            },
            'template': None,
            'backup_path': None,
            'included_in_backup': False,
        },
        'fedora-25-lvm': {
            'klass': 'TemplateVM',
            'label': 'black',
            'properties': {
                'maxmem': '4000',
            },
            'devices': {},
            'tags': set(),
            'features': {},
            'template': None,
            'backup_path': None,
            'included_in_backup': False,
        },
        'debian-8': {
            'klass': 'TemplateVM',
            'label': 'black',
            'properties': {},
            'devices': {},
            'tags': {'created-by-dom0'},
            'features': {
                'gui': '1',
                'qrexec': 'True',
                'updates-available': False},
            'template': None,
            'backup_path': None,
            'included_in_backup': False,
        },
        'sys-net': {
            'klass': 'AppVM',
            'label': 'red',
            'properties': {
                'virt_mode': 'hvm',
                'kernelopts': 'nopat i8042.nokbd i8042.noaux',
                'maxmem': '300',
                'memory': '300',
                'netvm': None,
                'default_user': 'user',
                'provides_network': 'True'},
            'devices': {
                'pci': {
                    ('dom0', '02_00.0'): {},
                }
            },
            'tags': set(),
            'features': {
                'service.clocksync': '1',
                'service.meminfo-writer': False
            },
            'template': 'fedora-25',
            'backup_path': None,
            'included_in_backup': False,
        },
        'sys-firewall': {
            'klass': 'AppVM',
            'label': 'green',
            'properties': {
                'autostart': 'True',
                'memory': '500',
                'provides_network': 'True'
            },
            'devices': {},
            'tags': set(),
            'features': {},
            'template': 'fedora-25',
            'backup_path': None,
            'included_in_backup': False,
        },
        'test-d8test': {
            'klass': 'AppVM',
            'label': 'gray',
            'properties': {'debug': 'True', 'kernel': None},
            'devices': {},
            'tags': {'created-by-dom0'},
            'features': {},
            'template': 'debian-8',
            'backup_path': 'appvms/test-d8test',
            'included_in_backup': True,
        },
        'fedora-25-dvm': {
            'klass': 'AppVM',
            'label': 'red',
            'properties': {
                'template_for_dispvms': 'True',
                'vcpus': '1',
            },
            'devices': {},
            'tags': set(),
            'features': {
                'internal': '1', 'service.meminfo-writer': '1'},
            'template': 'fedora-25',
            'backup_path': None,
            'included_in_backup': False,
        },
        'fedora-25-clone-dvm': {
            'klass': 'AppVM',
            'label': 'red',
            'properties': {
                'vcpus': '1',
                'template_for_dispvms': 'True',
            },
            'devices': {},
            'tags': set(),
            'features': {
                'internal': '1', 'service.meminfo-writer': '1'},
            'template': 'test-fedora-25-clone',
            'backup_path': None,
            'included_in_backup': False,
        },
        'vault': {
            'klass': 'AppVM',
            'label': 'black',
            'properties': {'virt_mode': 'pv', 'maxmem': '1536', 'netvm': None},
            'devices': {},
            'tags': set(),
            'features': {},
            'template': 'fedora-25',
            'backup_path': None,
            'included_in_backup': False,
        },
        'personal': {
            'klass': 'AppVM',
            'label': 'yellow',
            'properties': {'netvm': 'sys-firewall'},
            'devices': {},
            'tags': set(),
            'features': {
                'feat1': '1',
                'feat2': False,
                'feat32': '1',
                'featdis': False,
                'xxx': '1'
            },
            'template': 'fedora-25',
            'backup_path': None,
            'included_in_backup': False,
        },
        'untrusted': {
            'klass': 'AppVM',
            'label': 'red',
            'properties': {
                'netvm': None,
                'backup_timestamp': '1474318497',
                'default_dispvm': 'fedora-25-clone-dvm',
            },
            'devices': {},
            'tags': set(),
            'features': {'service.meminfo-writer': '1'},
            'template': 'fedora-25',
            'backup_path': None,
            'included_in_backup': False,
        },
        'sys-usb': {
            'klass': 'AppVM',
            'label': 'red',
            'properties': {
                'autostart': 'True',
                'maxmem': '400',
                'provides_network': 'True',
            },
            'devices': {},
            'tags': set(),
            'features': {
                'service.meminfo-writer': False,
                'service.network-manager': False,
            },
            'template': 'fedora-25',
            'backup_path': None,
            'included_in_backup': False,
        },
        'test-proxy': {
            'klass': 'AppVM',
            'label': 'red',
            'properties': {'netvm': 'sys-net', 'provides_network': 'True'},
            'devices': {},
            'tags': {'created-by-dom0'},
            'features': {},
            'template': 'debian-8',
            'backup_path': 'appvms/test-proxy',
            'included_in_backup': True,
        },
        'test-hvm': {
            'klass': 'StandaloneVM',
            'label': 'purple',
            'properties': {
                'kernel': None,
                'virt_mode': 'hvm',
                'maxmem': '4000'},
            'devices': {},
            'tags': set(),
            'features': {'service.meminfo-writer': False},
            'template': None,
            'backup_path': 'appvms/test-hvm',
            'included_in_backup': True,
            'root_size': 2097664,
        },
        'test-work': {
            'klass': 'AppVM',
            'label': 'green',
            'properties': {
                'ip': '192.168.0.1',
                'maxmem': '4000',
                'memory': '400'},
            'devices': {},
            'tags': {'tag1', 'tag2'},
            'features': {'service.meminfo-writer': '1'},
            'template': 'fedora-25',
            'backup_path': 'appvms/test-work',
            'included_in_backup': True,
        },
        'test-fedora-25-clone': {
            'klass': 'TemplateVM',
            'label': 'black',
            'properties': {'maxmem': '4000'},
            'devices': {},
            'tags': set(),
            'features': {'service.meminfo-writer': '1'},
            'template': None,
            'backup_path': 'vm-templates/test-fedora-25-clone',
            'included_in_backup': True,
        },
        'test-custom-template-appvm': {
            'klass': 'AppVM',
            'label': 'yellow',
            'properties': {'debug': 'True', 'kernel': None},
            'devices': {},
            'tags': {'created-by-dom0'},
            'features': {},
            'template': 'test-fedora-25-clone',
            'backup_path': 'appvms/test-custom-template-appvm',
            'included_in_backup': True,
        },
        'test-standalonevm': {
            'klass': 'StandaloneVM',
            'label': 'blue',
            'properties': {'maxmem': '4000'},
            'devices': {},
            'tags': set(),
            'features': {},
            'template': None,
            'backup_path': 'appvms/test-standalonevm',
            'included_in_backup': True,
            'root_size': 2097664,
        },
        'test-net': {
            'klass': 'AppVM',
            'label': 'red',
            'properties': {
                'maxmem': '300',
                'memory': '300',
                'netvm': None,
                'provides_network': 'True'
            },
            'devices': {
                'pci': {
                    ('dom0', '03_00.0'): {},
                }
            },
            'tags': set(),
            'features': {
                'service.ntpd': False,
                'service.meminfo-writer': False
            },
            'template': 'fedora-25',
            'backup_path': 'appvms/test-net',
            'included_in_backup': True,
        },
    },
    'globals': {
        'default_template': 'fedora-25',
        'default_kernel': '4.9.31-17',
        'default_netvm': 'sys-firewall',
        'default_dispvm': 'fedora-25-dvm',
        #'default_fw_netvm': 'sys-net',
        'clockvm': 'sys-net',
        'updatevm': 'sys-firewall'
    },
}


class TC_00_QubesXML(qubesadmin.tests.QubesTestCase):

    def assertCorrectlyConverted(self, backup_app, expected_data):
        self.assertCountEqual(backup_app.domains.keys(),
            expected_data['domains'].keys())
        for vm in expected_data['domains']:
            self.assertEqual(backup_app.domains[vm].name, vm)
            self.assertEqual(backup_app.domains[vm].properties,
                expected_data['domains'][vm]['properties'], vm)
            for devtype in expected_data['domains'][vm]['devices']:
                self.assertEqual(backup_app.domains[vm].devices[devtype],
                    expected_data['domains'][vm]['devices'][devtype], vm)
            self.assertEqual(backup_app.domains[vm].tags,
                expected_data['domains'][vm]['tags'], vm)
            self.assertEqual(backup_app.domains[vm].features,
                expected_data['domains'][vm]['features'], vm)
            self.assertEqual(backup_app.domains[vm].template,
                expected_data['domains'][vm]['template'], vm)
            self.assertEqual(backup_app.domains[vm].klass,
                expected_data['domains'][vm]['klass'], vm)
            self.assertEqual(backup_app.domains[vm].label,
                expected_data['domains'][vm]['label'], vm)
            self.assertEqual(backup_app.domains[vm].backup_path,
                expected_data['domains'][vm]['backup_path'], vm)
            self.assertEqual(backup_app.domains[vm].included_in_backup,
                expected_data['domains'][vm]['included_in_backup'], vm)

        self.assertEqual(backup_app.globals, expected_data['globals'])

    def test_000_qubes_xml_r2(self):
        xml_path = importlib.resources.files("qubesadmin") / "tests/backup/v3-qubes.xml"
        with tempfile.NamedTemporaryFile() as qubes_xml:
            qubes_xml.file.write(xml_path.read_bytes())
            backup_app = qubesadmin.backup.core2.Core2Qubes(qubes_xml.name)
        self.assertCorrectlyConverted(backup_app, parsed_qubes_xml_r2)

    def test_010_qubes_xml_r4(self):
        self.maxDiff = None
        xml_path = importlib.resources.files("qubesadmin") / "tests/backup/v4-qubes.xml"
        with tempfile.NamedTemporaryFile() as qubes_xml:
            qubes_xml.file.write(xml_path.read_bytes())
            backup_app = qubesadmin.backup.core3.Core3Qubes(qubes_xml.name)
        self.assertCorrectlyConverted(backup_app, parsed_qubes_xml_v4)

# backup code use multiprocessing, synchronize with main process
class AppProxy(object):
    def __init__(self, app, sync_queue, delay_stream=0):
        self._app = app
        self._sync_queue = sync_queue
        self._delay_stream = delay_stream
        self.cache_enabled = False

    def qubesd_call(self, dest, method, arg=None, payload=None,
            payload_stream=None):
        if payload_stream:
            time.sleep(self._delay_stream)
            signature_bin = payload_stream.read(512)
            payload = signature_bin.split(b'\0', 1)[0]
            subprocess.call(['cat'], stdin=payload_stream,
                stdout=subprocess.DEVNULL)
            payload_stream.close()
        self._sync_queue.put((dest, method, arg, payload))
        return self._app.qubesd_call(dest, method, arg, payload)


class MockVolume(qubesadmin.storage.Volume):
    def __init__(self, import_data_queue, delay_stream, *args, **kwargs):
        super(MockVolume, self).__init__(*args, **kwargs)
        self.app = AppProxy(self.app, import_data_queue,
            delay_stream=delay_stream)

class MockFirewall(qubesadmin.firewall.Firewall):
    def __init__(self, import_data_queue, *args, **kwargs):
        super(MockFirewall, self).__init__(*args, **kwargs)
        self.vm.app = AppProxy(self.vm.app, import_data_queue)


@unittest.skipUnless(os.environ.get('ENABLE_SLOW_TESTS', False),
    'Set ENABLE_SLOW_TESTS=1 environment variable')
class TC_10_BackupCompatibility(qubesadmin.tests.backup.BackupTestCase):

    storage_pool = None

    def tearDown(self):
        super(TC_10_BackupCompatibility, self).tearDown()

    def create_whitelisted_appmenus(self, filename):
        with open(filename, "w") as f:
            f.write("gnome-terminal.desktop\n")
            f.write("nautilus.desktop\n")
            f.write("firefox.desktop\n")
            f.write("mozilla-thunderbird.desktop\n")
            f.write("libreoffice-startcenter.desktop\n")

    def create_appmenus(self, dir, template, list):
        for name in list:
            with open(os.path.join(dir, name + ".desktop"), "w") as f:
                f.write(template.format(name=name, comment=name, command=name))

    def create_private_img(self, filename, sparse=True):
        signature = '/'.join(os.path.splitext(filename)[0].split('/')[-2:])
        if sparse:
            self.create_sparse(filename, 2*2**20, signature=signature.encode())
        else:
            self.create_full_image(filename, 2 * 2 ** 30,
                signature=signature.encode())
        #subprocess.check_call(["/usr/sbin/mkfs.ext4", "-q", "-F", filename])

    def create_volatile_img(self, filename):
        self.create_sparse(filename, int(11.5*2**20))
        # here used to be sfdisk call with "0,1024,S\n,10240,L\n" input,
        # but since sfdisk folks like to change command arguments in
        # incompatible way, have an partition table verbatim here
        ptable = (
            '\x00\x00\x00\x00\x00\x00\x00\x00\xab\x39\xd5\xd4\x00\x00\x20\x00'
            '\x00\x21\xaa\x82\x82\x28\x08\x00\x00\x00\x00\x00\x00\x20\xaa\x00'
            '\x82\x29\x15\x83\x9c\x79\x08\x00\x00\x20\x00\x00\x01\x40\x00\x00'
            '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xaa\x55'
        )
        with open(filename, 'r+') as f:
            f.seek(0x1b0)
            f.write(ptable)

        # TODO: mkswap

    def fullpath(self, name):
        return os.path.join(self.backupdir, name)

    def create_v1_files(self, r2b2=False):
        appmenus_list = [
            "firefox", "gnome-terminal", "evince", "evolution",
            "mozilla-thunderbird", "libreoffice-startcenter", "nautilus",
            "gedit", "gpk-update-viewer", "gpk-application"
        ]

        os.mkdir(self.fullpath("appvms"))
        os.mkdir(self.fullpath("servicevms"))
        os.mkdir(self.fullpath("vm-templates"))

        # normal AppVM, with firewall
        os.mkdir(self.fullpath("appvms/test-work"))
        self.create_whitelisted_appmenus(self.fullpath(
            "appvms/test-work/whitelisted-appmenus.list"))
        os.symlink("/usr/share/qubes/icons/green.png",
                   self.fullpath("appvms/test-work/icon.png"))
        self.create_private_img(self.fullpath("appvms/test-work/private.img"))
        with open(self.fullpath("appvms/test-work/firewall.xml"), "wb") as \
                f_firewall:
            xml_path = importlib.resources.files("qubesadmin") / "tests/backup/v3-firewall.xml"
            f_firewall.write(xml_path.read_bytes())

        # StandaloneVM
        os.mkdir(self.fullpath("appvms/test-standalonevm"))
        self.create_whitelisted_appmenus(self.fullpath(
            "appvms/test-standalonevm/whitelisted-appmenus.list"))
        os.symlink("/usr/share/qubes/icons/blue.png",
                   self.fullpath("appvms/test-standalonevm/icon.png"))
        self.create_private_img(self.fullpath(
            "appvms/test-standalonevm/private.img"))
        self.create_sparse(
            self.fullpath("appvms/test-standalonevm/root.img"), 10*2**30)
        self.fill_image(self.fullpath("appvms/test-standalonevm/root.img"),
            1024*1024, True,
            signature=b'test-standalonevm/root')
        os.mkdir(self.fullpath("appvms/test-standalonevm/apps.templates"))
        self.create_appmenus(self.fullpath("appvms/test-standalonevm/apps"
                                           ".templates"),
                             APPTEMPLATE_R2B2,
                             appmenus_list)
        os.mkdir(self.fullpath("appvms/test-standalonevm/kernels"))
        for k_file in ["initramfs", "vmlinuz", "modules.img"]:
            self.fill_image(self.fullpath("appvms/test-standalonevm/kernels/"
            + k_file), 1024*1024)

        # VM based on custom template
        subprocess.check_call(
            ["/bin/cp", "-a", self.fullpath("appvms/test-work"),
                        self.fullpath("appvms/test-custom-template-appvm")])
        # override for correct signature
        self.create_private_img(
            self.fullpath("appvms/test-custom-template-appvm/private.img"))

        # HVM
        if r2b2:
            subprocess.check_call(
                ["/bin/cp", "-a", self.fullpath("appvms/test-standalonevm"),
                            self.fullpath("appvms/test-testhvm")])
            # override for correct signature
            self.create_private_img(
                self.fullpath("appvms/test-testhvm/private.img"))
            self.fill_image(self.fullpath("appvms/test-testhvm/root.img"),
                1024*1024, True,
                signature=b'test-testhvm/root')

        # ProxyVM
        os.mkdir(self.fullpath("servicevms/test-testproxy"))
        self.create_whitelisted_appmenus(self.fullpath(
            "servicevms/test-testproxy/whitelisted-appmenus.list"))
        self.create_private_img(
            self.fullpath("servicevms/test-testproxy/private.img"))

        # NetVM
        os.mkdir(self.fullpath("servicevms/test-net"))
        self.create_whitelisted_appmenus(self.fullpath(
            "servicevms/test-net/whitelisted-appmenus.list"))
        self.create_private_img(
            self.fullpath("servicevms/test-net/private.img"))

        # Custom template
        os.mkdir(self.fullpath("vm-templates/test-template-clone"))
        self.create_private_img(
            self.fullpath("vm-templates/test-template-clone/private.img"))
        self.create_sparse(self.fullpath(
            "vm-templates/test-template-clone/root-cow.img"), 10*2**20)
        self.create_sparse(self.fullpath(
            "vm-templates/test-template-clone/root.img"), 10*2**20)
        self.fill_image(self.fullpath(
            "vm-templates/test-template-clone/root.img"), 100*2**20, True,
            signature=b'test-template-clone/root')
        self.create_volatile_img(self.fullpath(
            "vm-templates/test-template-clone/volatile.img"))
        subprocess.check_call([
            "/bin/tar", "cS",
            "-f", self.fullpath(
                "vm-templates/test-template-clone/clean-volatile.img.tar"),
            "-C", self.fullpath("vm-templates/test-template-clone"),
            "volatile.img"])
        self.create_whitelisted_appmenus(self.fullpath(
            "vm-templates/test-template-clone/whitelisted-appmenus.list"))
        self.create_whitelisted_appmenus(self.fullpath(
            "vm-templates/test-template-clone/vm-whitelisted-appmenus.list"))
        if r2b2:
            self.create_whitelisted_appmenus(self.fullpath(
                "vm-templates/test-template-clone/netvm-whitelisted-appmenus"
                ".list"))
        os.symlink("/usr/share/qubes/icons/green.png",
                   self.fullpath("vm-templates/test-template-clone/icon.png"))
        os.mkdir(
            self.fullpath("vm-templates/test-template-clone/apps.templates"))
        self.create_appmenus(
            self.fullpath("vm-templates/test-template-clone/apps.templates"),
            APPTEMPLATE_R2B2,
            appmenus_list)
        os.mkdir(self.fullpath("vm-templates/test-template-clone/apps"))
        self.create_appmenus(
            self.fullpath("vm-templates/test-template-clone/apps"),
            APPTEMPLATE_R2B2.replace("%VMNAME%", "test-template-clone")
            .replace("%VMDIR%", self.fullpath(
                "vm-templates/test-template-clone")),
            appmenus_list)

        self.create_dom0_files()

    dom0_dirs = ('Downloads', 'Pictures', 'Documents', '.config', '.local')
    dom0_files = ('.bash_history', 'some-file.txt',
        'Pictures/another-file.png')

    def create_dom0_files(self):
        # dom0 files
        os.mkdir(self.fullpath('dom0-home'))
        os.mkdir(self.fullpath('dom0-home/user'))
        for d in self.dom0_dirs:
            os.mkdir(self.fullpath('dom0-home/user/' + d))
        for f in self.dom0_files:
            with open(self.fullpath('dom0-home/user/' + f), 'w') as ff:
                ff.write('some content')

    def assertDirectoryExists(self, path):
        if not os.path.exists(path):
            self.fail(path + ' missing')
        if not os.path.isdir(path):
            self.fail(path + ' is not a directory')

    def assertFileExists(self, path):
        if not os.path.exists(path):
            self.fail(path + ' missing')
        if not os.path.isfile(path):
            self.fail(path + ' is not a file')

    def assertDom0Restored(self, timestamp):
        expected_dir = os.path.expanduser(
            '~/home-restore-' + timestamp + '/dom0-home/user')
        self.assertTrue(os.path.exists(expected_dir))
        for d in self.dom0_dirs:
            self.assertDirectoryExists(os.path.join(expected_dir, d))
        for f in self.dom0_files:
            self.assertFileExists(os.path.join(expected_dir, f))
        # cleanup
        shutil.rmtree(expected_dir)

    def create_v4_files(self):
        appmenus_list = [
            "firefox", "gnome-terminal", "evince", "evolution",
            "mozilla-thunderbird", "libreoffice-startcenter", "nautilus",
            "gedit", "gpk-update-viewer", "gpk-application"
        ]

        os.mkdir(self.fullpath("appvms"))
        os.mkdir(self.fullpath("vm-templates"))

        # normal AppVMs
        for vm in ('test-work', 'test-d8test', 'test-proxy',
                'test-custom-template-appvm', 'test-net'):
            os.mkdir(self.fullpath('appvms/{}'.format(vm)))
            self.create_whitelisted_appmenus(self.fullpath(
                'appvms/{}/whitelisted-appmenus.list'.format(vm)))
            self.create_private_img(self.fullpath('appvms/{}/private.img'.format(
                vm)))

        # setup firewall only on one VM
        with open(self.fullpath("appvms/test-work/firewall.xml"), "wb") as \
                f_firewall:
            xml_path = importlib.resources.files("qubesadmin") / "tests/backup/v4-firewall.xml"
            f_firewall.write(xml_path.read_bytes())

        # StandaloneVMs
        for vm in ('test-standalonevm', 'test-hvm'):
            os.mkdir(self.fullpath('appvms/{}'.format(vm)))
            self.create_whitelisted_appmenus(self.fullpath(
                'appvms/{}/whitelisted-appmenus.list'.format(vm)))
            self.create_private_img(self.fullpath(
                'appvms/{}/private.img'.format(vm)))
            self.create_sparse(
                self.fullpath('appvms/{}/root.img'.format(vm)), 10*2**30)
            self.fill_image(self.fullpath('appvms/{}/root.img'.format(vm)),
                1024*1024, True,
                signature='{}/root'.format(vm).encode())

        # only for Linux one
        os.mkdir(self.fullpath('appvms/test-standalonevm/apps.templates'))
        self.create_appmenus(
            self.fullpath('appvms/test-standalonevm/apps.templates'),
            APPTEMPLATE_R2B2,
            appmenus_list)

        # Custom template
        os.mkdir(self.fullpath("vm-templates/test-fedora-25-clone"))
        self.create_private_img(
            self.fullpath("vm-templates/test-fedora-25-clone/private.img"))
        self.create_sparse(self.fullpath(
            "vm-templates/test-fedora-25-clone/root.img"), 10*2**20)
        self.fill_image(self.fullpath(
            "vm-templates/test-fedora-25-clone/root.img"), 1*2**20, True,
            signature=b'test-fedora-25-clone/root')
        self.create_volatile_img(self.fullpath(
            "vm-templates/test-fedora-25-clone/volatile.img"))
        self.create_whitelisted_appmenus(self.fullpath(
            "vm-templates/test-fedora-25-clone/whitelisted-appmenus.list"))
        self.create_whitelisted_appmenus(self.fullpath(
            "vm-templates/test-fedora-25-clone/vm-whitelisted-appmenus.list"))
        os.mkdir(
            self.fullpath("vm-templates/test-fedora-25-clone/apps.templates"))
        self.create_appmenus(
            self.fullpath("vm-templates/test-fedora-25-clone/apps.templates"),
            APPTEMPLATE_R2B2,
            appmenus_list)
        os.mkdir(self.fullpath("vm-templates/test-fedora-25-clone/apps"))
        self.create_appmenus(
            self.fullpath("vm-templates/test-fedora-25-clone/apps"),
            APPTEMPLATE_R2B2.replace("%VMNAME%", "test-fedora-25-clone")
            .replace("%VMDIR%", self.fullpath(
                "vm-templates/test-fedora-25-clone")),
            appmenus_list)

        self.create_dom0_files()

    def scrypt_encrypt(self, f_name, output_name=None, password='qubes',
            basedir=None):
        if basedir is None:
            basedir = self.backupdir
        if output_name is None:
            output_name = f_name + '.enc'
        if f_name == 'backup-header':
            scrypt_pass = 'backup-header!' + password
        else:
            scrypt_pass = '20161020T123455-1234!{}!{}'.format(f_name, password)
        p = subprocess.Popen(['scrypt', 'enc', '-P', '-t', '0.1',
            os.path.join(basedir, f_name), os.path.join(basedir, output_name)],
            stdin=subprocess.PIPE)
        p.communicate(scrypt_pass.encode())
        assert p.wait() == 0
        return output_name

    def calculate_hmac(self, f_name, algorithm="sha512", password="qubes"):
        with open(self.fullpath(f_name), "r") as f_data:
            with open(self.fullpath(f_name+".hmac"), "w") as f_hmac:
                subprocess.check_call(
                    ["openssl", "dgst", "-"+algorithm, "-hmac", password],
                    stdin=f_data, stdout=f_hmac)

    def append_backup_stream(self, f_name, stream, basedir=None):
        if not basedir:
            basedir = self.backupdir
        subprocess.check_call(["tar", "-cO", "--posix", "-C", basedir,
                               f_name],
                              stdout=stream)

    def handle_v3_file(self, f_name, subdir, stream, compressed=True,
                       encrypted=True):
        # create inner archive
        tar_cmdline = ["tar", "-Pc", '--sparse',
               '-C', self.fullpath(os.path.dirname(f_name)),
               '--xform', 's:^%s:%s\\0:' % (
                   os.path.basename(f_name),
                   subdir),
               os.path.basename(f_name)
               ]
        if compressed:
            tar_cmdline.insert(-1, "--use-compress-program=%s" % "gzip")
        tar = subprocess.Popen(tar_cmdline, stdout=subprocess.PIPE)
        if encrypted:
            encryptor = subprocess.Popen(
                ["openssl", "enc", "-e", "-aes-256-cbc",
                 "-md", "MD5", "-pass", "pass:qubes"],
                stdin=tar.stdout,
                stdout=subprocess.PIPE)
            tar.stdout.close()
            data = encryptor.stdout
        else:
            data = tar.stdout
            encryptor = None

        stage1_dir = self.fullpath(os.path.join("stage1", subdir))
        if not os.path.exists(stage1_dir):
            os.makedirs(stage1_dir)
        subprocess.check_call(["split", "--numeric-suffixes",
                               "--suffix-length=3",
                               "--bytes="+str(100*1024*1024), "-",
                               os.path.join(stage1_dir,
                                            os.path.basename(f_name+"."))],
                              stdin=data)
        data.close()
        tar.wait()
        if encryptor:
            encryptor.wait()

        for part in sorted(os.listdir(stage1_dir)):
            if not re.match(
                    r"^{}.[0-9][0-9][0-9]$".format(os.path.basename(f_name)),
                    part):
                continue
            part_with_dir = os.path.join(subdir, part)
            self.calculate_hmac(os.path.join("stage1", part_with_dir))
            self.append_backup_stream(part_with_dir, stream,
                                      basedir=self.fullpath("stage1"))
            self.append_backup_stream(part_with_dir+".hmac", stream,
                                      basedir=self.fullpath("stage1"))

    def handle_v4_file(self, f_name, subdir, stream, compressed="gzip"):
        # create inner archive
        tar_cmdline = ["tar", "-Pc", '--sparse',
               '-C', self.fullpath(os.path.dirname(f_name)),
               '--xform', 's:^%s:%s\\0:' % (
                   os.path.basename(f_name),
                   subdir),
               os.path.basename(f_name)
               ]
        if compressed and isinstance(compressed, str):
            tar_cmdline.insert(-1, "--use-compress-program=%s" % compressed)
        elif compressed:
            tar_cmdline.insert(-1, "--use-compress-program=%s" % "gzip")
        tar = subprocess.Popen(tar_cmdline, stdout=subprocess.PIPE)
        data = tar.stdout

        stage1_dir = self.fullpath(os.path.join("stage1", subdir))
        if not os.path.exists(stage1_dir):
            os.makedirs(stage1_dir)
        subprocess.check_call(["split", "--numeric-suffixes",
                               "--suffix-length=3",
                               "--bytes="+str(100*1024*1024), "-",
                               os.path.join(stage1_dir,
                                            os.path.basename(f_name+"."))],
                              stdin=data)
        data.close()
        tar.wait()

        for part in sorted(os.listdir(stage1_dir)):
            if not re.match(
                    r"^{}.[0-9][0-9][0-9]$".format(os.path.basename(f_name)),
                    part):
                continue
            part_with_dir = os.path.join(subdir, part)
            f_name_enc = self.scrypt_encrypt(part_with_dir,
                basedir=self.fullpath('stage1'))
            self.append_backup_stream(f_name_enc, stream,
                                      basedir=self.fullpath("stage1"))

    def create_v3_backup(self, encrypted=True, compressed=True):
        """
        Create "backup format 3" backup - used in R2 and R3.0

        :param encrypted: Should the backup be encrypted
        :param compressed: Should the backup be compressed
        :return:
        """
        output = open(self.fullpath("backup.bin"), "w")
        with open(self.fullpath("backup-header"), "w") as f:
            f.write(BACKUP_HEADER_R2.format(
                encrypted=str(encrypted),
                compressed=str(compressed)
            ))
        self.calculate_hmac("backup-header")
        self.append_backup_stream("backup-header", output)
        self.append_backup_stream("backup-header.hmac", output)
        with open(self.fullpath("qubes.xml"), "wb") as f:
            xml_path = importlib.resources.files("qubesadmin") / "tests/backup/v3-qubes.xml"

            qubesxml = xml_path.read_bytes()
            if encrypted:
                for vmname, subdir in MANGLED_SUBDIRS_R2.items():
                    qubesxml = re.sub(r"[a-z-]*/{}".format(vmname).encode(),
                                      subdir.encode(), qubesxml)
                f.write(qubesxml)
            else:
                f.write(qubesxml)

        self.handle_v3_file("qubes.xml", "", output, encrypted=encrypted,
                            compressed=compressed)

        self.create_v1_files(r2b2=True)
        for vm_type in ["appvms", "servicevms"]:
            for vm_name in os.listdir(self.fullpath(vm_type)):
                vm_dir = os.path.join(vm_type, vm_name)
                for f_name in os.listdir(self.fullpath(vm_dir)):
                    if encrypted:
                        subdir = MANGLED_SUBDIRS_R2[vm_name]
                    else:
                        subdir = vm_dir
                    self.handle_v3_file(
                        os.path.join(vm_dir, f_name),
                        subdir+'/', output,
                        compressed=compressed,
                        encrypted=encrypted)

        for vm_name in os.listdir(self.fullpath("vm-templates")):
            vm_dir = os.path.join("vm-templates", vm_name)
            if encrypted:
                subdir = MANGLED_SUBDIRS_R2[vm_name]
            else:
                subdir = vm_dir
            self.handle_v3_file(
                os.path.join(vm_dir, "."),
                subdir+'/', output,
                compressed=compressed,
                encrypted=encrypted)

        self.handle_v3_file(
            'dom0-home/user',
            'dom0-home/', output,
            compressed=compressed,
            encrypted=encrypted)

        output.close()

    def create_v4_backup(self, compressed="gzip", big=False):
        """
        Create "backup format 4" backup - used in R4.0

        :param compressed: Should the backup be compressed
        :param big: Should the backup include big(ish) VM?
        :return:
        """
        output = open(self.fullpath("backup.bin"), "w")
        with open(self.fullpath("backup-header"), "w") as f:
            f.write(BACKUP_HEADER_R4.format(
                compressed=str(bool(compressed)),
                compression_filter=(compressed if compressed else "gzip")
            ))
        self.scrypt_encrypt("backup-header", output_name='backup-header.hmac')
        self.append_backup_stream("backup-header", output)
        self.append_backup_stream("backup-header.hmac", output)
        with open(self.fullpath("qubes.xml"), "wb") as f:
            xml_path = importlib.resources.files("qubesadmin") / "tests/backup/v4-qubes.xml"

            qubesxml = xml_path.read_bytes()
            for vmname, subdir in MANGLED_SUBDIRS_R4.items():
                qubesxml = re.sub(
                    r'backup-path">[a-z-]*/{}'.format(vmname).encode(),
                    ('backup-path">' + subdir).encode(),
                    qubesxml)
            f.write(qubesxml)

        self.handle_v4_file("qubes.xml", "", output, compressed=compressed)

        self.create_v4_files()
        if big:
            # make one AppVM non-sparse
            self.create_private_img(
                self.fullpath('appvms/test-work/private.img'),
                sparse=False)

        for vm_type in ["appvms", "vm-templates"]:
            for vm_name in os.listdir(self.fullpath(vm_type)):
                vm_dir = os.path.join(vm_type, vm_name)
                for f_name in os.listdir(self.fullpath(vm_dir)):
                    subdir = MANGLED_SUBDIRS_R4[vm_name]
                    self.handle_v4_file(
                        os.path.join(vm_dir, f_name),
                        subdir+'/', output, compressed=compressed)

        self.handle_v4_file(
            'dom0-home/user',
            'dom0-home/', output,
            compressed=compressed)

        output.close()

    def setup_expected_calls(self, parsed_qubes_xml, templates_map=None):
        if templates_map is None:
            templates_map = {}

        extra_vm_list_lines = []
        for name, vm in parsed_qubes_xml['domains'].items():
            if not vm['included_in_backup']:
                continue

            if name == 'dom0':
                continue

            if self.storage_pool:
                self.app.expected_calls[
                    ('dom0', 'admin.vm.CreateInPool.' + vm['klass'],
                     templates_map.get(vm['template'], vm['template']),
                    'name={} label={} pool={}'.format(
                        name, vm['label'], self.storage_pool).encode())] = \
                    b'0\0'
            else:
                self.app.expected_calls[
                    ('dom0', 'admin.vm.Create.' + vm['klass'],
                     templates_map.get(vm['template'], vm['template']),
                    'name={} label={}'.format(name, vm['label']).encode())] =\
                    b'0\0'
            extra_vm_list_lines.append(
                '{} class={} state=Halted\n'.format(name, vm['klass']).encode())
            if vm['backup_path']:
                self.app.expected_calls[
                    (name, 'admin.vm.volume.List', None, None)] = \
                    b'0\0root\nprivate\nvolatile\n'
                if vm['klass'] == 'AppVM':
                    self.app.expected_calls[
                        (name, 'admin.vm.volume.Info', 'root', None)] = \
                        b'0\0' \
                        b'pool=default\n' \
                        b'vid=' + name.encode() + b'/root\n' \
                        b'size=1024\n' \
                        b'usage=512\n' \
                        b'rw=False\n' \
                        b'snap_on_start=True\n' \
                        b'save_on_stop=False\n' \
                        b'source=\n' \
                        b'internal=True\n' \
                        b'revisions_to_keep=3\n'
                else:
                    self.app.expected_calls[
                        (name, 'admin.vm.volume.Info', 'root', None)] = \
                        b'0\0' \
                        b'pool=default\n' \
                        b'vid=' + name.encode() + b'/root\n' \
                        b'size=1024\n' \
                        b'usage=512\n' \
                        b'rw=True\n' \
                        b'snap_on_start=False\n' \
                        b'save_on_stop=True\n' \
                        b'internal=True\n' \
                        b'revisions_to_keep=3\n'
                    self.app.expected_calls[
                        (name, 'admin.vm.volume.ImportWithSize', 'root',
                        name.encode() + b'/root')] = \
                        b'0\0'

                self.app.expected_calls[
                    (name, 'admin.vm.volume.Info', 'private', None)] = \
                    b'0\0' \
                    b'pool=default\n' \
                    b'vid=' + name.encode() + b'/private\n' \
                    b'size=1024\n' \
                    b'usage=512\n' \
                    b'rw=True\n' \
                    b'snap_on_start=False\n' \
                    b'save_on_stop=True\n' \
                    b'revisions_to_keep=3\n'
                self.app.expected_calls[
                    (name, 'admin.vm.volume.ImportWithSize', 'private',
                    name.encode() + b'/private')] = \
                    b'0\0'
                self.app.expected_calls[
                    (name, 'admin.vm.volume.Info', 'volatile', None)] = \
                    b'0\0' \
                    b'pool=default\n' \
                    b'vid=' + name.encode() + b'/root\n' \
                    b'size=1024\n' \
                    b'usage=512\n' \
                    b'rw=True\n' \
                    b'snap_on_start=False\n' \
                    b'save_on_stop=False\n' \
                    b'revisions_to_keep=3\n'

            for prop, value in vm['properties'].items():
                self.app.expected_calls[
                    (name, 'admin.vm.property.Set', prop,
                    str(value).encode() if value is not None else b'')] = b'0\0'

            for bus, devices in vm['devices'].items():
                for (backend_domain, ident), options in devices.items():
                    all_options = options.copy()
                    all_options['persistent'] = True
                    encoded_options = ' '.join('{}={}'.format(key, value) for
                        key, value in all_options.items()).encode()
                    self.app.expected_calls[
                        (name, 'admin.vm.device.{}.Attach'.format(bus),
                        '{}+{}'.format(backend_domain, ident),
                        encoded_options)] = b'0\0'

            for feature, value in vm['features'].items():
                if value is False:
                    value = ''
                elif value is True:
                    value = '1'
                self.app.expected_calls[
                    (name, 'admin.vm.feature.Set', feature,
                    str(value).encode())] = b'0\0'

            for tag in vm['tags']:
                if tag.startswith('created-by-'):
                    self.app.expected_calls[
                        (name, 'admin.vm.tag.Set', tag, None)] = b''
                    self.app.expected_calls[
                        (name, 'admin.vm.tag.Get', tag, None)] = b'0\0001'
                else:
                    self.app.expected_calls[
                        (name, 'admin.vm.tag.Set', tag, None)] = b'0\0'

            if vm['backup_path']:
                appmenus = (
                    b'gnome-terminal.desktop\n'
                    b'nautilus.desktop\n'
                    b'firefox.desktop\n'
                    b'mozilla-thunderbird.desktop\n'
                    b'libreoffice-startcenter.desktop\n'
                )
                self.app.expected_calls[
                    (name, 'appmenus', None, appmenus)] = b'0\0'

        orig_admin_vm_list = self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)]
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            [orig_admin_vm_list] + \
            [orig_admin_vm_list + b''.join(extra_vm_list_lines)] * \
            len(extra_vm_list_lines)

    def mock_appmenus(self, queue, vm, stream):
        queue.put((vm.name, 'appmenus', None, stream.read()))

    def cleanup_tmpdir(self, tmpdir: tempfile.TemporaryDirectory):
        subprocess.run(['sudo', 'umount', tmpdir.name], check=True)
        tmpdir.cleanup()

    def create_limited_tmpdir(self, size):
        d = tempfile.TemporaryDirectory()
        subprocess.run(['sudo', 'mount', '-t', 'tmpfs', 'none', d.name, '-o',
                        'size={}'.format(size)], check=True)
        self.addCleanup(self.cleanup_tmpdir, d)
        return d.name

    def test_210_r2(self):
        self.create_v3_backup(False)
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0dom0 class=AdminVM state=Running\n'
            b'fedora-25 class=TemplateVM state=Halted\n'
            b'testvm class=AppVM state=Running\n'
        )
        self.app.expected_calls[
            ('dom0', 'admin.property.Get', 'default_template', None)] = \
            b'0\0default=no type=vm fedora-25'
        self.setup_expected_calls(parsed_qubes_xml_r2, templates_map={
            'fedora-20-x64': 'fedora-25'
        })
        firewall_data = (
            'action=accept specialtarget=dns\n'
            'action=accept proto=icmp\n'
            'action=accept proto=tcp dstports=22-22\n'
            'action=accept proto=tcp dstports=9418-9418\n'
            'action=accept proto=tcp dst4=192.168.0.1/32 dstports=1234-1234\n'
            'action=accept proto=tcp dsthost=fedorahosted.org dstports=443-443\n'
            'action=accept proto=tcp dsthost=xenbits.xen.org dstports=80-80\n'
            'action=drop\n'
        )
        self.app.expected_calls[
            ('test-work', 'admin.vm.firewall.Set', None,
            firewall_data.encode())] = b'0\0'
        self.app.expected_calls[
            ('test-custom-template-appvm', 'admin.vm.firewall.Set', None,
            firewall_data.encode())] = b'0\0'
        qubesd_calls_queue = multiprocessing.Queue()

        dummy_timestamp = time.strftime("test-%Y-%m-%d-%H%M%S")
        patches = [
            mock.patch('qubesadmin.storage.Volume',
                functools.partial(MockVolume, qubesd_calls_queue, 0)),
            mock.patch(
                'qubesadmin.backup.restore.BackupRestore._handle_appmenus_list',
                functools.partial(self.mock_appmenus, qubesd_calls_queue)),
            mock.patch(
                'qubesadmin.firewall.Firewall',
                functools.partial(MockFirewall, qubesd_calls_queue)),
            mock.patch(
                'time.strftime',
                return_value=dummy_timestamp)
        ]
        for patch in patches:
            patch.start()
        try:
            self.restore_backup(self.fullpath("backup.bin"), options={
                'use-default-template': True,
                'use-default-netvm': True,
            })
        finally:
            for patch in patches:
                patch.stop()

        # retrieve calls from other multiprocess.Process instances
        while not qubesd_calls_queue.empty():
            call_args = qubesd_calls_queue.get()
            self.app.qubesd_call(*call_args)
        qubesd_calls_queue.close()

        self.assertAllCalled()

        self.assertDom0Restored(dummy_timestamp)

    def test_220_r2_encrypted(self):
        self.create_v3_backup(True)

        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0dom0 class=AdminVM state=Running\n'
            b'fedora-25 class=TemplateVM state=Halted\n'
            b'testvm class=AppVM state=Running\n'
        )
        self.app.expected_calls[
            ('dom0', 'admin.property.Get', 'default_template', None)] = \
            b'0\0default=no type=vm fedora-25'
        self.setup_expected_calls(parsed_qubes_xml_r2, templates_map={
            'fedora-20-x64': 'fedora-25'
        })
        firewall_data = (
            'action=accept specialtarget=dns\n'
            'action=accept proto=icmp\n'
            'action=accept proto=tcp dstports=22-22\n'
            'action=accept proto=tcp dstports=9418-9418\n'
            'action=accept proto=tcp dst4=192.168.0.1/32 dstports=1234-1234\n'
            'action=accept proto=tcp dsthost=fedorahosted.org dstports=443-443\n'
            'action=accept proto=tcp dsthost=xenbits.xen.org dstports=80-80\n'
            'action=drop\n'
        )
        self.app.expected_calls[
            ('test-work', 'admin.vm.firewall.Set', None,
            firewall_data.encode())] = b'0\0'
        self.app.expected_calls[
            ('test-custom-template-appvm', 'admin.vm.firewall.Set', None,
            firewall_data.encode())] = b'0\0'

        qubesd_calls_queue = multiprocessing.Queue()

        dummy_timestamp = time.strftime("test-%Y-%m-%d-%H%M%S")
        patches = [
            mock.patch('qubesadmin.storage.Volume',
                functools.partial(MockVolume, qubesd_calls_queue, 0)),
            mock.patch(
                'qubesadmin.backup.restore.BackupRestore._handle_appmenus_list',
                functools.partial(self.mock_appmenus, qubesd_calls_queue)),
            mock.patch(
                'qubesadmin.firewall.Firewall',
                functools.partial(MockFirewall, qubesd_calls_queue)),
            mock.patch(
                'time.strftime',
                return_value=dummy_timestamp)
        ]
        for patch in patches:
            patch.start()
        try:
            self.restore_backup(self.fullpath("backup.bin"), options={
                'use-default-template': True,
                'use-default-netvm': True,
            })
        finally:
            for patch in patches:
                patch.stop()

        # retrieve calls from other multiprocess.Process instances
        while not qubesd_calls_queue.empty():
            call_args = qubesd_calls_queue.get()
            self.app.qubesd_call(*call_args)
        qubesd_calls_queue.close()

        self.assertAllCalled()

        self.assertDom0Restored(dummy_timestamp)

    def test_230_r2_uncompressed(self):
        self.create_v3_backup(False, False)
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0dom0 class=AdminVM state=Running\n'
            b'fedora-25 class=TemplateVM state=Halted\n'
            b'testvm class=AppVM state=Running\n'
        )
        self.app.expected_calls[
            ('dom0', 'admin.property.Get', 'default_template', None)] = \
            b'0\0default=no type=vm fedora-25'
        self.setup_expected_calls(parsed_qubes_xml_r2, templates_map={
            'fedora-20-x64': 'fedora-25'
        })
        firewall_data = (
            'action=accept specialtarget=dns\n'
            'action=accept proto=icmp\n'
            'action=accept proto=tcp dstports=22-22\n'
            'action=accept proto=tcp dstports=9418-9418\n'
            'action=accept proto=tcp dst4=192.168.0.1/32 dstports=1234-1234\n'
            'action=accept proto=tcp dsthost=fedorahosted.org dstports=443-443\n'
            'action=accept proto=tcp dsthost=xenbits.xen.org dstports=80-80\n'
            'action=drop\n'
        )
        self.app.expected_calls[
            ('test-work', 'admin.vm.firewall.Set', None,
            firewall_data.encode())] = b'0\0'
        self.app.expected_calls[
            ('test-custom-template-appvm', 'admin.vm.firewall.Set', None,
            firewall_data.encode())] = b'0\0'

        qubesd_calls_queue = multiprocessing.Queue()

        dummy_timestamp = time.strftime("test-%Y-%m-%d-%H%M%S")
        patches = [
            mock.patch('qubesadmin.storage.Volume',
                functools.partial(MockVolume, qubesd_calls_queue, 0)),
            mock.patch(
                'qubesadmin.backup.restore.BackupRestore._handle_appmenus_list',
                functools.partial(self.mock_appmenus, qubesd_calls_queue)),
            mock.patch(
                'qubesadmin.firewall.Firewall',
                functools.partial(MockFirewall, qubesd_calls_queue)),
            mock.patch(
                'time.strftime',
                return_value=dummy_timestamp)
        ]
        for patch in patches:
            patch.start()
        try:
            self.restore_backup(self.fullpath("backup.bin"), options={
                'use-default-template': True,
                'use-default-netvm': True,
            })
        finally:
            for patch in patches:
                patch.stop()

        # retrieve calls from other multiprocess.Process instances
        while not qubesd_calls_queue.empty():
            call_args = qubesd_calls_queue.get()
            self.app.qubesd_call(*call_args)
        qubesd_calls_queue.close()

        self.assertAllCalled()

        self.assertDom0Restored(dummy_timestamp)

    @unittest.skipUnless(spawn.find_executable('scrypt'),
        "scrypt not installed")
    def test_230_r4(self):
        self.create_v4_backup("")
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0dom0 class=AdminVM state=Running\n'
            b'fedora-25 class=TemplateVM state=Halted\n'
            b'testvm class=AppVM state=Running\n'
            b'sys-net class=AppVM state=Running\n'
        )
        self.app.expected_calls[
            ('dom0', 'admin.property.Get', 'default_template', None)] = \
            b'0\0default=no type=vm fedora-25'
        self.app.expected_calls[
            ('sys-net', 'admin.vm.property.Get', 'provides_network', None)] = \
            b'0\0default=no type=bool True'
        self.setup_expected_calls(parsed_qubes_xml_v4, templates_map={
            'debian-8': 'fedora-25'
        })
        firewall_data = (
            'action=accept specialtarget=dns\n'
            'action=accept proto=icmp\n'
            'action=accept proto=tcp dstports=22-22\n'
            'action=accept proto=tcp dsthost=www.qubes-os.org '
            'dstports=443-443\n'
            'action=accept proto=tcp dst4=192.168.0.0/24\n'
            'action=drop\n'
        )
        self.app.expected_calls[
            ('test-work', 'admin.vm.firewall.Set', None,
            firewall_data.encode())] = b'0\0'

        qubesd_calls_queue = multiprocessing.Queue()

        dummy_timestamp = time.strftime("test-%Y-%m-%d-%H%M%S")
        patches = [
            mock.patch('qubesadmin.storage.Volume',
                functools.partial(MockVolume, qubesd_calls_queue, 0)),
            mock.patch(
                'qubesadmin.backup.restore.BackupRestore._handle_appmenus_list',
                functools.partial(self.mock_appmenus, qubesd_calls_queue)),
            mock.patch(
                'qubesadmin.firewall.Firewall',
                functools.partial(MockFirewall, qubesd_calls_queue)),
            mock.patch(
                'time.strftime',
                return_value=dummy_timestamp)
        ]
        for patch in patches:
            patch.start()
        try:
            self.restore_backup(self.fullpath("backup.bin"), options={
                'use-default-template': True,
                'use-default-netvm': True,
            })
        finally:
            for patch in patches:
                patch.stop()

        # retrieve calls from other multiprocess.Process instances
        while not qubesd_calls_queue.empty():
            call_args = qubesd_calls_queue.get()
            with contextlib.suppress(qubesadmin.exc.QubesException):
                self.app.qubesd_call(*call_args)
        qubesd_calls_queue.close()

        self.assertAllCalled()

        self.assertDom0Restored(dummy_timestamp)

    @unittest.skipUnless(spawn.find_executable('scrypt'),
        "scrypt not installed")
    def test_230_r4_compressed(self):
        self.create_v4_backup("gzip")

        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0dom0 class=AdminVM state=Running\n'
            b'fedora-25 class=TemplateVM state=Halted\n'
            b'testvm class=AppVM state=Running\n'
            b'sys-net class=AppVM state=Running\n'
        )
        self.app.expected_calls[
            ('dom0', 'admin.property.Get', 'default_template', None)] = \
            b'0\0default=no type=vm fedora-25'
        self.app.expected_calls[
            ('sys-net', 'admin.vm.property.Get', 'provides_network', None)] = \
            b'0\0default=no type=bool True'
        self.setup_expected_calls(parsed_qubes_xml_v4, templates_map={
            'debian-8': 'fedora-25'
        })
        firewall_data = (
            'action=accept specialtarget=dns\n'
            'action=accept proto=icmp\n'
            'action=accept proto=tcp dstports=22-22\n'
            'action=accept proto=tcp dsthost=www.qubes-os.org '
            'dstports=443-443\n'
            'action=accept proto=tcp dst4=192.168.0.0/24\n'
            'action=drop\n'
        )
        self.app.expected_calls[
            ('test-work', 'admin.vm.firewall.Set', None,
            firewall_data.encode())] = b'0\0'

        qubesd_calls_queue = multiprocessing.Queue()

        dummy_timestamp = time.strftime("test-%Y-%m-%d-%H%M%S")
        patches = [
            mock.patch('qubesadmin.storage.Volume',
                functools.partial(MockVolume, qubesd_calls_queue, 0)),
            mock.patch(
                'qubesadmin.backup.restore.BackupRestore._handle_appmenus_list',
                functools.partial(self.mock_appmenus, qubesd_calls_queue)),
            mock.patch(
                'qubesadmin.firewall.Firewall',
                functools.partial(MockFirewall, qubesd_calls_queue)),
            mock.patch(
                'time.strftime',
                return_value=dummy_timestamp)
        ]
        for patch in patches:
            patch.start()
        try:
            self.restore_backup(self.fullpath("backup.bin"), options={
                'use-default-template': True,
                'use-default-netvm': True,
            })
        finally:
            for patch in patches:
                patch.stop()

        # retrieve calls from other multiprocess.Process instances
        while not qubesd_calls_queue.empty():
            call_args = qubesd_calls_queue.get()
            with contextlib.suppress(qubesadmin.exc.QubesException):
                self.app.qubesd_call(*call_args)
        qubesd_calls_queue.close()

        self.assertAllCalled()

        self.assertDom0Restored(dummy_timestamp)

    @unittest.skipUnless(spawn.find_executable('scrypt'),
        "scrypt not installed")
    def test_230_r4_custom_cmpression(self):
        self.create_v4_backup("bzip2")

        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0dom0 class=AdminVM state=Running\n'
            b'fedora-25 class=TemplateVM state=Halted\n'
            b'testvm class=AppVM state=Running\n'
            b'sys-net class=AppVM state=Running\n'
        )
        self.app.expected_calls[
            ('dom0', 'admin.property.Get', 'default_template', None)] = \
            b'0\0default=no type=vm fedora-25'
        self.app.expected_calls[
            ('sys-net', 'admin.vm.property.Get', 'provides_network', None)] = \
            b'0\0default=no type=bool True'
        self.setup_expected_calls(parsed_qubes_xml_v4, templates_map={
            'debian-8': 'fedora-25'
        })
        firewall_data = (
            'action=accept specialtarget=dns\n'
            'action=accept proto=icmp\n'
            'action=accept proto=tcp dstports=22-22\n'
            'action=accept proto=tcp dsthost=www.qubes-os.org '
            'dstports=443-443\n'
            'action=accept proto=tcp dst4=192.168.0.0/24\n'
            'action=drop\n'
        )
        self.app.expected_calls[
            ('test-work', 'admin.vm.firewall.Set', None,
            firewall_data.encode())] = b'0\0'

        qubesd_calls_queue = multiprocessing.Queue()

        dummy_timestamp = time.strftime("test-%Y-%m-%d-%H%M%S")
        patches = [
            mock.patch('qubesadmin.storage.Volume',
                functools.partial(MockVolume, qubesd_calls_queue, 0)),
            mock.patch(
                'qubesadmin.backup.restore.BackupRestore._handle_appmenus_list',
                functools.partial(self.mock_appmenus, qubesd_calls_queue)),
            mock.patch(
                'qubesadmin.firewall.Firewall',
                functools.partial(MockFirewall, qubesd_calls_queue)),
            mock.patch(
                'time.strftime',
                return_value=dummy_timestamp)
        ]
        for patch in patches:
            patch.start()
        try:
            self.restore_backup(self.fullpath("backup.bin"), options={
                'use-default-template': True,
                'use-default-netvm': True,
            })
        finally:
            for patch in patches:
                patch.stop()

        # retrieve calls from other multiprocess.Process instances
        while not qubesd_calls_queue.empty():
            call_args = qubesd_calls_queue.get()
            with contextlib.suppress(qubesadmin.exc.QubesException):
                self.app.qubesd_call(*call_args)
        qubesd_calls_queue.close()

        self.assertAllCalled()

        self.assertDom0Restored(dummy_timestamp)

    @unittest.skipUnless(spawn.find_executable('scrypt'),
        "scrypt not installed")
    def test_230_r4_uncommon_compression(self):
        self.create_v4_backup("less")

        qubesd_calls_queue = multiprocessing.Queue()

        dummy_timestamp = time.strftime("test-%Y-%m-%d-%H%M%S")
        patches = [
            mock.patch('qubesadmin.storage.Volume',
                functools.partial(MockVolume, qubesd_calls_queue, 0)),
            mock.patch(
                'qubesadmin.backup.restore.BackupRestore._handle_appmenus_list',
                functools.partial(self.mock_appmenus, qubesd_calls_queue)),
            mock.patch(
                'qubesadmin.firewall.Firewall',
                functools.partial(MockFirewall, qubesd_calls_queue)),
            mock.patch(
                'time.strftime',
                return_value=dummy_timestamp)
        ]
        for patch in patches:
            patch.start()
        try:
            with self.assertRaises(qubesadmin.exc.QubesException):
                qubesadmin.backup.restore.BackupRestore(
                    self.app, self.fullpath("backup.bin"), None, 'qubes')
        finally:
            for patch in patches:
                patch.stop()

    @unittest.skipUnless(spawn.find_executable('scrypt'),
        "scrypt not installed")
    def test_230_r4_uncommon_cmpression_forced(self):
        self.create_v4_backup("less")

        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0dom0 class=AdminVM state=Running\n'
            b'fedora-25 class=TemplateVM state=Halted\n'
            b'testvm class=AppVM state=Running\n'
            b'sys-net class=AppVM state=Running\n'
        )
        self.app.expected_calls[
            ('dom0', 'admin.property.Get', 'default_template', None)] = \
            b'0\0default=no type=vm fedora-25'
        self.app.expected_calls[
            ('sys-net', 'admin.vm.property.Get', 'provides_network', None)] = \
            b'0\0default=no type=bool True'
        self.setup_expected_calls(parsed_qubes_xml_v4, templates_map={
            'debian-8': 'fedora-25'
        })
        firewall_data = (
            'action=accept specialtarget=dns\n'
            'action=accept proto=icmp\n'
            'action=accept proto=tcp dstports=22-22\n'
            'action=accept proto=tcp dsthost=www.qubes-os.org '
            'dstports=443-443\n'
            'action=accept proto=tcp dst4=192.168.0.0/24\n'
            'action=drop\n'
        )
        self.app.expected_calls[
            ('test-work', 'admin.vm.firewall.Set', None,
            firewall_data.encode())] = b'0\0'

        qubesd_calls_queue = multiprocessing.Queue()

        dummy_timestamp = time.strftime("test-%Y-%m-%d-%H%M%S")
        patches = [
            mock.patch('qubesadmin.storage.Volume',
                functools.partial(MockVolume, qubesd_calls_queue, 0)),
            mock.patch(
                'qubesadmin.backup.restore.BackupRestore._handle_appmenus_list',
                functools.partial(self.mock_appmenus, qubesd_calls_queue)),
            mock.patch(
                'qubesadmin.firewall.Firewall',
                functools.partial(MockFirewall, qubesd_calls_queue)),
            mock.patch(
                'time.strftime',
                return_value=dummy_timestamp)
        ]
        for patch in patches:
            patch.start()
        try:
            self.restore_backup(self.fullpath("backup.bin"), options={
                'use-default-template': True,
                'use-default-netvm': True,
            }, force_compression_filter='less')
        finally:
            for patch in patches:
                patch.stop()

        # retrieve calls from other multiprocess.Process instances
        while not qubesd_calls_queue.empty():
            call_args = qubesd_calls_queue.get()
            with contextlib.suppress(qubesadmin.exc.QubesException):
                self.app.qubesd_call(*call_args)
        qubesd_calls_queue.close()

        self.assertAllCalled()

        self.assertDom0Restored(dummy_timestamp)

    @unittest.skipUnless(spawn.find_executable('scrypt'),
        "scrypt not installed")
    def test_300_r4_no_space(self):
        self.create_v4_backup("", big=True)
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0dom0 class=AdminVM state=Running\n'
            b'fedora-25 class=TemplateVM state=Halted\n'
            b'testvm class=AppVM state=Running\n'
            b'sys-net class=AppVM state=Running\n'
        )
        self.app.expected_calls[
            ('dom0', 'admin.property.Get', 'default_template', None)] = \
            b'0\0default=no type=vm fedora-25'
        self.app.expected_calls[
            ('sys-net', 'admin.vm.property.Get', 'provides_network', None)] = \
            b'0\0default=no type=bool True'
        self.setup_expected_calls(parsed_qubes_xml_v4, templates_map={
            'debian-8': 'fedora-25'
        })
        firewall_data = (
            'action=accept specialtarget=dns\n'
            'action=accept proto=icmp\n'
            'action=accept proto=tcp dstports=22-22\n'
            'action=accept proto=tcp dsthost=www.qubes-os.org '
            'dstports=443-443\n'
            'action=accept proto=tcp dst4=192.168.0.0/24\n'
            'action=drop\n'
        )
        self.app.expected_calls[
            ('test-work', 'admin.vm.firewall.Set', None,
            firewall_data.encode())] = b'0\0'

        qubesd_calls_queue = multiprocessing.Queue()

        dummy_timestamp = time.strftime("test-%Y-%m-%d-%H%M%S")
        patches = [
            mock.patch('qubesadmin.storage.Volume',
                functools.partial(MockVolume, qubesd_calls_queue, 30)),
            mock.patch(
                'qubesadmin.backup.restore.BackupRestore._handle_appmenus_list',
                functools.partial(self.mock_appmenus, qubesd_calls_queue)),
            mock.patch(
                'qubesadmin.firewall.Firewall',
                functools.partial(MockFirewall, qubesd_calls_queue)),
            mock.patch(
                'time.strftime',
                return_value=dummy_timestamp),
            mock.patch(
                'qubesadmin.backup.restore.BackupRestore.check_disk_space')
        ]
        small_tmpdir = self.create_limited_tmpdir('620M')
        for patch in patches:
            patch.start()
        try:
            self.restore_backup(self.fullpath("backup.bin"),
                tmpdir=small_tmpdir,
                options={
                    'use-default-template': True,
                    'use-default-netvm': True,
            })
        finally:
            for patch in patches:
                patch.stop()

        # retrieve calls from other multiprocess.Process instances
        while not qubesd_calls_queue.empty():
            call_args = qubesd_calls_queue.get()
            with contextlib.suppress(qubesadmin.exc.QubesException):
                self.app.qubesd_call(*call_args)
        qubesd_calls_queue.close()

        self.assertAllCalled()

        self.assertDom0Restored(dummy_timestamp)


class TC_11_BackupCompatibilityIntoLVM(TC_10_BackupCompatibility):
    storage_pool = 'some-pool'


    def restore_backup(self, source=None, appvm=None, options=None,
            **kwargs):
        if options is None:
            options = {}
        options['override_pool'] = self.storage_pool
        super(TC_11_BackupCompatibilityIntoLVM, self).restore_backup(source,
            appvm, options, **kwargs)
