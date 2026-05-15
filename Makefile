SHELL:=bash

# Define directories
root_dir:=$(realpath .)
kao_dir:=$(root_dir)/src

# Instantiate CI rules

include ci/ci.mk

python_srcs+=$(shell find $(kao_dir) -name "*.py")
$(call ci, pylint, $(python_srcs))

all_files:=$(python_srcs)
$(call ci, license, "Apache-2.0", $(all_files))

.PHONY: ci
ci: pylint license-check
