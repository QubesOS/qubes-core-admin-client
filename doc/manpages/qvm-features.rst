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

.. option:: --version

   Show program's version number and exit

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

Feature managed by the `system` must not be modified by users.

List of known features
----------------------

.. warning::

   This list of features may be incomplete, because extensions are free to use any
   values, without registering them anywhere.

boot-mode.\*
^^^^^^^^^^^^

Boot mode information. Boot modes allow qubes to provide the user features that
are controlled via kernel parameters. Each boot mode has one or more kernel
parameters associated with it. If a qube is booted in a particular boot mode,
that boot mode's kernel parameters are appended to the qube's usual kernel
command line, activating the corresponding features within the VM. Templates
that support toggling features in this way can advertise boot modes, which will
then be shown in the settings dialog of Qube Manager. Templates can also specify
default boot modes for themselves and for AppVMs based on them.

All VMs have an implicitly defined bootmode, `default`, which appends no
additional kernel parameters. It is used as a fallback in the event a template
does not specify any boot modes, or there is no valid bootmode set.

boot-mode.active
^^^^^^^^^^^^^^^^

The default boot mode this qube will use. This boot mode option is expected to
be set by the template and should not be modified by the user. The user can
override this boot mode by setting a boot mode in Qube Manager, or by setting
the `bootmode` property with `qvm-prefs`.

boot-mode.appvm-default
^^^^^^^^^^^^^^^^^^^^^^^

The default boot mode AppVMs based on this template will use. This boot mode
option is expected to be set by the template and should not be modified by the
user. The user can override this boot mode by setting default boot mode for
derived AppVMs in Qube Manager, or by setting the `appvm_default_bootmode`
property with `qvm-prefs`.

boot-mode.kernelopts.\*
^^^^^^^^^^^^^^^^^^^^^^^

A boot mode supported by this qube. The boot mode's ID is specified by the
last dot-separated word in the feature key, while the boot mode's kernel
options are specified by the feature value.

boot-mode.name.\*
^^^^^^^^^^^^^^^^^

The user-visible pretty name for a boot mode. The ID of the boot mode with the
given pretty name is specified by the last dot-separated word in the feature
key, while the pretty name is specified by the feature value.

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
and generally hidden from normal usage (including not showing as a Qrexec target
for `Ask` rules. It is not recommended to set this feature manually. If this
feature is set to a template, applications may consider qubes based on this
template as internal also.

Default: not internal VM

anon-timezone
^^^^^^^^^^^^^

Do not expose the system timezone to the VM.

Default: expose the timezone in the VM via the
``/qubes-timezone`` key in QubesDB.

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

memory-hotplug
^^^^^^^^^^^^^^

Use memory hotplug for dynamic memory balancing. When enabled, qube will be
started with only initial memory assigned and qmemman may give it more memory
later via hotplug. When disabled, qube is started with maximum memory assigned
and balloon driver in qube's kernel returns unused memory at startup (this does
delay qube startup by few seconds).
Support is detected by looking for `memory-hotplug-supported` (empty) file in
dom0-provided kernel directory, or for `supported-feature.memory-hotplug`
feature - for in-qube kernel.

Default: yes if support in the qube kernel is detected, otherwise no.

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

service.*
^^^^^^^^^

Enabled/disabled "qvm-services". Values can be either `1` for enabled service,
or empty string for disabled service.
See :manpage:`qvm-service(1)` for details.

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

app-dispvm.*
^^^^^^^^^^^^

These features are used to cause a given application (identified by app ID)
to open files and URLs in a disposable VM.  It works by changing the value of
`XDG_DATA_DIRS` so that applications see `qvm-open-in-dvm.desktop` as the only
way to open any file or URL.  It is known to work with Thunderbird
(app ID `mozilla-thunderbird.desktop`) and Element (app ID `im.riot.Riot` for
the flatpak and `io.element.Element` for the non-flatpak version).  It may
break icons in some applications.  Please report a bug if `app-dispvm.*`
breaks an application.

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

skip-update
^^^^^^^^^^^

By setting this feature to `1` for TemplateVMs and StandaloneVMs, you will not
receive notifications if they are outdated or EOL. They will not be targeted for
update via `qubes-vm-update` unless explicitly targeted with `--target` option.
Similarly, updater GUI will not select them for update.

prohibit-start
^^^^^^^^^^^^^^

Prevents qube from being started in anyway. By setting `prohibit-start` feature
value of a qube to any non-empty string, the system will refuse to start it
at all conditions (via qvm-run, qrexec, Qube Manager, ...). This is useful for
known compromised qubes, awating some forensic analysis; templates user really
need to keep in the original, unmodified state; qubes user want to re-configure
and need not automatically started but the qube is a target of frequent qrexec
calls. Feature value could contain the rationale for the start ban.

Note: `prohibit-start` for a TemplateVM does not forbid start of AppVMs based
on it.

preload-dispvm-max
^^^^^^^^^^^^^^^^^^

Number of disposables to preload. Upon setting, the quantity of running
preloaded disposables will be adjusted to match the maximum configured, if there
is not enough of them and there is enough available memory on the system, new
ones will be created, if there are more than enough, the excess will be removed.

|
| **Valid on**: disposable template
| **Type**: `int`
| **Default**: `0`

preload-dispvm
^^^^^^^^^^^^^^

Space separated list of preloaded disposables originated from the disposable
template. Preloaded disposables are disposables that run in the background
waiting for use, specially designed for minimal waiting time to open
applications in a fresh disposable.

Preloaded disposables have its GUI applications entries hidden and are paused to
avoid user mistakes, as it is not intended to use them directly. To use them,
target the disposable template to start a service in a disposable, instead of
creating a new disposable, calls will be redirected to the first preloaded
disposable in the list. As soon as the preloaded disposable is requested to be
used, it is removed from the `preload-dispvm` list, GUI applications entries
become visible, followed by a new disposable being preloaded.

|
| **Managed by**: system
| **Valid on**: disposable template
| **Type**: `str`
| **Default**: empty

preload-dispvm-complete
^^^^^^^^^^^^^^^^^^^^^^^

If `True`, preloaded disposable has completed all necessary steps to be usable.

|
| **Managed by**: system
| **Valid on**: preloaded disposables
| **Type**: `boolean`
| **Default**: `False`

preload-dispvm-requested
^^^^^^^^^^^^^^^^^^^^^^^^

If `True`, preloaded disposable has been requested for use and is running the
procedures to mark it as used.

|
| **Managed by**: system
| **Valid on**: preloaded disposables
| **Type**: `boolean`
| **Default**: `False`

preload-dispvm-used
^^^^^^^^^^^^^^^^^^^

If `True`, preloaded disposable has been used.

|
| **Managed by**: system
| **Valid on**: preloaded disposables
| **Type**: `boolean`
| **Default**: `False`

custom-persist.*
^^^^^^^^^^^^^^^^

Adds a bind-dirs element in an AppVM where `custom-persist` service is
enabled. The `custom-persist.*` key can take any arbitrary name and will
have no effect on the feature behaviour. The value must be the absolute path to
the file or directory that need to be added to the bind-dirs list.
The entry value can be prefixed by settings to pre-create the resource in
``/rw/bind-dirs`` before bind-mounting it . When using the pre-creation
settings, the feature value must respect the following format:
``<file|dir>:<owner>:<group>:<mode>:<absolute path>``.

expert-mode
^^^^^^^^^^^
Allows expert mode for specific domain(s) or the entire system if it is enabled
for the GUIVM (dom0 by default). At the time of writing this documentation, the
only recognized feature is the `Debug Console` in Qui Domains systray widget.


End user specific features
--------------------------

Features with the `x-` prefix are specifically meant for end users and will
never be used for internal Qubes OS features.

Authors
-------

| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Marek Marczykowski-Górecki <marmarek at invisiblethingslab dot com>
| Wojtek Porczyk <woju at invisiblethingslab dot com>
| Demi Marie Obenour <demi at invisiblethingslab dot com>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
