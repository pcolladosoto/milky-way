# Copyright (c) 2021 Sine Nomine Associates

.PHONY: help build install publish clean distclean

NAMESPACE := $(strip $(subst namespace:,,$(shell grep namespace: galaxy.yml)))
NAME := $(strip $(subst name:,,$(shell grep name: galaxy.yml)))
VERSION := $(strip $(subst version:,,$(shell grep version: galaxy.yml)))
PYTHON := /usr/local/bin/python3
UPDATE := --force
AG_TOKEN := $(shell cat .galaxy-token)

help:
	@echo "usage: make <target>"
	@echo "targets:"
	@echo "  venv        install a virtualenv"
	@echo "  build       build the collection"
	@echo "  install     install the collection"
	@echo "  publish     upload the collection to Ansible Galaxy"
	@echo "  clean       remove generated files"
	@echo "  distclean   remove generated files and virtualenv"

.venv/bin/activate:
	test -d .venv || $(PYTHON) -m venv .venv
	.venv/bin/pip install -U pip
	.venv/bin/pip install wheel
	.venv/bin/pip install -r requirements.txt
	touch .venv/bin/activate

venv: .venv/bin/activate

build:
	@mkdir -p builds
	@ansible-galaxy collection build --output-path builds $(UPDATE) .

install: build
	ansible-galaxy collection install $(UPDATE) builds/$(NAMESPACE)-$(NAME)-$(VERSION).tar.gz

publish: build
	ansible-galaxy collection publish \
		builds/$(NAMESPACE)-$(NAME)-$(VERSION).tar.gz --token $(AG_TOKEN)

clean:
	rm -rf builds

distclean: clean
	rm -rf .venv