# vim: fileencoding=utf-8

import os
import setuptools
import setuptools.command.install
import sys

exclude=[]
if sys.version_info[0:2] < (3, 5):
    exclude += ['qubesadmin.backup', 'qubesadmin.tests.backup']
    exclude += ['qubesadmin.tools', 'qubesadmin.tests.tools']
    exclude += ['qubesadmin.events']

# don't import: import * is unreliable and there is no need, since this is
# compile time and we have source files
def get_console_scripts():
    if sys.version_info[0:2] >= (3, 4):
        for filename in os.listdir('./qubesadmin/tools'):
            basename, ext = os.path.splitext(os.path.basename(filename))
            if basename in ['__init__', 'dochelpers', 'xcffibhelpers']\
                    or ext != '.py':
                continue
            yield basename.replace('_', '-'), 'qubesadmin.tools.{}'.format(
                basename)

# create simple scripts that run much faster than "console entry points"
class CustomInstall(setuptools.command.install.install):
    def run(self):
        bin = os.path.join(self.root, "usr/bin")
        try:
            os.makedirs(bin)
        except:
            pass
        for file, pkg in get_console_scripts():
           path = os.path.join(bin, file)
           with open(path, "w") as f:
               f.write(
"""#!/usr/bin/python3
from {} import main
import sys
if __name__ == '__main__':
	sys.exit(main())
""".format(pkg))

           os.chmod(path, 0o755)
        setuptools.command.install.install.run(self)

if __name__ == '__main__':
    setuptools.setup(
        name='qubesadmin',
        version=open('version').read().strip(),
        author='Invisible Things Lab',
        author_email='marmarek@invisiblethingslab.com',
        description='Qubes Admin API package',
        license='LGPL2.1+',
        url='https://www.qubes-os.org/',
        packages=setuptools.find_packages(exclude=exclude),
        package_data={
            'qubesadmin.tests.backup': ['*.xml'],
        },
        cmdclass={
           'install': CustomInstall
        },

        )
