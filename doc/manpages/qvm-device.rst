.. program:: qvm-device

=============================================
:program:`qvm-device` -- List/set VM devices
=============================================

Synopsis
========
| :command:`qvm-device` *DEVICE_CLASS* {list,ls,l} [*options*] <*vm-name*>
| :command:`qvm-device` *DEVICE_CLASS* {attach,at,a} [*options*] <*vm-name*> <*device*>
| :command:`qvm-device` *DEVICE_CLASS* {detach,dt,d} [*options*] <*vm-name*> [<*device*>]
| :command:`qvm-device` *DEVICE_CLASS* {info,i} [*options*] <*vm-name*> [<*device*>]
| :command:`qvm-*DEVICE_CLASS*` {list,ls,l,attach,at,a,detach,dt,d,info,i} [*options*] <*vmname*> ...

.. note:: :command:`qvm-block`, :command:`qvm-usb` and :command:`qvm-pci` are just aliases for :command:`qvm-device block`, :command:`qvm-device usb` and :command:`qvm-device pci` respectively.

Options
=======

.. option:: --help, -h

    Show this help message and exit

.. option:: --verbose, -v

   increase verbosity

.. option:: --quiet, -q

   decrease verbosity

.. option:: --list-device-classes

   list device classes

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

   Alias for `assign --required` for backward compatibility.

aliases: a, at

detach
^^^^^^

| :command:`qvm-device` *DEVICE_CLASS* detach [-h] [--verbose] [--quiet] *VMNAME* *BACKEND_DOMAIN:DEVICE_ID*

Detach the device with *BACKEND_DOMAIN:DEVICE_ID* from domain *VMNAME*.
If no device is given, detach all *DEVICE_CLASS* devices.

aliases: d, dt

assign
^^^^^^

| :command:`qvm-device` *DEVICE_CLASS* assign [-h] [--verbose] [--quiet] [--ro] *VMNAME* *BACKEND_DOMAIN:DEVICE_ID*

Assign the device with *DEVICE_ID* from *BACKEND_DOMAIN* to the domain *VMNAME*

.. option:: --option, -o

   Specify device-class specific option, use `name=value` format. You can
   specify this option multiple times. See below for options specific to
   different device classes.

.. option:: --ro

   Alias for the `read-only=yes` option. If you specify both `--ro` and
   `--option read-only=no`, `--ro` takes precedence.

.. option:: --required, -r

   Assign device persistently which means it will be required to the qube's startup and then automatically attached.

aliases: s

unassign
^^^^^^^^

| :command:`qvm-device` *DEVICE_CLASS* unassign [-h] [--verbose] [--quiet] *VMNAME* *BACKEND_DOMAIN:DEVICE_ID*

Remove assignment of device with *BACKEND_DOMAIN:DEVICE_ID* from domain *VMNAME*.
If no device is given, remove assignments of all *DEVICE_CLASS* devices.

aliases: u

info
^^^^

| :command:`qvm-device` *DEVICE_CLASS* info [-h] [--verbose] [--quiet] *VMNAME* *BACKEND_DOMAIN:DEVICE_ID*

Show info about the device with *DEVICE_ID* from *BACKEND_DOMAIN* attached to the domain *VMNAME*

aliases: i

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
* `permissive` - allow write access to most of PCI config space, instead of only selected whitelisted rregisters; a workaround for some PCI passthrough problems, potentially unsafe; default: `False`, accepted values: `True`, `False` (option absent)

mic
^^^

Microphone, or other audio input. Normally there is only one device of this
type - `dom0:mic`. Use PulseAudio settings in dom0 to select which input source
is used.
This type of device does not support options.

Authors
=======
| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Frédéric Pierret <frederic.pierret at qubes dash os dot org>
| Piotr Bartman-Szwarc <prbartman at invisiblethingslab dot com>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git
