.. program:: qvm-create

:program:`qvm-create` -- create new domain
==========================================

Synopsis
--------

:command:`qvm-create` [-h] [--verbose] [--quiet] [--force-root] [--class *CLS*] [--property *NAME*=*VALUE*] [--pool *POOL_NAME:VOLUME_NAME*] [--template *VALUE*] --label *VALUE* [--root-copy-from *FILENAME* | --root-move-from *FILENAME*] *VMNAME*
:command:`qvm-create` --help-classes

Options
-------

.. option:: --help, -h

   show help message and exit

.. option:: --verbose, -v

   Increase verbosity.

.. option:: --quiet, -q

   Decrease verbosity.

.. option:: --help-classes

   List available qube classes and exit. See below for short description.

.. option:: --class, -C

   The new domain class name (default: **AppVM** for
   :py:class:`qubes.vm.appvm.AppVM`).

.. option:: --prop=NAME=VALUE, --property=NAME=VALUE

   Set domain's property, like "internal", "memory" or "vcpus". Any property may
   be set this way, even "qid".

.. option:: --template=VALUE, -t VALUE

   Specify the TemplateVM to use, when applicable. This is an alias for
   ``--property template=VALUE``.

.. option:: --label=VALUE, -l VALUE

   Specify the label to use for the new domain (e.g. red, yellow, green, ...).
   This in an alias for ``--property label=VALUE``.

.. option:: --root-copy-from=FILENAME, -r FILENAME

   Use provided :file:`root.img` instead of default/empty one (file will be
   *copied*). This option is mutually exclusive with :option:`--root-move-from`.

.. option:: --root-move-from=FILENAME, -R FILENAME

   Use provided :file:`root.img` instead of default/empty one (file will be
   *moved*). This option is mutually exclusive with :option:`--root-copy-from`.

.. option:: -P POOL

    Pool to use for the new domain. All volumes besides snapshots volumes are
    imported in to the specified POOL. ~HIS IS WHAT YOU WANT TO USE NORMALLY.

.. option:: --pool=POOL:VOLUME, -p POOL:VOLUME

    Specify the pool to use for the specific volume

Qube classes
------------

Qube class (or type) specify basic features of it, mostly what data persists
across reboots and what properties qube have.

AppVM
^^^^^

Default qube class, for template-based qubes. In this type, root volume is used
from its template and changes made to it are discarded at qube restart. Changes
in qube's private volume are persistent.

StandaloneVM
^^^^^^^^^^^^

This qube class have both root and private volumes persistent. This qube type
does not have template property.

TemplateVM
^^^^^^^^^^

A qube that can be used as a template for `AppVM`. Otherwise very similar to
`StandaloneVM`.

DispVM
^^^^^^

A disposable qube - no data persists across qube restarts. It must have template
set to an `AppVM` instance that have `dispvm_allowed` property set to true (see
:manpage:`qvm-prefs(1)`).

Authors
-------

| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Wojtek Porczyk <woju at invisiblethingslab dot com>
| Bahtiar `kalkin-` Gadimov <bahtiar at gadimov dot de> 

.. vim: ts=3 sw=3 et tw=80
