.. program:: qvm-device

=============================================
:program:`qvm-device` -- List/set VM devices
=============================================

Synopsis
========
| :command:`qvm-device` [*options*] *DEVICE_CLASS* {list,ls,l} <*vm-name*>
| :command:`qvm-device` [*options*] *DEVICE_CLASS* {attach,at,a} <*vm-name*> <*device*>
| :command:`qvm-device` [*options*] *DEVICE_CLASS* {detach,dt,d} <*vm-name*> [<*device*>]
| :command:`qvm-*DEVICE_CLASS*` [*options*] {list,ls,l,attach,at,a,detach,dt,d} <*vmname*> ...

Tool can be called either as `qvm-device *DEVICE_CLASS* ...`, or
`qvm-*DEVICE_CLASS* ...`. The latter is used for `qvm-pci`, `qvm-block` etc.

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
   specify this option multiple times. See below for options specific to
   different device classes.

.. option:: --ro

   Alias for the `read-only=yes` option. If you specify both `--ro` and
   `--option read-only=no`, `--ro` takes precedence.

.. option:: --persistent, -p

   Attach device persistently, which means have it attached also after qube restart.

aliases: a, at

detach
^^^^^^

| :command:`qvm-device` *DEVICE_CLASS* detach [-h] [--verbose] [--quiet] *VMNAME* *BACKEND_DOMAIN:DEVICE_ID*

Detach the device with *BACKEND_DOMAIN:DEVICE_ID* from domain *VMNAME*.
If no device is given, detach all *DEVICE_CLASS* devices.

aliases: d, dt


Device classes
==============

block
^^^^^

Block device. Available options:

* `frontend-dev` - device node in target domain, by default first available, starting from `xvdi`
* `read-only` - attach device in read-only mode; default depends on device, if possible - attach read-write; if device itself is read-only, only read-only attach is allowed
* `devtype` - type of device - either `disk` or `cdrom`; default: `disk`

usb
^^^

USB device. This type of device does not support options.

pci
^^^

PCI device. Only dom0 expose such devices. One should be very careful when attaching this type of devices, because some of them are strictly required to stay in dom0 (for example host bridge). Available options:

* `no-strict-reset` - allow to attach device even if it does not support any reliable reset operation; switching such device to another domain (without full host restart) can be a security risk; default: `False`, accepted values: `True`, `False` (option absent)


Authors
=======
| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
