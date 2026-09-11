.. program:: qvm-clone

:program:`qvm-clone` -- Clones an existing VM by copying all its disk files
===========================================================================

Synopsis
--------
:command:`qvm-clone` [*options*] *VMNAME* *NEWVM*

Description
-----------

This tool creates a new qube that is a copy of an existing one. Besides the
content of all storage volumes, the clone receives the source qube's
properties (except identity ones like name or UUID), tags (except the
automatic ``created-by-*`` ones), features, notes, firewall rules, device
assignments and application menu settings.

The source qube is left untouched and the clone is completely independent of
it afterwards - unlike a template and qubes based on it, the clone and the
source share no storage. The clone is not started automatically.

To ensure the copied volumes are in a consistent state, shut the qube down
before cloning it.

Options
-------

.. option:: --help, -h

    Show this help message and exit

.. option:: --class=CLASS, -C CLASS

    Create VM of different class than source VM. The tool will try to copy as
    much as possible data/metadata from source VM, but some information may be
    impossible to preserve (for example target VM have no matching properties).

.. option:: -P POOL

    Pool to use for the new domain. All volumes besides snapshots volumes are
    imported in to the specified POOL. THIS IS WHAT YOU WANT TO USE NORMALLY.
    Cannot be used together with :option:`--pool`.

.. option:: --pool=VOLUME=POOL, -p VOLUME=POOL

    Specify the pool to use for the specific volume (e.g.
    ``--pool private=lvm-pool``). Can be specified multiple times, for
    different volumes. Cannot be used together with :option:`-P`. If neither
    is given, each volume is cloned to the pool used by the source qube.

.. option:: --ignore-errors

    Log errors encountered when creating metadata, but continue with clone
    operation. Useful if qvm-appmenus call fails from an AdminVM during clone.

.. option:: --quiet, -q

    Be quiet

.. option:: --verbose, -v

    Increase verbosity

.. option:: --version

   Show program's version number and exit

Authors
-------
| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Bahtiar `kalkin-` Gadimov <bahtiar at gadimov dot de>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git
