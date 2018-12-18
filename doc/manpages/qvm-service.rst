.. program:: qvm-service

========================================================================
:program:`qvm-service` -- Manage (Qubes-specific) services started in VM
========================================================================

Synopsis
========
| :command:`qvm-service` [-l] <*vmname*>
| :command:`qvm-service` [-e|-d|-D] <*vmname*> <*service*>
| :command:`qvm-service` <*vmname*> <*service*> [on|off]

Options
=======
.. option:: --help, -h

    Show this help message and exit

.. option:: --list, -l

    List services (default action)

.. option:: --enable, -e

    Enable service

.. option:: --disable, -d

    Disable service

.. option:: --default, -D, --delete, --unset

    Reset service to its default state (remove from the list). Default state
    means "lets VM choose" and can depend on VM type (NetVM, AppVM etc).

.. option:: --verbose, -v

   increase verbosity

.. option:: --quiet, -q

   decrease verbosity

Supported services
==================

This list can be incomplete as VM can implement any additional service without
knowledge of qubes-core code.

meminfo-writer
    Default: enabled everywhere excluding NetVM

    This service reports VM memory usage to dom0, which effectively enables
    dynamic memory management for the VM.

    .. note::

        This service is managed by dom0 code and is not visible for *qvm-service* tool.

qubes-firewall
    Default: enabled only in ProxyVM

    Dynamic firewall manager, based on settings in dom0 (qvm-firewall, firewall tab in qubes-manager).
    This service is not supported in netvms.

qubes-network
    Default: enabled only in NetVM and ProxyVM

    Expose network for other VMs. This includes enabling network forwarding,
    MASQUERADE, DNS redirection and basic firewall.

qubes-update-check
    Default: enabled

    Notify dom0 about updates available for this VM. This is shown in
    qubes-manager as 'update-pending' flag.

cups
    Default: enabled only in AppVM

    Enable CUPS service. The user can disable cups in VM which do not need
    printing to speed up booting.

crond
    Default: disabled

    Enable CRON service.

network-manager
    Default: enabled in NetVM

    Enable NetworkManager. Only VM with direct access to network device needs
    this service, but can be useful in ProxyVM to ease VPN setup.

clocksync
    Default: disabled

    Enable NTPD (or equivalent) service. If disabled, VM will sync clock with
    selected VM (aka ClockVM) instead. ClockVM for particular VM can be set in
    policy of qubes.GetDate service, using target= parameter.

qubes-yum-proxy
    Deprecated name for qubes-updates-proxy.

qubes-updates-proxy
    Default: enabled in NetVM

    Provide proxy service, which allow access only to yum repos. Filtering is
    done based on URLs, so it shouldn't be used as leak control (pretty easy to
    bypass), but is enough to prevent some erroneous user actions.

yum-proxy-setup
    Deprecated name for updates-proxy-setup.

updates-proxy-setup
    Default: enabled in AppVM (also in templates)

    Setup yum at startup to use qubes-yum-proxy service.

    .. note::

       this service is automatically enabled when you allow VM to access updates
       proxy and disabled when you deny access to updates proxy.

disable-default-route
    Default: disabled

    Disables the default route for networking.  Enabling  this  service
    will  prevent the creation of the default route, but the VM will
    still be able to reach it's direct neighbors.  The functionality
    is implemented in /usr/lib/qubes/setup-ip.

disable-dns-server
    Default: disabled

    Enabling this service will result in an empty /etc/resolv.conf.
    The functionality is implemented in /usr/lib/qubes/setup-ip.


Authors
=======
| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
