.. program:: qvm-template

:program:`qvm-template` -- Manage template VMs
==============================================

Synopsis
--------

:command:`qvm-template` [-h] [--repo-files *REPO_FILES*] [--keyring *KEYRING*] [--updatevm *UPDATEVM*] [--enablerepo *REPOID*] [--disablerepo *REPOID*] [--repoid *REPOID*] [--releasever *RELEASEVER*] [--refresh] [--cachedir *CACHEDIR*] [--yes] [--quiet] *SUBCOMMAND*

See Section `Commands`_ for available subcommands.

Options
-------

.. option:: --help, -h

   Show help message and exit.

.. option:: --repo-files REPO_FILES

   Specify files containing DNF repository configuration. Can be
   used more than once. (default:
   ['/etc/qubes/repo-templates/qubes-templates.repo'])

.. option:: --keyring KEYRING

   Specify directory containing RPM public keys. (default:
   /etc/qubes/repo-templates/keys)

.. option:: --updatevm UPDATEVM

   Specify VM to download updates from. (Set to empty string to specify the
   current VM.) (default: same as UpdateVM - see ``qubes-prefs``)

.. option:: --enablerepo REPOID

   Enable additional repositories by an id or a glob. Can be used more than
   once.

.. option:: --disablerepo REPOID

   Disable certain repositories by an id or a glob. Can be used more than once.

.. option:: --repoid REPOID

   Enable just specific repositories by an id or a glob. Can be used more than
   once.

.. option:: --releasever RELEASEVER

   Override Qubes release version.

.. option:: --refresh

   Set repository metadata as expired before running the command.

.. option:: --cachedir CACHEDIR

   Specify cache directory. (default: ~/.cache/qvm-template)

.. option:: --yes

   Assume "yes" to questions.

.. option:: --quiet

   Decrease verbosity.

Commands
--------

install
^^^^^^^

| :command:`qvm-template install` [-h] [--pool *POOL*] [--nogpgcheck] [--allow-pv] [--downloaddir *DOWNLOADDIR*] [--retries *RETRIES*] [*TEMPLATESPEC* [*TEMPLATESPEC* ...]]

Install template packages.
See Section `Template Spec`_ for an explanation of *TEMPLATESPEC*.

.. option:: -h, --help

   Show help message and exit.

.. option:: --pool POOL

   Specify pool to store created VMs in.

.. option:: --nogpgcheck

   Disable signature checks.

.. option:: --allow-pv

   Allow templates that set virt_mode to pv.

.. option:: --downloaddir DOWNLOADDIR

   Specify download directory. (default: .)

.. option:: --retries RETRIES

   Specify maximum number of retries for downloads. (default: 5)

{reinstall,downgrade,upgrade}
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| :command:`qvm-template {reinstall,downgrade,upgrade}` [-h] [--nogpgcheck] [--allow-pv] [--downloaddir *DOWNLOADDIR*] [--retries *RETRIES*] [*TEMPLATESPEC* [*TEMPLATESPEC* ...]]

Reinstall/downgrade/upgrade template packages.

See Section `Template Spec`_ for an explanation of *TEMPLATESPEC*.

.. option:: -h, --help

   Show help message and exit.

.. option:: --nogpgcheck

   Disable signature checks.

.. option:: --allow-pv

   Allow templates that set virt_mode to pv.

.. option:: --downloaddir DOWNLOADDIR

   Specify download directory. (default: .)

.. option:: --retries RETRIES

   Specify maximum number of retries for downloads. (default: 5)

download
^^^^^^^^

| :command:`qvm-template download` [-h] [--downloaddir *DOWNLOADDIR*] [--retries *RETRIES*] [*TEMPLATESPEC* [*TEMPLATESPEC* ...]]

Download template packages.

See Section `Template Spec`_ for an explanation of *TEMPLATESPEC*.

.. option:: -h, --help

   Show help message and exit.

.. option:: --downloaddir DOWNLOADDIR

   Specify download directory. (default: .)

.. option:: --retries RETRIES

   Specify maximum number of retries for downloads. (default: 5)

list
^^^^

| :command:`qvm-template list` [-h] [--all] [--installed] [--available] [--extras] [--upgrades] [--machine-readable | --machine-readable-json] [*TEMPLATESPEC* [*TEMPLATESPEC* ...]]

List templates.

See Section `Template Spec`_ for an explanation of *TEMPLATESPEC*.

.. option:: -h, --help

   Show help message and exit.

.. option:: --all

   Show all templates (default).

.. option:: --installed

   Show installed templates.

.. option:: --available

   Show available templates.

.. option:: --extras

   Show extras (e.g., ones that exist locally but not in repos)
   templates.

.. option:: --upgrades

   Show available upgrades.

.. option:: --machine-readable

   Enable machine-readable output.

   Format
       Each line describes a template in the following format:

       ::

           {status}|{name}|{evr}|{reponame}

       Where ``{status}`` can be one of ``installed``, ``available``,
       ``extra``, or ``upgradable``.

       The field ``{evr}`` contains version information in the form of
       ``{epoch}:{version}-{release}``.

.. option:: --machine-readable-json

   Enable machine-readable output (JSON).

   Format
       The resulting JSON document is in the following format:

       ::

           {
               STATUS: [
                   {
                       "name": str,
                       "evr": str,
                       "reponame": str
                   },
                   ...
               ],
               ...
           }

       Where ``STATUS`` can be one of ``"installed"``, ``"available"``,
       ``"extra"``, or ``"upgradable"``.

       The fields ``buildtime`` and ``installtime`` are in ``%Y-%m-%d
       %H:%M:%S`` format in UTC.

       The field ``{evr}`` contains version information in the form of
       ``{epoch}:{version}-{release}``.

info
^^^^

| :command:`qvm-template list` [-h] [--all] [--installed] [--available] [--extras] [--upgrades] [--machine-readable | --machine-readable-json] [*TEMPLATESPEC* [*TEMPLATESPEC* ...]]

Display details about templates.

See Section `Template Spec`_ for an explanation of *TEMPLATESPEC*.

.. option:: -h, --help

   Show help message and exit.

.. option:: --all

   Show all templates (default).

.. option:: --installed

   Show installed templates.

.. option:: --available

   Show available templates.

.. option:: --extras

   Show extras (e.g., ones that exist locally but not in repos)
   templates.

.. option:: --upgrades

   Show available upgrades.

.. option:: --machine-readable

   Enable machine-readable output.

   Format
       Each line describes a template in the following format:

       ::

           {status}|{name}|{epoch}|{version}|{release}|{reponame}|{size}|{buildtime}|{installtime}|{license}|{url}|{summary}|{description}

       Where ``{status}`` can be one of ``installed``, ``available``,
       ``extra``, or ``upgradable``.

       The fields ``buildtime`` and ``installtime`` are in ``%Y-%m-%d
       %H:%M:%S`` format in UTC.

       Newlines in the ``{description}`` field are replaced with pipe
       characters (``|``) for easier processing.

.. option:: --machine-readable-json

   Enable machine-readable output (JSON).

   Format
       The resulting JSON document is in the following format:

       ::

           {
               STATUS: [
                   {
                       "name": str,
                       "epoch": str,
                       "version": str,
                       "release": str,
                       "reponame": str,
                       "size": int,
                       "buildtime": str,
                       "installtime": str,
                       "license": str,
                       "url": str,
                       "summary": str,
                       "description": str
                   },
                   ...
               ],
               ...
           }

       Where ``STATUS`` can be one of ``"installed"``, ``"available"``,
       ``"extra"``, or ``"upgradable"``.

       The fields ``buildtime`` and ``installtime`` are in ``%Y-%m-%d
       %H:%M:%S`` format in UTC.

search
^^^^^^

| :command:`qvm-template search` [-h] [--all] [*PATTERN* [*PATTERN* ...]]

Search template details for the given string.

.. option:: -h, --help

   Show help message and exit.

.. option:: --all

   Search also in the template description and URL. In addition, the criterion
   are evaluated with OR instead of AND.

remove
^^^^^^

| :command:`qvm-template remove` [-h] [--disassoc] [*TEMPLATE* [*TEMPLATE* ...]]

Remove installed templates.

.. option:: -h, --help

   Show help message and exit.

.. option:: --disassoc

   Also disassociate VMs from the templates to be removed. This
   creates a *dummy* template for the VMs to link with.

purge
^^^^^

| :command:`qvm-template purge` [-h] [*TEMPLATE* [*TEMPLATE* ...]]

Remove installed templates and associated VMs.

.. option:: -h, --help

   Show help message and exit.

clean
^^^^^

| :command:`qvm-template clean` [-h]

Remove locally cached packages.

.. option:: -h, --help

   Show help message and exit.

repolist
^^^^^^^^

| :command:`qvm-template repolist` [-h] [--all | --enabled | --disabled] [*REPOS* [*REPOS* ...]]

Show configured repositories.

.. option:: -h, --help

   Show help message and exit.

.. option:: --all

   Show all repos.

.. option:: --enabled

   Show only enabled repos (default).

.. option:: --disabled

   Show only disabled repos.

migrate-from-rpmdb
^^^^^^^^^^^^^^^^^^

| :command:`qvm-template migrate-from-rpmdb` [-h]

Migrate templates metadata from R4.0 format. This makes template originally
installed via rpm (qubes-dom0-update) available for qvm-template.
All templates gets `installed_by_rpm` property set to false.
If the operation fails for any reason, it is safe to retry.

.. option:: -h, --help

   Show help message and exit.

Template Spec
-------------

Subcommands such as ``install`` and ``download`` accept one or more
*TEMPLATESPEC* strings. The format is, in essence, almost identical to
``<package-name-spec>`` described in the DNF documentation.

In short, the spec is matched against the following list of NEVRA forms, in
decreasing orders of priority:

* ``name-[epoch:]version-release``
* ``name``
* ``name-[epoch:]version``

Note that unlike DNF, ``arch`` is currently ignored as the template packages
should all be of ``noarch``.

One can also use globs in spec strings. See Section `Globs`_ for details.

Refer to Section *NEVRA Matching* in the DNF documentation for details.

Globs
-----

`Template Spec`_ strings, repo ids, and search patterns support glob pattern
matching. In particular, the following special characters can be used:

* ``*``: Matches any number of characters.
* ``?``: Matches exactly one character.
* ``[]``: Matches any enclosed character.
* ``[!]``: Matches any character except those enclosed.

In particular, note that ``{}``, while supported by DNF, is not supported by
`qvm-template`.

Authors
-------

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git
