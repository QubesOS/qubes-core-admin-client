.. program:: qvm-clone

:program:`qvm-clone` -- Clones an existing VM by copying all its disk files
===========================================================================

Description
-----------

:program:`qvm-clone` creates a new qube from an existing one. It copies the
source qube's persistent volumes and, where supported by the destination
class, its properties, features, tags, firewall rules, and application-menu
metadata. The source qube is not modified.

By default the clone has the same class and uses the configured default pools,
while preserving explicit non-default pool placement from the source. Use
:option:`-P` to place all non-snapshot volumes in one pool, or :option:`--pool`
to choose pools per volume. These two forms cannot be combined.

Synopsis
--------
:command:`qvm-clone` [*options*] *VMNAME* *NEWVM*

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

.. option:: --pool=VOLUME=POOL, -p VOLUME=POOL

    Specify the pool to use for the specific volume

.. option:: --ignore-errors

    Log errors encountered when creating metadata, but continue with clone
    operation. Useful if qvm-appmenus call fails from an AdminVM during clone.

.. option:: --quiet, -q

    Be quiet

.. option:: --verbose, -v

    Increase verbosity

.. option:: --version

   Show program's version number and exit

Examples
--------

Clone ``work`` as ``work-copy``::

   qvm-clone work work-copy

Place all persistent clone volumes in the ``external`` pool::

   qvm-clone -P external work work-copy

Choose pools for individual volumes::

   qvm-clone -p private=external -p root=fast work work-copy

Authors
-------
| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Bahtiar `kalkin-` Gadimov <bahtiar at gadimov dot de> 

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git
