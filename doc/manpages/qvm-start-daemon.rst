.. program:: qvm-start-daemon

:program:`qvm-start-daemon` -- start GUI/AUDIO for qube(s)
==========================================================

.. note::

   `qvm-start-gui` has been renamed to `qvm-start-daemon` as it handles now
   `gui` and `audio`.

Synopsis
--------

| :command:`qvm-start-daemon` [*options*] [--all] [--exclude *EXCLUDE*] [*VMNAME* ...]
| :command:`qvm-start-daemon` [*options*] --watch [--pidfile *PIDFILE*] [--all] [*VMNAME* ...]
| :command:`qvm-start-daemon` --notify-monitor-layout

Description
-----------

This tool starts the daemons that provide display and sound for qubes: the
GUI daemon (``qubes-guid``), which displays windows of a qube on the local
display server, and the audio daemon (``pacat-simple-vchan``), which connects
a qube's audio to the local sound server.

It is meant to run in the qube that serves as the GUI and/or Audio virtual
machine - that is, dom0 or a qube with the ``guivm`` and/or ``audiovm``
service enabled (see :program:`qvm-service`). Only daemons for the enabled
services are started; when neither service is enabled, the tool does nothing
(unless :option:`--force` is given). It is normally started automatically as
part of the GUI/Audio qube session in ``--watch --all`` mode; running it
manually is mostly useful to restart daemons or debug problems.

The tool operates in one of three modes:

* Without :option:`--watch`, it starts the daemons for those of the given
  qubes (or, with ``--all``, all qubes) that are currently running, then
  exits. Daemons that are already running are left alone, so it is safe to
  run repeatedly.

* With :option:`--watch`, it keeps running, listens for qube startup events
  and starts the daemons for each qube as needed. In this mode it also
  propagates monitor layout and keyboard layout changes of the local session
  to the qubes. Only one watching instance may run at a time (guarded by a
  lock on the pidfile).

* With :option:`--notify-monitor-layout`, it does not start anything itself;
  instead it notifies the running ``--watch`` instance (via the pidfile) to
  re-send the current monitor layout to the qubes, e.g. after connecting an
  external display.

Options
-------

.. option:: --help, -h

   show this help message and exit

.. option:: --debug, -d

   Show debug messages

.. option:: --verbose, -v

   increase verbosity

.. option:: --quiet, -q

   decrease verbosity

.. option:: --all

   perform the action on all qubes

.. option:: --exclude=EXCLUDE

   exclude the qube from :option:`--all`

.. option:: --watch

   Keep watching for further domain startups and start the daemons for them
   as they come up. Cannot be used with :option:`--notify-monitor-layout`.

.. option:: --force-stubdomain

   Start GUI to stubdomain-emulated VGA, even if gui-agent is running in the
   VM. Applies to HVM qubes, whose emulated VGA output is served by a
   stubdomain.

.. option:: --force

   Force running, even if this isn't GUI/Audio domain. GUI domain is a domain
   with 'guivm' qvm-service enabled. Similarly for Audio domain it is
   'audiovm' qvm-service.

.. option:: --kde

   Set KDE specific arguments to gui-daemon - required for proper windows
   decoration on KDE.

.. option:: --pidfile

   Pidfile path to create in --watch mode. The default is
   :file:`$XDG_RUNTIME_DIR/qvm-start-daemon.pid` (or
   :file:`~/.qvm-start-daemon.pid` when ``XDG_RUNTIME_DIR`` is not set).

.. option:: --notify-monitor-layout

   Notify running instance in --watch mode about changed monitor layout

.. option:: --version

   Show program's version number and exit

Authors
-------

| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Wojtek Porczyk <woju at invisiblethingslab dot com>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
