#  Copyright (c) Bao Project and Contributors. All rights reserved  
#  SPDX-License-Identifier: Apache-2.0

ifndef TESTF_TESTS_DIR
$(error User must define the variable(s) TESTF_TESTS_DIR with the path to the \
directory containing the test sources)
#TODO: add a default value?
endif

ifndef TESTF_REPO_DIR
$(error User must define the variable(s) TESTF_REPO_DIR with the path to the \
directory containing the test framework repository)
#TODO: add a default value?
endif

ifdef BAO_TEST

TESTF_SRC_DIR:=$(TESTF_REPO_DIR)/src
TESTF_INC_DIR:=$(TESTF_SRC_DIR)/inc

TESTF_SRCS += $(TESTF_SRC_DIR)/testf_entry.c 
TESTF_SRCS += $(wildcard $(TESTF_TESTS_DIR)/*.c)

ifndef SUITES
ifndef TESTS
$(error User must define the variable(s) SUITES and/or TESTS)
endif
endif

ifdef SUITES
TESTF_FLAGS+=$(addprefix -D, $(SUITES))
endif

ifdef TESTS
TESTF_FLAGS+=$(addprefix -D, $(TESTS))
endif 

ifdef TESTF_LOG_LEVEL
TESTF_FLAGS+=-DTESTF_LOG_LEVEL=$(TESTF_LOG_LEVEL)
endif

ifdef TESTF_NO_RTE
TESTF_FLAGS+=-Dno_rte
endif

else
TESTF_SRCS += $(TESTF_SRC_DIR)/testf_weak.c 

endif
