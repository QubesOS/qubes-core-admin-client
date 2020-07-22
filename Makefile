.PHONY: all
all: build

PYTHON ?= python3

.PHONY: build
build:
	$(PYTHON) setup.py build

.PHONY: install
install:
	$(PYTHON) setup.py install -O1 $(PYTHON_PREFIX_ARG) --root $(DESTDIR)
	install -d $(DESTDIR)/etc/xdg/autostart
	install -m 0644 etc/qvm-start-daemon.desktop $(DESTDIR)/etc/xdg/autostart/
	install -m 0644 etc/qvm-start-daemon-kde.desktop $(DESTDIR)/etc/xdg/autostart/
	install -d $(DESTDIR)/usr/share/xsessions/
	install -m 0644 xsessions/sys-gui.desktop $(DESTDIR)/usr/share/xsessions/
	install -d $(DESTDIR)/usr/bin
	ln -sf qvm-start-daemon $(DESTDIR)/usr/bin/qvm-start-gui
	install -m 0755 scripts/qubes-gui-session $(DESTDIR)/usr/bin/

clean:
	rm -rf test-packages/__pycache__ qubesadmin/__pycache__
	rm -rf qubesadmin/*/__pycache__ qubesadmin/tests/*/__pycache__
	rm -rf test-packages/*.egg-info
	rm -f .coverage
	rm -rf debian/changelog.*
	rm -rf pkgs
