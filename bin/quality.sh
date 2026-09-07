#!/usr/bin/env bash

set -eu

main() {
    ruff check .
    ruff format --check .
    ty check
    pytest
}

main "$@"