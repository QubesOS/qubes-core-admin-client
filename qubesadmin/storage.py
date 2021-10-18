# -*- encoding: utf-8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2017 Marek Marczykowski-Górecki
#                               <marmarek@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program; if not, see <http://www.gnu.org/licenses/>.

"""Storage subsystem."""
import qubesadmin.exc


class Volume(object):
    """Storage volume."""
    def __init__(self, app, pool=None, vid=None, vm=None, vm_name=None):
        """Construct a Volume object.

        Volume may be identified using pool+vid, or vm+vm_name. Either of
        those argument pairs must be given.

        :param Qubes app: application instance
        :param str pool: pool name
        :param str vid: volume id (within pool)
        :param str vm: owner VM name
        :param str vm_name: name within owning VM (like 'private', 'root' etc)
        """
        self.app = app
        if pool is None and vm is None:
            raise ValueError('Either pool or vm must be given')
        if pool is not None and vid is None:
            raise ValueError('If pool is given, vid must be too.')
        if vm is not None and vm_name is None:
            raise ValueError('If vm is given, vm_name must be too.')
        self._pool = pool
        self._vid = vid
        self._vm = vm
        self._vm_name = vm_name
        self._info = None

    def _qubesd_call(self, func_name, payload=None, payload_stream=None):
        """Make a call to qubesd regarding this volume

        :param str func_name: API function name, like `Info` or `Resize`
        :param bytes payload: Payload to send.
        :param file payload_stream: Stream to pipe payload from. Only one of
        `payload` and `payload_stream` can be used.
        """
        if self._vm is not None:
            method = 'admin.vm.volume.' + func_name
            dest = self._vm
            arg = self._vm_name
        else:
            if payload_stream:
                raise NotImplementedError(
                    'payload_stream not implemented for '
                    'admin.pool.volume.* calls')
            method = 'admin.pool.volume.' + func_name
            dest = 'dom0'
            arg = self._pool
            if payload is not None:
                payload = self._vid.encode('ascii') + b' ' + payload
            else:
                payload = self._vid.encode('ascii')
        return self.app.qubesd_call(
            dest, method, arg, payload=payload,
            payload_stream=payload_stream)

    def _fetch_info(self, force=True):
        """Fetch volume properties

        Populate self._info dict

        :param bool force: refresh self._info, even if already populated.
        """
        if not force and self._info is not None:
            return
        info = self._qubesd_call('Info')
        info = info.decode('ascii')
        self._info = dict([line.split('=', 1) for line in info.splitlines()])

    def __eq__(self, other):
        if isinstance(other, Volume):
            return self.pool == other.pool and self.vid == other.vid
        return NotImplemented

    def __lt__(self, other):
        # pylint: disable=protected-access
        if isinstance(other, Volume):
            if self._vm and other._vm:
                return (self._vm, self._vm_name) < (other._vm, other._vm_name)
            if self._vid and other._vid:
                return (self._pool, self._vid) < (other._pool, other._vid)
        return NotImplemented

    @property
    def name(self):
        """per-VM volume name, if available"""
        return self._vm_name

    @property
    def pool(self):
        """Storage volume pool name."""
        if self._pool is not None:
            return self._pool
        try:
            self._fetch_info()
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('pool')
        return str(self._info['pool'])

    @property
    def vid(self):
        """Storage volume id, unique within given pool."""
        if self._vid is not None:
            return self._vid
        try:
            self._fetch_info()
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('vid')
        return str(self._info['vid'])

    @property
    def size(self):
        """Size of volume, in bytes."""
        try:
            self._fetch_info()
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('size')
        return int(self._info['size'])

    @property
    def usage(self):
        """Used volume space, in bytes."""
        try:
            self._fetch_info()
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('usage')
        return int(self._info['usage'])

    @property
    def rw(self):
        """True if volume is read-write."""
        try:
            self._fetch_info()
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('rw')
        return self._info['rw'] == 'True'

    @rw.setter
    def rw(self, value):
        """Set rw property"""
        self._qubesd_call('Set.rw', str(value).encode('ascii'))
        self._info = None

    @property
    def ephemeral(self):
        """True if volume is read-write."""
        try:
            self._fetch_info()
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('ephemeral')
        return self._info.get('ephemeral', 'False') == 'True'

    @ephemeral.setter
    def ephemeral(self, value):
        """Set rw property"""
        self._qubesd_call('Set.ephemeral', str(value).encode('ascii'))
        self._info = None

    @property
    def snap_on_start(self):
        """Create a snapshot from source on VM start."""
        try:
            self._fetch_info()
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('snap_on_start')
        return self._info['snap_on_start'] == 'True'

    @property
    def save_on_stop(self):
        """Commit changes to original volume on VM stop."""
        try:
            self._fetch_info()
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('save_on_stop')
        return self._info['save_on_stop'] == 'True'

    @property
    def source(self):
        """Volume ID of source volume (for :py:attr:`snap_on_start`).

        If None, this volume itself will be used.
        """
        try:
            self._fetch_info()
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('source')
        if self._info['source']:
            return self._info['source']
        return None

    @property
    def revisions_to_keep(self):
        """Number of revisions to keep around"""
        try:
            self._fetch_info()
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('revisions_to_keep')
        return int(self._info['revisions_to_keep'])

    @revisions_to_keep.setter
    def revisions_to_keep(self, value):
        """Set revisions_to_keep property"""
        self._qubesd_call('Set.revisions_to_keep', str(value).encode('ascii'))
        self._info = None

    def is_outdated(self):
        """Returns `True` if this snapshot of a source volume (for
        `snap_on_start`=True) is outdated.
        """
        try:
            self._fetch_info()
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('is_outdated')
        return self._info.get('is_outdated', False) == 'True'

    def resize(self, size):
        """Resize volume.

        Currently only extending is supported.

        :param int size: new size in bytes.
        """
        self._qubesd_call('Resize', str(size).encode('ascii'))

    @property
    def revisions(self):
        """ Returns iterable containing revision identifiers"""
        revisions = self._qubesd_call('ListSnapshots')
        return revisions.decode('ascii').splitlines()

    def revert(self, revision):
        """ Revert volume to previous revision

        :param str revision: Revision identifier to revert to
        """
        if not isinstance(revision, str):
            raise TypeError('revision must be a str')
        self._qubesd_call('Revert', revision.encode('ascii'))

    def import_data(self, stream):
        """ Import volume data from a given file-like object.

        This function overrides existing volume content.

        :param stream: file-like object, must support fileno()
        """
        self._qubesd_call('Import', payload_stream=stream)

    def import_data_with_size(self, stream, size):
        """ Import volume data from a given file-like object, informing qubesd
        that data has a specific size.

        This function overrides existing volume content.

        :param stream: file-like object, must support fileno()
        :param size: size of data in bytes
        """
        size_line = str(size) + '\n'
        self._qubesd_call(
            'ImportWithSize', payload=size_line.encode(),
            payload_stream=stream)

    def clear_data(self):
        """ Clear existing volume content. """
        self._qubesd_call('Clear')

    def clone(self, source):
        """ Clone data from sane volume of another VM.

        This function override existing volume content.
        This operation is implemented for VM volumes - those in vm.volumes
        collection (not pool.volumes).

        :param source: source volume object
        """

        # pylint: disable=protected-access

        # get a token from source volume
        token = source._qubesd_call('CloneFrom')
        # and use it to actually clone volume data
        self._qubesd_call('CloneTo', payload=token)


class Pool(object):
    """ A Pool is used to manage different kind of volumes (File
        based/LVM/Btrfs/...).
    """
    def __init__(self, app, name=None):
        """ Initialize storage pool wrapper

        :param app: Qubes() object
        :param name: name of the pool
        """
        self.app = app
        self.name = name
        self._config = None

    def __str__(self):
        return self.name

    def __eq__(self, other):
        if isinstance(other, Pool):
            return self.name == other.name
        if isinstance(other, str):
            return self.name == other
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, Pool):
            return self.name < other.name
        return NotImplemented

    @property
    def usage_details(self):
        """ Storage pool usage details (current - not cached) """
        try:
            pool_usage_data = self.app.qubesd_call(
                'dom0', 'admin.pool.UsageDetails', self.name, None)
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('usage_details')
        pool_usage_data = pool_usage_data.decode('utf-8')
        assert pool_usage_data.endswith('\n') or pool_usage_data == ''
        pool_usage_data = pool_usage_data[:-1]

        def _int_split(text):  # pylint: disable=missing-docstring
            key, value = text.split("=", 1)
            return key, int(value)

        return dict(_int_split(l) for l in pool_usage_data.splitlines())

    @property
    def config(self):
        """ Storage pool config """
        if self._config is None:
            try:
                pool_info_data = self.app.qubesd_call(
                    'dom0', 'admin.pool.Info', self.name, None)
            except qubesadmin.exc.QubesDaemonAccessError:
                raise qubesadmin.exc.QubesPropertyAccessError('config')
            pool_info_data = pool_info_data.decode('utf-8')
            assert pool_info_data.endswith('\n')
            pool_info_data = pool_info_data[:-1]
            self._config = dict(
                l.split('=', 1) for l in pool_info_data.splitlines())
        return self._config

    @property
    def size(self):
        """ Storage pool size, in bytes"""
        try:
            return int(self.usage_details['data_size'])
        except KeyError:
            # pool driver does not provide size information
            return None

    @property
    def usage(self):
        """ Space used in the pool, in bytes """
        try:
            return int(self.usage_details['data_usage'])
        except KeyError:
            # pool driver does not provide usage information
            return None

    @property
    def driver(self):
        """ Storage pool driver """
        return self.config['driver']

    @property
    def revisions_to_keep(self):
        """Number of revisions to keep around"""
        return int(self.config['revisions_to_keep'])

    @revisions_to_keep.setter
    def revisions_to_keep(self, value):
        """Set revisions_to_keep property"""
        self.app.qubesd_call(
            'dom0',
            'admin.pool.Set.revisions_to_keep',
            self.name,
            str(value).encode('ascii'))
        self._config = None

    @property
    def volumes(self):
        """ Volumes managed by this pool """
        try:
            volumes_data = self.app.qubesd_call(
                'dom0', 'admin.pool.volume.List', self.name, None)
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('volumes')
        assert volumes_data.endswith(b'\n')
        volumes_data = volumes_data[:-1].decode('ascii')
        for vid in volumes_data.splitlines():
            yield Volume(self.app, self.name, vid)
