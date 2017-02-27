.PHONY: all
all: build

PYTHON ?= python

.PHONY: build
build:
	$(PYTHON) setup.py build

.PHONY: install
install:
	$(PYTHON) setup.py install -O1 --skip-build $(PYTHON_PREFIX_ARG) --root $(DESTDIR)
