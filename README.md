This is client side implementation of Qubes Admin API. See
https://www.qubes-os.org/doc/admin-api/ for protocol specification.



Compatibility
=============

Most of the API modules are compatible with Python >= 2.7.
Very few parts require Python >= 3.5:
 - tools (`qvm-*`)
 - qubesadmin.events module (for asyncio module)

Parts not compatible with Python < 3.5, are not installed in such environment.
