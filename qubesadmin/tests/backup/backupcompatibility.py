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
import tempfile
from multiprocessing import Queue

import os
import subprocess

try:
    import unittest.mock as mock
except ImportError:
    import mock
import re

import multiprocessing

import sys

import qubesadmin.backup.core2
import qubesadmin.storage
import qubesadmin.tests
import qubesadmin.tests.backup

QUBESXML_R2B2 = '''
<QubesVmCollection updatevm="3" default_kernel="3.7.6-2" default_netvm="3" default_fw_netvm="2" default_template="1" clockvm="2">
  <QubesTemplateVm installed_by_rpm="True" kernel="3.7.6-2" uses_default_kernelopts="True" qid="1" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="fedora-18-x64.conf" label="black" template_qid="none" kernelopts="" memory="400" default_user="user" netvm_qid="3" uses_default_netvm="True" volatile_img="volatile.img" services="{'meminfo-writer': True}" maxmem="1535" pcidevs="[]" name="fedora-18-x64" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/vm-templates/fedora-18-x64"/>
  <QubesNetVm installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="2" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="netvm.conf" label="red" template_qid="1" kernelopts="iommu=soft swiotlb=4096" memory="200" default_user="user" volatile_img="volatile.img" services="{'ntpd': False, 'meminfo-writer': False}" maxmem="1535" pcidevs="['02:00.0', '03:00.0']" name="netvm" netid="1" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/servicevms/netvm"/>
  <QubesProxyVm installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="3" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="firewallvm.conf" label="green" template_qid="1" kernelopts="" memory="200" default_user="user" netvm_qid="2" volatile_img="volatile.img" services="{'meminfo-writer': True}" maxmem="1535" pcidevs="[]" name="firewallvm" netid="2" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/servicevms/firewallvm"/>
  <QubesAppVm installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="4" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="True" conf_file="fedora-18-x64-dvm.conf" label="gray" template_qid="1" kernelopts="" memory="400" default_user="user" netvm_qid="3" uses_default_netvm="True" volatile_img="volatile.img" services="{'meminfo-writer': True}" maxmem="1535" pcidevs="[]" name="fedora-18-x64-dvm" private_img="private.img" vcpus="1" root_img="root.img" debug="False" dir_path="/var/lib/qubes/appvms/fedora-18-x64-dvm"/>
  <QubesAppVm installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="5" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="test-work.conf" label="green" template_qid="1" kernelopts="" memory="400" default_user="user" netvm_qid="3" uses_default_netvm="True" volatile_img="volatile.img" services="{'meminfo-writer': True}" maxmem="1535" pcidevs="[]" name="test-work" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/appvms/test-work"/>
  <QubesAppVm installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="6" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="banking.conf" label="green" template_qid="1" kernelopts="" memory="400" default_user="user" netvm_qid="3" uses_default_netvm="True" volatile_img="volatile.img" services="{'meminfo-writer': True}" maxmem="1535" pcidevs="[]" name="banking" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/appvms/banking"/>
  <QubesAppVm installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="7" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="personal.conf" label="yellow" template_qid="1" kernelopts="" memory="400" default_user="user" netvm_qid="3" uses_default_netvm="True" volatile_img="volatile.img" services="{'meminfo-writer': True}" maxmem="1535" pcidevs="[]" name="personal" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/appvms/personal"/>
  <QubesAppVm installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="8" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="untrusted.conf" label="red" template_qid="1" kernelopts="" memory="400" default_user="user" netvm_qid="12" uses_default_netvm="False" volatile_img="volatile.img" services="{'meminfo-writer': True}" maxmem="1535" pcidevs="[]" name="untrusted" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/appvms/untrusted"/>
  <QubesTemplateVm installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="9" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="test-template-clone.conf" label="green" template_qid="none" kernelopts="" memory="400" default_user="user" netvm_qid="3" uses_default_netvm="True" volatile_img="volatile.img" services="{'meminfo-writer': True}" maxmem="1535" pcidevs="[]" name="test-template-clone" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/vm-templates/test-template-clone"/>
  <QubesAppVm installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="10" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="test-custom-template-appvm.conf" label="yellow" template_qid="9" kernelopts="" memory="400" default_user="user" netvm_qid="3" uses_default_netvm="True" volatile_img="volatile.img" services="{'meminfo-writer': True}" maxmem="1535" pcidevs="[]" name="test-custom-template-appvm" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/appvms/test-custom-template-appvm"/>
  <QubesAppVm installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="11" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="test-standalonevm.conf" label="blue" template_qid="none" kernelopts="" memory="400" default_user="user" netvm_qid="3" uses_default_netvm="True" volatile_img="volatile.img" services="{'meminfo-writer': True}" maxmem="1535" pcidevs="[]" name="test-standalonevm" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/appvms/test-standalonevm"/>
  <QubesProxyVm installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="12" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="test-testproxy.conf" label="red" template_qid="1" kernelopts="" memory="200" default_user="user" netvm_qid="3" volatile_img="volatile.img" services="{'meminfo-writer': True}" maxmem="1535" pcidevs="[]" name="test-testproxy" netid="3" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/servicevms/test-testproxy"/>
  <QubesProxyVm installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="13" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="testproxy2.conf" label="red" template_qid="9" kernelopts="" memory="200" default_user="user" netvm_qid="2" volatile_img="volatile.img" services="{'meminfo-writer': True}" maxmem="1535" pcidevs="[]" name="testproxy2" netid="4" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/servicevms/testproxy2"/>
  <QubesHVm installed_by_rpm="False" netvm_qid="none" qid="14" include_in_backups="True" timezone="localtime" qrexec_timeout="60" conf_file="test-testhvm.conf" label="purple" template_qid="none" internal="False" memory="512" uses_default_netvm="True" services="{'meminfo-writer': False}" default_user="user" pcidevs="[]" name="test-testhvm" qrexec_installed="False" private_img="private.img" drive="None" vcpus="2" root_img="root.img" guiagent_installed="False" debug="False" dir_path="/var/lib/qubes/appvms/test-testhvm"/>
  <QubesDisposableVm dispid="50" firewall_conf="firewall.xml" label="red" name="disp50" netvm_qid="2" qid="15" template_qid="1"/>
</QubesVmCollection>
'''

QUBESXML_R2 = '''
<QubesVmCollection updatevm="3" default_kernel="3.7.6-2" default_netvm="3" default_fw_netvm="2" default_template="1" clockvm="2">
  <QubesTemplateVm installed_by_rpm="True" kernel="3.7.6-2" uses_default_kernelopts="True" qid="1" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="fedora-20-x64.conf" label="black" template_qid="none" kernelopts="" memory="400" default_user="user" netvm_qid="3" uses_default_netvm="True" volatile_img="volatile.img" services="{ 'meminfo-writer': True}" maxmem="1535" pcidevs="[]" name="fedora-20-x64" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/vm-templates/fedora-20-x64"/>
  <QubesNetVm installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="2" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="netvm.conf" label="red" template_qid="1" kernelopts="iommu=soft swiotlb=4096" memory="200" default_user="user" volatile_img="volatile.img" services="{'ntpd': False, 'meminfo-writer': False}" maxmem="1535" pcidevs="['02:00.0', '03:00.0']" name="netvm" netid="1" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/servicevms/netvm"/>
  <QubesProxyVm installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="3" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="firewallvm.conf" label="green" template_qid="1" kernelopts="" memory="200" default_user="user" netvm_qid="2" volatile_img="volatile.img" services="{'meminfo-writer': True}" maxmem="1535" pcidevs="[]" name="firewallvm" netid="2" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/servicevms/firewallvm"/>
  <QubesAppVm installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="4" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="True" conf_file="fedora-20-x64-dvm.conf" label="gray" template_qid="1" kernelopts="" memory="400" default_user="user" netvm_qid="3" uses_default_netvm="True" volatile_img="volatile.img" services="{ 'meminfo-writer': True}" maxmem="1535" pcidevs="[]" name="fedora-20-x64-dvm" private_img="private.img" vcpus="1" root_img="root.img" debug="False" dir_path="/var/lib/qubes/appvms/fedora-20-x64-dvm"/>
  <QubesAppVm backup_content="True" backup_path="appvms/test-work" installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="5" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="test-work.conf" label="green" template_qid="1" kernelopts="" memory="400" default_user="user" netvm_qid="3" uses_default_netvm="True" volatile_img="volatile.img" services="{'meminfo-writer': True}" maxmem="1535" pcidevs="[]" name="test-work" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/appvms/test-work"/>
  <QubesAppVm installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="6" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="banking.conf" label="green" template_qid="1" kernelopts="" memory="400" default_user="user" netvm_qid="3" uses_default_netvm="True" volatile_img="volatile.img" services="{'meminfo-writer': True}" maxmem="1535" pcidevs="[]" name="banking" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/appvms/banking"/>
  <QubesAppVm installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="7" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="personal.conf" label="yellow" template_qid="1" kernelopts="" memory="400" default_user="user" netvm_qid="3" uses_default_netvm="True" volatile_img="volatile.img" services="{'meminfo-writer': True}" maxmem="1535" pcidevs="[]" name="personal" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/appvms/personal"/>
  <QubesAppVm installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="8" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="untrusted.conf" label="red" template_qid="1" kernelopts="" memory="400" default_user="user" netvm_qid="12" uses_default_netvm="False" volatile_img="volatile.img" services="{'meminfo-writer': True}" maxmem="1535" pcidevs="[]" name="untrusted" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/appvms/untrusted"/>
  <QubesTemplateVm backup_size="104857600" backup_content="True" backup_path="vm-templates/test-template-clone" installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="9" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="test-template-clone.conf" label="green" template_qid="none" kernelopts="" memory="400" default_user="user" netvm_qid="3" uses_default_netvm="True" volatile_img="volatile.img" services="{'meminfo-writer': True}" maxmem="1535" pcidevs="[]" name="test-template-clone" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/vm-templates/test-template-clone"/>
  <QubesAppVm backup_size="104857600" backup_content="True" backup_path="appvms/test-custom-template-appvm" installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="10" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="test-custom-template-appvm.conf" label="yellow" template_qid="9" kernelopts="" memory="400" default_user="user" netvm_qid="3" uses_default_netvm="True" volatile_img="volatile.img" services="{'meminfo-writer': True}" maxmem="1535" pcidevs="[]" name="test-custom-template-appvm" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/appvms/test-custom-template-appvm"/>
  <QubesAppVm backup_size="104857600" backup_content="True" backup_path="appvms/test-standalonevm" installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="11" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="test-standalonevm.conf" label="blue" template_qid="none" kernelopts="" memory="400" default_user="user" netvm_qid="3" uses_default_netvm="True" volatile_img="volatile.img" services="{'meminfo-writer': True}" maxmem="1535" pcidevs="[]" name="test-standalonevm" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/appvms/test-standalonevm"/>
  <QubesProxyVm backup_size="104857600" backup_content="True" backup_path="servicevms/test-testproxy" installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="12" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="test-testproxy.conf" label="red" template_qid="1" kernelopts="" memory="200" default_user="user" netvm_qid="3" volatile_img="volatile.img" services="{'meminfo-writer': True}" maxmem="1535" pcidevs="[]" name="test-testproxy" netid="3" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/servicevms/test-testproxy"/>
  <QubesProxyVm installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="13" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="testproxy2.conf" label="red" template_qid="9" kernelopts="" memory="200" default_user="user" netvm_qid="2" volatile_img="volatile.img" services="{'meminfo-writer': True}" maxmem="1535" pcidevs="[]" name="testproxy2" netid="4" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/servicevms/testproxy2"/>
  <QubesHVm backup_size="104857600" backup_content="True" backup_path="appvms/test-testhvm" installed_by_rpm="False" netvm_qid="none" qid="14" include_in_backups="True" timezone="localtime" qrexec_timeout="60" conf_file="test-testhvm.conf" label="purple" template_qid="none" internal="False" memory="512" uses_default_netvm="True" services="{'meminfo-writer': False}" default_user="user" pcidevs="[]" name="test-testhvm" qrexec_installed="False" private_img="private.img" drive="None" vcpus="2" root_img="root.img" guiagent_installed="False" debug="False" dir_path="/var/lib/qubes/appvms/test-testhvm"/>
  <QubesDisposableVm dispid="50" firewall_conf="firewall.xml" label="red" name="disp50" netvm_qid="2" qid="15" template_qid="1"/>
  <QubesNetVm backup_size="104857600" backup_content="True" backup_path="servicevms/test-net" installed_by_rpm="False" kernel="3.7.6-2" uses_default_kernelopts="True" qid="16" include_in_backups="True" uses_default_kernel="True" qrexec_timeout="60" internal="False" conf_file="test-net.conf" label="red" template_qid="1" kernelopts="iommu=soft swiotlb=4096" memory="200" default_user="user" volatile_img="volatile.img" services="{'ntpd': False, 'meminfo-writer': False}" maxmem="1535" pcidevs="['02:00.0', '03:00.0']" name="test-net" netid="2" private_img="private.img" vcpus="2" root_img="root.img" debug="False" dir_path="/var/lib/qubes/servicevms/test-net"/>
</QubesVmCollection>
'''

MANGLED_SUBDIRS_R2 = {
    "test-work": "vm5",
    "test-template-clone": "vm9",
    "test-custom-template-appvm": "vm10",
    "test-standalonevm": "vm11",
    "test-testproxy": "vm12",
    "test-testhvm": "vm14",
    "test-net": "vm16",
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
            'backup_path': None,
            'included_in_backup': False,
        },
        'fedora-20-x64': {
            'klass': 'TemplateVM',
            'label': 'black',
            'properties': {
                'hvm': False,
                'maxmem': '1535',
            },
            'devices': {},
            'tags': set(),
            'features': {'services.meminfo-writer': True},
            'template': None,
            'backup_path': None,
            'included_in_backup': False,
        },
        'netvm': {
            'klass': 'AppVM',
            'label': 'red',
            'properties': {
                'hvm': False,
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
                'services.meminfo-writer': False
            },
            'template': 'fedora-20-x64',
            'backup_path': None,
            'included_in_backup': False,
        },
        'firewallvm': {
            'klass': 'AppVM',
            'label': 'green',
            'properties': {
                'hvm': False,
                'maxmem': '1535',
                'memory': '200',
                'provides_network': True
            },
            'devices': {},
            'tags': set(),
            'features': {'services.meminfo-writer': True},
            'template': 'fedora-20-x64',
            'backup_path': None,
            'included_in_backup': False,
        },
        'fedora-20-x64-dvm': {
            'klass': 'AppVM',
            'label': 'gray',
            'properties': {
                'hvm': False,
                'maxmem': '1535',
                'vcpus': '1'
            },
            'devices': {},
            'tags': set(),
            'features': {
                'internal': True, 'services.meminfo-writer': True},
            'template': 'fedora-20-x64',
            'backup_path': None,
            'included_in_backup': False,
        },
        'banking': {
            'klass': 'AppVM',
            'label': 'green',
            'properties': {'hvm': False, 'maxmem': '1535'},
            'devices': {},
            'tags': set(),
            'features': {'services.meminfo-writer': True},
            'template': 'fedora-20-x64',
            'backup_path': None,
            'included_in_backup': False,
        },
        'personal': {
            'klass': 'AppVM',
            'label': 'yellow',
            'properties': {'hvm': False, 'maxmem': '1535'},
            'devices': {},
            'tags': set(),
            'features': {'services.meminfo-writer': True},
            'template': 'fedora-20-x64',
            'backup_path': None,
            'included_in_backup': False,
        },
        'untrusted': {
            'klass': 'AppVM',
            'label': 'red',
            'properties': {
                'hvm': False,
                'maxmem': '1535',
                'netvm': 'test-testproxy',
                'default_dispvm': 'disp-test-testproxy',
            },
            'devices': {},
            'tags': set(),
            'features': {'services.meminfo-writer': True},
            'template': 'fedora-20-x64',
            'backup_path': None,
            'included_in_backup': False,
        },
        'testproxy2': {
            'klass': 'AppVM',
            'label': 'red',
            'properties': {
                'hvm': False,
                'maxmem': '1535',
                'memory': '200',
                'provides_network': True},
            'devices': {},
            'tags': set(),
            'features': {'services.meminfo-writer': True},
            'template': 'test-template-clone',
            'backup_path': None,
            'included_in_backup': False,
        },
        'test-testproxy': {
            'klass': 'AppVM',
            'label': 'red',
            'properties': {
                'hvm': False,
                'maxmem': '1535',
                'memory': '200',
                'provides_network': True},
            'devices': {},
            'tags': set(),
            'features': {'services.meminfo-writer': True},
            'template': 'fedora-20-x64',
            'backup_path': 'servicevms/test-testproxy',
            'included_in_backup': True,
        },
        'test-testhvm': {
            'klass': 'StandaloneVM',
            'label': 'purple',
            'properties': {'hvm': True, 'memory': '512'},
            'devices': {},
            'tags': set(),
            'features': {'services.meminfo-writer': False},
            'template': None,
            'backup_path': 'appvms/test-testhvm',
            'included_in_backup': True,
            'root_size': 2097664,
        },
        'test-work': {
            'klass': 'AppVM',
            'label': 'green',
            'properties': {'hvm': False, 'maxmem': '1535'},
            'devices': {},
            'tags': set(),
            'features': {'services.meminfo-writer': True},
            'template': 'fedora-20-x64',
            'backup_path': 'appvms/test-work',
            'included_in_backup': True,
        },
        'test-template-clone': {
            'klass': 'TemplateVM',
            'label': 'green',
            'properties': {'hvm': False, 'maxmem': '1535'},
            'devices': {},
            'tags': set(),
            'features': {'services.meminfo-writer': True},
            'template': None,
            'backup_path': 'vm-templates/test-template-clone',
            'included_in_backup': True,
        },
        'test-custom-template-appvm': {
            'klass': 'AppVM',
            'label': 'yellow',
            'properties': {'hvm': False, 'maxmem': '1535'},
            'devices': {},
            'tags': set(),
            'features': {'services.meminfo-writer': True},
            'template': 'test-template-clone',
            'backup_path': 'appvms/test-custom-template-appvm',
            'included_in_backup': True,
        },
        'test-standalonevm': {
            'klass': 'StandaloneVM',
            'label': 'blue',
            'properties': {'hvm': False, 'maxmem': '1535'},
            'devices': {},
            'tags': set(),
            'features': {'services.meminfo-writer': True},
            'template': None,
            'backup_path': 'appvms/test-standalonevm',
            'included_in_backup': True,
            'root_size': 2097664,
        },
        'test-net': {
            'klass': 'AppVM',
            'label': 'red',
            'properties': {'hvm': False,
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
                'services.meminfo-writer': False
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
                'dispvm_allowed': True,
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
                'dispvm_allowed': True,
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


class TC_00_QubesXML(qubesadmin.tests.QubesTestCase):

    def assertCorrectlyConverted(self, xml_data, expected_data):
        with tempfile.NamedTemporaryFile() as qubes_xml:
            qubes_xml.file.write(xml_data.encode())
            backup_app = qubesadmin.backup.core2.Core2Qubes(qubes_xml.name)
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
        self.assertCorrectlyConverted(QUBESXML_R2, parsed_qubes_xml_r2)

# backup code use multiprocessing, synchronize with main process
class AppProxy(object):
    def __init__(self, app, sync_queue):
        self._app = app
        self._sync_queue = sync_queue

    def qubesd_call(self, dest, method, arg=None, payload=None,
            payload_stream=None):
        if payload_stream:
            signature_bin = payload_stream.read(512)
            payload = signature_bin.split(b'\0', 1)[0]
            subprocess.call(['cat'], stdin=payload_stream,
                stdout=subprocess.DEVNULL)
            payload_stream.close()
        self._sync_queue.put((dest, method, arg, payload))
        return self._app.qubesd_call(dest, method, arg, payload)


class MockVolume(qubesadmin.storage.Volume):
    def __init__(self, import_data_queue, *args, **kwargs):
        super(MockVolume, self).__init__(*args, **kwargs)
        self.app = AppProxy(self.app, import_data_queue)


class TC_10_BackupCompatibility(qubesadmin.tests.backup.BackupTestCase):

    storage_pool = None

    def tearDown(self):
        try:
            for vm in self.app.domains:
                if vm.name.startswith('test-'):
                    del self.app.domains[vm.name]
        except:
            pass
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

    def create_private_img(self, filename):
        signature = '/'.join(os.path.splitext(filename)[0].split('/')[-2:])
        self.create_sparse(filename, 2*2**20, signature=signature.encode())
        #subprocess.check_call(["/usr/sbin/mkfs.ext4", "-q", "-F", filename])

    def create_volatile_img(self, filename):
        self.create_sparse(filename, 11.5*2**20)
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

        # normal AppVM
        os.mkdir(self.fullpath("appvms/test-work"))
        self.create_whitelisted_appmenus(self.fullpath(
            "appvms/test-work/whitelisted-appmenus.list"))
        os.symlink("/usr/share/qubes/icons/green.png",
                   self.fullpath("appvms/test-work/icon.png"))
        self.create_private_img(self.fullpath("appvms/test-work/private.img"))

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
            "vm-templates/test-template-clone/root.img"), 1*2**20, True,
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
                ["openssl", "enc", "-e", "-aes-256-cbc", "-pass", "pass:qubes"],
                stdin=tar.stdout,
                stdout=subprocess.PIPE)
            tar.stdout.close()
            data = encryptor.stdout
        else:
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
        with open(self.fullpath("qubes.xml"), "w") as f:
            if encrypted:
                qubesxml = QUBESXML_R2
                for vmname, subdir in MANGLED_SUBDIRS_R2.items():
                    qubesxml = re.sub(r"[a-z-]*/{}".format(vmname),
                                      subdir, qubesxml)
                f.write(qubesxml)
            else:
                f.write(QUBESXML_R2)

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
                        subdir+'/', output, encrypted=encrypted)

        for vm_name in os.listdir(self.fullpath("vm-templates")):
            vm_dir = os.path.join("vm-templates", vm_name)
            if encrypted:
                subdir = MANGLED_SUBDIRS_R2[vm_name]
            else:
                subdir = vm_dir
            self.handle_v3_file(
                os.path.join(vm_dir, "."),
                subdir+'/', output, encrypted=encrypted)

        output.close()

    def setup_expected_calls(self, parsed_qubes_xml, templates_map=None):
        if templates_map is None:
            templates_map = {}

        extra_vm_list_lines = []
        for name, vm in parsed_qubes_xml['domains'].items():
            if not vm['included_in_backup']:
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
                        (name, 'admin.vm.volume.Resize', 'root',
                        str(vm.get('root_size', 2097664)).encode())] = \
                        b'0\0'
                    self.app.expected_calls[
                        (name, 'admin.vm.volume.Import', 'root',
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
                    (name, 'admin.vm.volume.Resize', 'private', b'2097152')] = \
                    b'0\0'
                self.app.expected_calls[
                    (name, 'admin.vm.volume.Import', 'private',
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
                self.app.expected_calls[
                    (name, 'admin.vm.feature.Set', feature,
                    str(value).encode())] = b'0\0'

        orig_admin_vm_list = self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)]
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            [orig_admin_vm_list] + \
            [orig_admin_vm_list + b''.join(extra_vm_list_lines)] * \
            len(extra_vm_list_lines)

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

        qubesd_calls_queue = multiprocessing.Queue()

        with mock.patch('qubesadmin.storage.Volume',
                functools.partial(MockVolume, qubesd_calls_queue)):
            self.restore_backup(self.fullpath("backup.bin"), options={
                'use-default-template': True,
                'use-default-netvm': True,
            })

        # retrieve calls from other multiprocess.Process instances
        while not qubesd_calls_queue.empty():
            call_args = qubesd_calls_queue.get()
            self.app.qubesd_call(*call_args)
        qubesd_calls_queue.close()

        self.assertAllCalled()

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

        qubesd_calls_queue = multiprocessing.Queue()

        with mock.patch('qubesadmin.storage.Volume',
                functools.partial(MockVolume, qubesd_calls_queue)):
            self.restore_backup(self.fullpath("backup.bin"), options={
                'use-default-template': True,
                'use-default-netvm': True,
            })

        # retrieve calls from other multiprocess.Process instances
        while not qubesd_calls_queue.empty():
            call_args = qubesd_calls_queue.get()
            self.app.qubesd_call(*call_args)
        qubesd_calls_queue.close()

        self.assertAllCalled()


class TC_11_BackupCompatibilityIntoLVM(TC_10_BackupCompatibility):
    storage_pool = 'some-pool'


    def restore_backup(self, source=None, appvm=None, options=None,
            expect_errors=None, manipulate_restore_info=None,
            passphrase='qubes'):
        if options is None:
            options = {}
        options['override_pool'] = self.storage_pool
        super(TC_11_BackupCompatibilityIntoLVM, self).restore_backup(source,
            appvm, options, expect_errors, manipulate_restore_info)