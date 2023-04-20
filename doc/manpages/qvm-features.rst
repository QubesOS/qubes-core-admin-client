.. program:: qvm-features

:program:`qvm-features` -- manage domain's features
===================================================

Synopsis
--------

:command:`qvm-features` [-h] [--verbose] [--quiet] *VMNAME* [*FEATURE* [*VALUE*]]

Options
-------

.. option:: --help, -h

   show this help message and exit

.. option:: --verbose, -v

   increase verbosity

.. option:: --quiet, -q

   decrease verbosity

.. option:: --unset, --default, --delete, -D

   Unset the feature.

Description
-----------

This command is used to manually manage the *features* of the domain. The
features are key-value pairs with both key and value being strings. They are
used by extensions to store information about the domain and make policy
decisions based on them. For example, they may indicate that some specific
software package was installed inside the template and the domains based on it
have some specific capability.

.. warning::

   The features are normally managed by the extensions themselves and you should
   not change them directly. Strange things might happen otherwise.

Some extensions interpret the values as boolean. In this case, the empty string
means :py:obj:`False` and non-empty string (commonly ``'1'``) means
:py:obj:`True`. An absence of the feature means "default", which is
extension-dependent. In most cases the default value for feature is retrieved
from a qube template.

List of known features
----------------------

.. warning::

   This list of features may be incomplete, because extensions are free to use any
   values, without registering them anywhere.

gui
^^^

Qube has gui-agent installed. Setting this feature to :py:obj:`True` enables GUI
based on a gui-agent installed inside the VM.
See also `gui-emulated` feature.

If neither `gui` nor `gui-emulated` is set, emulated VGA is used (if
applicable for given VM virtualization mode).

gui-emulated
^^^^^^^^^^^^

Qube provides GUI through emulated VGA. Setting this feature to
:py:obj:`True` enables emulated VGA output. Note that when gui-agent connects to
actual VM, emulated VGA output is closed (unless `debug` property is set to
:py:obj:`True`). It's possible to open emulated VGA output for a running qube,
regardless of this feature, using `qvm-start-daemon --force-stubdomain QUBE_NAME`
command.

This feature is applicable only when qube's `virt_mode` is set to `hvm`.
See also `gui` feature.

If neither `gui` nor `gui-emulated` is set, emulated VGA is used (if
applicable for given VM virtualization mode).

gui-\*, gui-default-\*
^^^^^^^^^^^^^^^^^^^^^^

GUI daemon configuration. See `/etc/qubes/guid.conf` for a list of supported
options.

To change a given GUI option for a specific qube, set the `gui-{option}`
feature (with underscores replaced with dashes). For example, to enable
`allow_utf8_titles` for a qube, set `gui-allow-utf8-titles` to `True`.

To change a given GUI option globally, set the `gui-default-{option}` feature
on the GuiVM for that qube.

input-dom0-proxy
^^^^^^^^^^^^^^^^

When set to :py:obj:`True`, Qubes input proxy sender services will start
for every non-virtual input devices available in dom0 on domain start.


qrexec
^^^^^^

Qube has qrexec agent installed - i.e. it is possible to request staring a
command/service in there.

Default: assume qrexec not installed (do not wait for it while starting the
qube)

rpc-clipboard
^^^^^^^^^^^^^

Use `qubes.ClipboardCopy` and `qubes.ClipboardPaste` qubes RPC services to
fetch/send clipboard content from/to this qube, instead of using GUI protocol.
This is supported (and required) by Qubes Windows Tools.

Default: use GUI protocol for clipboard operations

no-monitor-layout
^^^^^^^^^^^^^^^^^

When set to :py:obj:`True`, monitor layout is not sent to this qube. That is
avoid calling `qubes.SetMonitorLayout` in this qube.

Default: send monitor layout

internal
^^^^^^^^

Internal qubes (with this feature set to :py:obj:`True`) are not included in the
menu, not available in GUI tools (e.g in Global Settings as a default net qube)
and generally hidden from normal usage. It is not recommended to set this
feature manually.

Default: not internal VM

appmenus-legacy
^^^^^^^^^^^^^^^

Generate legacy menu entries, using `qubes-desktop-run` command inside a VM,
instead of `qubes.StartApp` qrexec service. This is used for qubes imported from
previous Qubes version.

Default: new style menu entries, using `qubes.StartApp` service

appmenus-dispvm
^^^^^^^^^^^^^^^

Generate menu entries for starting applications in Disposable VM based on given
AppVM, instead of this AppVM directly.

Default: create menu entries for AppVM itself

qubes-firewall
^^^^^^^^^^^^^^

Setting this to :py:obj:`True` means that qube support enforcing firewall rules
set with `qvm-firewall` command.

Default: assume qubes-firewall not enforced

net.fake-ip
^^^^^^^^^^^

Hide the real IP of the qube from it, and configure it with value set to this
feature. Note that you can assign the same `net.fake-ip` address to multiple
qubes and it shouldn't cause any troubles (unless you want to two such qubes
communicate with each other). This feature does not affect address used in
firewall rules, routing tables etc.

Default: do not hide IP (qube's `ip` property) from the qube

net.fake-gateway
^^^^^^^^^^^^^^^^

Hide the real gateway of the qube from it, and configure it with value set to
this feature.

Default: do not hide geteway (qube's `gateway` property) from the qube

net.fake-netmask
^^^^^^^^^^^^^^^^

Hide the real netmask of the qube from it, and configure it with value set to
this feature.

Default: do not hide netmask (qube's `netmask` property) from the qube

updates-available
^^^^^^^^^^^^^^^^^

There are updates available. In most cases it is useful to (only) read this
feature to check if qube needs to be updated.

Default/no value: no updates available

video-model
^^^^^^^^^^^

Choose video card modes emulated by QEMU for this qube. For available values see
libvirt documentation about <video><model type=...> element:
https://libvirt.org/formatdomain.html#elementsVideo
Some systems (Windows) works better with 'cirrus' model set here.
Setting this feature to `none` disables emulated video card.

Default: vga

pci-e820-host
^^^^^^^^^^^^^

Enable e820_host option in Xen domU config if qube has any PCI device assigned.
This is option is needed for some PCI device drivers to correctly allocate
memory. Refer to Xen documentation for details.

Default: yes if qube has any PCI device, otherwise no

linux-stubdom
^^^^^^^^^^^^^

Use Linux-based stubdomain for running device model (qemu). This makes use of
recent qemu upstream version. If disabled, use MiniOS-based stubdomain with old
qemu fork (aka qemu-traditional). This applies only to `hvm` `virt_mode`, for
other modes it is ignored.

Default: True

tag-created-vm-with
^^^^^^^^^^^^^^^^^^^

When a qube with this feature create a new VM, it gets extra tags listed in this
feature value (separated with space) automatically. Tags are added before qube
creation finishes.

set-created-guivm
^^^^^^^^^^^^^^^^^

When a qube with this feature create a new VM, it sets to the new VM its `guivm`
property value to `set-created-guivm` feature value.

supported-feature.*
^^^^^^^^^^^^^^^^^^^

Advertised "features" as supported by given VM. Template-based qubes support all
features advertised by their template (in other words, to check for features
supported by a template-based qube, look at `supported-feature.*` on its
template). Supported feature `x` is noted as `supported-feature.x` with value of
`1`. Not supported feature is not listed at all. Other values are not supported.

supported-service.*
^^^^^^^^^^^^^^^^^^^

Advertised "qvm-services" as supported by given VM. Template-based qubes support all
services advertised by their template (in other words, to check for features
supported by a template-based qube, look at `supported-service.*` on its
template). Supported qvm-service `x` is noted as `supported-service.x` with value of
`1`. Not supported service is not listed at all. Other values are not supported.

supported-rpc.*
^^^^^^^^^^^^^^^

Advertised RPC services as supported by given VM. Template-based qubes support
all services advertised by their template, in addition to services advertised by
this very VM (in other words, to check for features supported by a
template-based qube, look at `supported-rpc.*` on both its template and
the VM itself). Supported RPC service `x` is noted as `supported-rpc.x`
with value of `1`. Not supported RPC service is not listed at all. Other values
are not supported.

qubes-agent-version
^^^^^^^^^^^^^^^^^^^

Qubes agent version installed in the template/standalone. It contains just
major.minor number (no patch number). Can be used to check if template was
updated to the current qubes version after importing from older release.

stubdom-qrexec
^^^^^^^^^^^^^^

Set this to value `1` to enable qrexec agent in the stubdomain. This feature can
be set on a qube with virt_mode HVM, to support USB passthrough via stubdomain.
It is ignored on non-HVM qubes. Useful for Windows qube for example.

vm-config.*
^^^^^^^^^^^

These features are exposed to qubesdb inside the qube in the `/vm-config` tree.
Can be used to pass external configuration to inside the qube. To read, use
`qubesdb-read`: for a feature named `vm-config.feature_name` use
`qubesdb-read /vm-config/feature_name`.

audio-model
^^^^^^^^^^^

Enable emulated audio for this qube. This feature can be set on a qube with
virt_mode HVM to support audio passthrough (both input and output) via emulated
device instead of audio agent installed in the qube itself. The value is audio
model to be emulated, supported values are `ich6`, `sb16`, `ac97`, `es1370`.
Recommended is `ich6`. This is useful to get audio in a Windows qube.

uefi
^^^^

Boot the HVM qube via UEFI boot, instead of legacy one. Support for this boot
mode is experimental and may not work in all the cases. It is ignored for
non-HVM qubes.

Authors
-------

| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Wojtek Porczyk <woju at invisiblethingslab dot com>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
