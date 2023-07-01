.. program:: qvm-prefs

:program:`qvm-prefs` -- List/set various per-VM properties
==========================================================

Synopsis
--------

:command:`qvm-prefs` qvm-prefs [-h] [--verbose] [--quiet] [--force-root] [--help-properties] *VMNAME* [*PROPERTY* [*VALUE* \| --default ]]

Options
-------

.. option:: --help, -h

   Show help message and exit.

.. option:: --help-properties

   List available properties with short descriptions and exit.

.. option:: --hide-default

   Do not show properties that are set to the default value.

.. option:: --verbose, -v

   Increase verbosity.

.. option:: --quiet, -q

   Decrease verbosity.

.. option:: --default, -D

   Reset property to its default value.

.. option:: --get, -g

   Ignored; for compatibility with older scripts.

.. option:: --set, -s

   Ignored; for compatibility with older scripts.


Property values
===============

Some properties may have strict type, here is description of available values.

bool
----

Accepted values for true: ``True``, ``true``, ``on``, ``1``
Accepted values for false: ``False``, ``false``, ``off``, ``0``

For example to enable debug mode, use: ``qvm-prefs vmname debug on``

VM
--

Reference to a VM can be either a VM name, or empty string for no VM (remember
to quote it, empty string is not the same as lack of argument!).

For example to change netvm to sys-whonix, use: ``qvm-prefs vmname netvm
sys-whonix``. Or to make VM offline, use: ``qvm-prefs vmname netvm ""``.


Common properties
=================

This list is non-exhaustive. For authoritative listing, see
:option:`--help-properties` and documentation of the source code.

autostart
    Property type: bool

    Start the VM during system startup. The default netvm is autostarted
    regardless of this setting.

debug
    Property type: bool

    Enables debug mode for VM. This can be used to turn on/off verbose logging
    in many Qubes components at once (gui virtualization, VM kernel, some other
    services). Also, for HVM, this will show VGA output, regardless of GUI agent
    being installed or not.

default_dispvm
    Property type: VM

    Which Disposable VMs should be userd when requested by this VM, by default.
    VM may request different DispVM, if qrexec policy allows that.

default_user
    Accepted values: username

    Default user used by :manpage:`qvm-run(1)`. Note that it make sense only on
    non-standard template, as the standard one always have "user" account.

    TemplateBasedVM uses its template's value as a default.

template_for_dispvms
    Property type: bool

    Allow to use this VM as a base AppVM for Disposable VM. I.e. start this
    AppVM as Disposable VM.

include_in_backups
    Property type: bool

    Control whenever this VM will be included in backups by default (for now
    works only in qubes-manager). You can always manually select or
    deselect any VM for backup.

ip
    Accepted values: valid IPv4 address

    IP address of this VM, used for inter-vm communication.

kernel
    Accepted values: kernel version, empty

    Kernel version to use. Setting to empty value will use bootloader installed
    in root volume (of VM's template) - available only for HVM.

    TemplateBasedVM uses its template's value as a default.

kernelopts
    Accepted values: string

    VM kernel parameters (available only for PV VMs). This can be used to
    workaround some hardware specific problems (eg for NetVM). For VM without
    PCI devices default means inherit this value from the VM template (if any).
    Some helpful options (for debugging purposes): ``earlyprintk=xen``,
    ``init=/bin/bash``

    TemplateBasedVM uses its template's value as a default.

label
    Accepted values: ``red``, ``orange``, ``yellow``, ``green``, ``gray``,
    ``blue``, ``purple``, ``black``

    Color of VM label (icon, appmenus, windows border). If VM is running,
    change will be applied at first VM restart.

mac
    Accepted values: MAC address, ``auto``

    Can be used to force specific of virtual ethernet card in the VM. Setting
    to ``auto`` will use automatic-generated MAC - based on VM id. Especially
    useful when licensing requires a static MAC address.
    For template-based HVM ``auto`` mode means to clone template MAC.

maxmem
    Accepted values: memory size in MB

    Maximum memory size available for this VM. Dynamic memory management (aka
    qmemman) will not be able to balloon over this limit. For VMs with
    qmemman disabled, this will be overridden by *memory* property (at VM
    startup).

    TemplateBasedVM uses its template's value as a default.

memory
    Accepted values: memory size in MB

    Initial memory size for VM. This should be large enough to allow VM startup
    - before qmemman starts managing memory for this VM. For VM with qmemman
    disabled, this is static memory size.

    TemplateBasedVM uses its template's value as a default.

name
    Accepted values: alphanumerical name

    Name of the VM. Cannot be changed.

netvm
    Property type: VM

    To which NetVM connect. Default value (`--default` option) will follow
    system-global default NetVM (managed by qubes-prefs). Setting to empty name
    will disable networking in this VM.

provides_network
    Property type: bool

    Should this VM provide network to other VMs. Setting this property to
    ``True`` will allow to set this VM as ``netvm`` to other VMs.

qrexec_timeout
    Accepted values: timeout in seconds

    How long to wait for VM boot and qrexec agent connection. After this
    timeout, if qrexec agent is still not connected, VM is forcefully shut down.
    Ignored if qrexec not installed at all (`qrexec` feature not set, see
    :manpage:`qvm-features(1)`).

    TemplateBasedVM uses its template's value as a default.

stubdom_mem
    Accepted values: memory in MB

    Amount of memory to allocate to stubdomain. By default let Xen choose
    sensible value. This property is mostly for debugging early stubdomain
    implementations and may be removed in the future, without notice.

template
    Property type: VM

    TemplateVM on which VM is based. It can be changed only when VM isn't running.

vcpus
    Accepted values: no of CPUs

    Number of CPU (cores) available to VM. Some VM types (eg DispVM) will not
    work properly with more than one CPU.

    TemplateBasedVM uses its template's value as a default.

virt_mode
    Accepted values: ``hvm``, ``pvh``, ``pv``

    Virtualisation mode in which VM should be started. ``hvm`` allows
    installation of operating system without Xen-specific integration.

    TemplateBasedVM uses its template's value as a default.

Authors
-------

| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Wojtek Porczyk <woju at invisiblethingslab dot com>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
