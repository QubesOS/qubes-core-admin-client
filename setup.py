"""
Minimal setup.py shim for qubesadmin.

Most configuration is in pyproject.toml. This file handles:
- Custom install command for performance-optimized wrapper scripts
"""

import os
import setuptools
import setuptools.command.install
import sys


def get_console_scripts():
    """Generate list of (script_name, module_path) tuples for CLI tools."""
    for filename in os.listdir("./qubesadmin/tools"):
        basename, ext = os.path.splitext(os.path.basename(filename))
        if (
            basename in ["__init__", "dochelpers", "xcffibhelpers"]
            or ext != ".py"
        ):
            continue
        yield basename.replace("_", "-"), f"qubesadmin.tools.{basename}"


# create simple scripts that run much faster than "console entry points"
# TODO check if still relevant with modern  setuptools
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
                    f"""#!/usr/bin/python3
from {pkg} import main
import sys
if __name__ == '__main__':
    sys.exit(main())
"""
                )

            os.chmod(path, 0o755)
        setuptools.command.install.install.run(self)


if __name__ == "__main__":
    setuptools.setup(
        packages=setuptools.find_packages(),
        cmdclass={"install": CustomInstall},
    )
