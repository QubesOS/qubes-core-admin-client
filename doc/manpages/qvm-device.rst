.. program:: qvm-device

=============================================
:program:`qvm-device` -- List/set VM devices
=============================================

Synopsis
========
| :command:`qvm-device` [*options*] *DEVICE_CLASS* {list,ls,l} <*vm-name*>
| :command:`qvm-device` [*options*] *DEVICE_CLASS* {attach,at,a} <*vm-name*> <*device*>
| :command:`qvm-device` [*options*] *DEVICE_CLASS* {detach,dt,d} <*vm-name*> <*device*>

Options
=======

.. option:: --help, -h

    Show this help message and exit

.. option:: --verbose, -v

   increase verbosity

.. option:: --quiet, -q

   decrease verbosity

Commands
========

list
^^^^

| :command:`qvm-device` *DEVICE_CLASS* list [-h] [--verbose] [--quiet] [*VMNAME* [*VMNAME* ...]]

List devices.

.. option:: --all

   List devices from all qubes. You can use :option:`--exclude` to limit the
   qubes set.

.. option:: --exclude

   Exclude the qube from :option:`--all`.

aliases: ls, l

attach
^^^^^^

| :command:`qvm-device` *DEVICE_CLASS* attach [-h] [--verbose] [--quiet] [--ro] *VMNAME* *BACKEND_DOMAIN:DEVICE_ID*

Attach the device with *DEVICE_ID* from *BACKEND_DOMAIN* to the domain *VMNAME*

.. option:: --option, -o

   Specify device-class specific option, use `name=value` format. You can
   specify this option multiple times.

.. option:: --persistent, -p

   Attach device persistently, which means have it attached also after qube restart.

aliases: a, at

detach
^^^^^^

| :command:`qvm-device` *DEVICE_CLASS* detach [-h] [--verbose] [--quiet] *VMNAME* *BACKEND_DOMAIN:DEVICE_ID*

Detach the device with *BACKEND_DOMAIN:DEVICE_ID* from domain *VMNAME*

aliases: d, dt


Device classes
==============

* block - block devices
* usb - USB devices
* pci - PCI devices

Authors
=======
| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
