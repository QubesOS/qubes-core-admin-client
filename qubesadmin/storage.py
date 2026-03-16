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
from __future__ import annotations
from typing import BinaryIO, TYPE_CHECKING, IO
from collections.abc import Generator

import qubesadmin.exc
if TYPE_CHECKING:
    from qubesadmin.app import QubesBase


class Volume:
    """Storage volume."""
    def __init__(self, app: QubesBase, pool: str | None=None,
                 vid: str | None=None, vm: str | None=None,
                 vm_name: str | None=None):
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

    def _qubesd_call(self, func_name: str, payload: bytes | None = None,
                     payload_stream: IO | None = None) -> bytes:
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
            assert self._vid is not None
            if payload is not None:
                payload = self._vid.encode('ascii') + b' ' + payload
            else:
                payload = self._vid.encode('ascii')
        return self.app.qubesd_call(
            dest, method, arg, payload=payload,
            payload_stream=payload_stream)

    def _fetch_info(self, force: bool = True) -> None:
        """Fetch volume properties

        Populate self._info dict

        :param bool force: refresh self._info, even if already populated.
        """
        if not force and self._info is not None:
            return
        info = self._qubesd_call('Info')
        info = info.decode('ascii')
        self._info = dict([line.split('=', 1) for line in info.splitlines()])

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Volume):
            return self.pool == other.pool and self.vid == other.vid
        return NotImplemented

    def __lt__(self, other: object) -> bool:
        # pylint: disable=protected-access
        if isinstance(other, Volume):
            if self._vm and other._vm:
                assert self._vm_name is not None and other._vm_name is not None
                return (self._vm, self._vm_name) < (other._vm, other._vm_name)
            if self._vid and other._vid:
                assert self._pool is not None and other._pool is not None
                return (self._pool, self._vid) < (other._pool, other._vid)
        return NotImplemented

    @property
    def name(self) -> str | None:
        """per-VM volume name, if available"""
        return self._vm_name

    @property
    def pool(self) -> str:
        """Storage volume pool name."""
        if self._pool is not None:
            return self._pool
        try:
            self._fetch_info()
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('pool')
        assert self._info is not None
        return str(self._info['pool'])

    @property
    def vid(self) -> str:
        """Storage volume id, unique within given pool."""
        if self._vid is not None:
            return self._vid
        try:
            self._fetch_info()
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('vid')
        assert self._info is not None
        return str(self._info['vid'])

    @property
    def size(self) -> int:
        """Size of volume, in bytes."""
        try:
            self._fetch_info()
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('size')
        assert self._info is not None
        return int(self._info['size'])

    @property
    def usage(self) -> int:
        """Used volume space, in bytes."""
        try:
            self._fetch_info()
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('usage')
        assert self._info is not None
        return int(self._info['usage'])

    @property
    def rw(self) -> bool:
        """True if volume is read-write."""
        try:
            self._fetch_info()
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('rw')
        assert self._info is not None
        return self._info['rw'] == 'True'

    @rw.setter
    def rw(self, value: object) -> None:
        """Set rw property"""
        self._qubesd_call('Set.rw', str(value).encode('ascii'))
        self._info = None

    @property
    def ephemeral(self) -> bool:
        """True if volume is read-write."""
        try:
            self._fetch_info()
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('ephemeral')
        assert self._info is not None
        return self._info.get('ephemeral', 'False') == 'True'

    @ephemeral.setter
    def ephemeral(self, value: object) -> None:
        """Set rw property"""
        self._qubesd_call('Set.ephemeral', str(value).encode('ascii'))
        self._info = None

    @property
    def snap_on_start(self) -> bool:
        """Create a snapshot from source on VM start."""
        try:
            self._fetch_info()
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('snap_on_start')
        assert self._info is not None
        return self._info['snap_on_start'] == 'True'

    @property
    def save_on_stop(self) -> bool:
        """Commit changes to original volume on VM stop."""
        try:
            self._fetch_info()
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('save_on_stop')
        assert self._info is not None
        return self._info['save_on_stop'] == 'True'

    @property
    def source(self) -> str | None:
        """Volume ID of source volume (for :py:attr:`snap_on_start`).

        If None, this volume itself will be used.
        """
        try:
            self._fetch_info()
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('source')
        assert self._info is not None
        if self._info['source']:
            return self._info['source']
        return None

    @property
    def revisions_to_keep(self) -> int:
        """Number of revisions to keep around"""
        try:
            self._fetch_info()
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('revisions_to_keep')
        assert self._info is not None
        return int(self._info['revisions_to_keep'])

    @revisions_to_keep.setter
    def revisions_to_keep(self, value: object) -> None:
        """Set revisions_to_keep property"""
        self._qubesd_call('Set.revisions_to_keep', str(value).encode('ascii'))
        self._info = None

    def is_outdated(self) -> bool:
        """Returns `True` if this snapshot of a source volume (for
        `snap_on_start`=True) is outdated.
        """
        try:
            self._fetch_info()
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('is_outdated')
        assert self._info is not None
        return self._info.get('is_outdated', False) == 'True'

    def resize(self, size: object) -> None:
        """Resize volume.

        Currently only extending is supported.

        :param int size: new size in bytes.
        """
        self._qubesd_call('Resize', str(size).encode('ascii'))

    @property
    def revisions(self) -> list[str]:
        """ Returns iterable containing revision identifiers"""
        revisions = self._qubesd_call('ListSnapshots')
        return revisions.decode('ascii').splitlines()

    def revert(self, revision: str) -> None:
        """ Revert volume to previous revision

        :param str revision: Revision identifier to revert to
        """
        if not isinstance(revision, str):
            raise TypeError('revision must be a str')
        self._qubesd_call('Revert', revision.encode('ascii'))

    def import_data(self, stream: BinaryIO) -> None:
        """ Import volume data from a given file-like object.

        This function overrides existing volume content.

        :param stream: file-like object, must support fileno()
        """
        self._qubesd_call('Import', payload_stream=stream)

    def import_data_with_size(self, stream: IO, size: object) -> None:
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

    def clear_data(self) -> None:
        """ Clear existing volume content. """
        self._qubesd_call('Clear')

    def clone(self, source: Volume) -> None:
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


class Pool:
    """ A Pool is used to manage different kind of volumes (File
        based/LVM/Btrfs/...).
    """
    def __init__(self, app: QubesBase, name: str | None=None):
        """ Initialize storage pool wrapper

        :param app: Qubes() object
        :param name: name of the pool
        """
        self.app = app
        self.name = name
        self._config = None

    def __str__(self) -> str:
        assert self.name is not None
        return self.name

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Pool):
            return self.name == other.name
        if isinstance(other, str):
            return self.name == other
        return NotImplemented

    def __lt__(self, other: object) -> bool:
        if isinstance(other, Pool):
            assert self.name is not None and other.name is not None
            return self.name < other.name
        return NotImplemented

    @property
    def usage_details(self) -> dict[str, int]:
        """ Storage pool usage details (current - not cached) """
        try:
            pool_usage_data = self.app.qubesd_call(
                'dom0', 'admin.pool.UsageDetails', self.name, None)
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('usage_details')
        pool_usage_data = pool_usage_data.decode('utf-8')
        assert pool_usage_data.endswith('\n') or pool_usage_data == ''
        pool_usage_data = pool_usage_data[:-1]

        def _int_split(text: str) -> tuple[str, int]:  # pylint: disable=missing-docstring
            key, value = text.split("=", 1)
            return key, int(value)

        return dict(_int_split(l) for l in pool_usage_data.splitlines())

    @property
    def config(self) -> dict[str, str]:
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
    def size(self) -> int | None:
        """ Storage pool size, in bytes"""
        try:
            return int(self.usage_details['data_size'])
        except KeyError:
            # pool driver does not provide size information
            return None

    @property
    def usage(self) -> int | None:
        """ Space used in the pool, in bytes """
        try:
            return int(self.usage_details['data_usage'])
        except KeyError:
            # pool driver does not provide usage information
            return None

    @property
    def driver(self) -> str:
        """ Storage pool driver """
        return self.config['driver']

    @property
    def revisions_to_keep(self) -> int:
        """Number of revisions to keep around"""
        return int(self.config['revisions_to_keep'])

    @revisions_to_keep.setter
    def revisions_to_keep(self, value: object) -> None:
        """Set revisions_to_keep property"""
        self.app.qubesd_call(
            'dom0',
            'admin.pool.Set.revisions_to_keep',
            self.name,
            str(value).encode('ascii'))
        self._config = None

    @property
    def ephemeral_volatile(self) -> bool:
        """Whether volatile volumes in this pool should be encrypted with an
           ephemeral key in dom0"""
        return bool(self.config['ephemeral_volatile'])

    @ephemeral_volatile.setter
    def ephemeral_volatile(self, value: object) -> None:
        """Set ephemeral_volatile property"""
        self.app.qubesd_call(
            'dom0',
            'admin.pool.Set.ephemeral_volatile',
            self.name,
            str(value).encode('ascii'))
        self._config = None

    @property
    def volumes(self) -> Generator[Volume]:
        """ Volumes managed by this pool """
        try:
            volumes_data = self.app.qubesd_call(
                'dom0', 'admin.pool.volume.List', self.name, None)
        except qubesadmin.exc.QubesDaemonAccessError:
            raise qubesadmin.exc.QubesPropertyAccessError('volumes')
        if volumes_data == b'':
            return
        assert volumes_data.endswith(b'\n')
        volumes_data = volumes_data[:-1].decode('ascii')
        for vid in volumes_data.splitlines():
            yield Volume(self.app, self.name, vid)
