.. program:: qvm-firewall

:program:`qvm-firewall` -- Manage VM outbound firewall
======================================================

Synopsis
--------

:command:`qvm-firewall` [-h] [--verbose] [--quiet] [--reload] *VMNAME* add [--before=*RULE_NUMBER*]   *RULE*

:command:`qvm-firewall` [-h] [--verbose] [--quiet] [--reload] *VMNAME* del [--rule-no=*RULE_NUMBER*] [*RULE*]

:command:`qvm-firewall` [-h] [--verbose] [--quiet] [--reload] [--raw] *VMNAME* list

:command:`qvm-firewall` [-h] [--verbose] [--quiet] [--reload] *VMNAME* reset

Options
-------

.. option:: --help, -h

   show help message and exit

.. option:: --verbose, -v

   increase verbosity

.. option:: --quiet, -q

   decrease verbosity

.. option:: --reload, -r

   force reload of rules even when unchanged

.. option:: --raw

   in combination with `list` action, print raw rules

.. option:: --version

   Show program's version number and exit


Actions description
-------------------

Available actions:

* add - add specified rule. See `Rule syntax` section below.

* del - delete specified rule. The rule to remove can be selected either by rule number using :option:`--rule-no`
  or by specifying the rule itself using the same syntax used for adding it.

* list - list all the rules for a given VM.

* reset - remove all firewall rules and reset to default (accept all connections)


Rule syntax
-----------

A single rule is built from:
 - action - either ``drop`` or ``accept``
 - zero or more matches

Selected action is applied to packets when all specified matches match,
further rules are not evaluated. If none of the rules match, the default
firewall policy is ``drop``.

Supported matches:
 - ``dsthost`` - destination host or network. Can be either IP address in CIDR
   notation, or a host name. Both IPv4 and IPv6 are supported by the rule syntax.
   In order to allow reuse of ``--raw`` output, ``dst4`` and ``dst6`` are accepted
   as synonyms.

 - ``dst4`` - see ``dsthost``

 - ``dst6`` - see ``dsthost``

 - ``proto`` - specific IP protocol. Supported values: ``tcp``, ``udp``,
   ``icmp``.

 - ``dstports`` - destination port or ports range. Can be either a single port
   or a range separated by ``-``. Valid only together with ``proto=udp`` or
   ``proto=tcp``.

 - ``icmptype`` - ICMP message type, specified as numeric value. Valid only
   together with ``proto=icmp``.

 - ``specialtarget`` - predefined target. Currently the only supported value is
   ``dns``. This can be combined with other matches to narrow it down.

 - ``expire`` - the rule matches only until the specified time and is then
   automatically removed. The time can be given either as number of seconds
   since 1/1/1970 or as ``+seconds``, a relative time (``+300`` means 5
   minutes from now).

Authors
-------

| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Wojtek Porczyk <woju at invisiblethingslab dot com>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
