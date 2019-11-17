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
	install -d $(DESTDIR)/usr/bin
	ln -sf /usr/bin/qubes-start-daemon $(DESTDIR)/usr/bin/qubes-start-gui

clean:
	rm -rf test-packages/__pycache__ qubesadmin/__pycache__
	rm -rf qubesadmin/*/__pycache__ qubesadmin/tests/*/__pycache__
	rm -rf test-packages/*.egg-info
	rm -f .coverage
