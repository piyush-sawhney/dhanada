.PHONY: help install install-dev test lint format format-check typecheck security migrate upgrade-db downgrade-db run generate-kek clean ci

help:
	cd backend && make help

install install-dev test lint format format-check typecheck security migrate upgrade-db downgrade-db run generate-kek clean ci:
	cd backend && make $@