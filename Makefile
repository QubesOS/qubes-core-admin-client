.PHONY: all
all: build

PYTHON ?= python3
PIP ?= pip3

.PHONY: build
build:
    # --no-isolation to use distro packages instead of downloading missing ones
	$(PYTHON) -m build --no-isolation

.PHONY: install-misc
install-misc:
	install -d $(DESTDIR)/etc/xdg/autostart
	install -m 0644 etc/qvm-start-daemon.desktop $(DESTDIR)/etc/xdg/autostart/
	install -m 0644 etc/qvm-start-daemon-kde.desktop $(DESTDIR)/etc/xdg/autostart/
	install -d $(DESTDIR)/usr/bin
	ln -sf qvm-start-daemon $(DESTDIR)/usr/bin/qvm-start-gui
	for i in block usb pci; do ln -sf qvm-device $(DESTDIR)/usr/bin/"qvm-$$i"; done
	install -m 0755 scripts/qubes-guivm-session $(DESTDIR)/usr/bin/
	install -d $(DESTDIR)/etc/qubes/post-install.d
	install -m 0755 scripts/30-keyboard-layout-service.sh \
		$(DESTDIR)/etc/qubes/post-install.d/30-keyboard-layout-service.sh
	install -D scripts/qvm-console $(DESTDIR)/usr/bin/qvm-console

.PHONY: install-pip
install-pip:
	# /!\ will download deps from the internet if not present
	$(PIP) install .

.PHONY: install-editable
install-editable:
	# /!\ will download deps from the internet if not present
	$(PIP) install -e .

clean:
	rm -rf build/ dist/ .eggs/ pkgs/ .coverage
	rm -rf debian/changelog.*
	find . -type f -name *.pyc -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "__pycache__" -exec rm -rf {} +
