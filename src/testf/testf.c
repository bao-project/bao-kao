/*
 * Copyright (c) Bao Project and Contributors. All rights reserved
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "testf.h"

unsigned int testf_tests_total;
unsigned int testf_tests_failed;
unsigned int testf_failures;

static void testf_run(const struct testf_test* test)
{
    if (cpu_is_master()) {
        if (TESTF_LOG_LEVEL > 1) {
            printf("\n");
            INFO_TAG();
            printf("Running [%s] %s\n", test->id, test->name);
        }
        testf_tests_total++;
        testf_failures = 0;
    }

    test->fn();

    if (cpu_is_master()) {
        if (testf_failures) {
            testf_tests_failed++;
            if (TESTF_LOG_LEVEL > 1) {
                FAIL_TAG();
                printf("[%s] %s failed!\n", test->id, test->name);
            }
        } else if (TESTF_LOG_LEVEL > 1) {
            SUCC_TAG();
            printf("[%s] %s passed!\n", test->id, test->name);
        }
    }
}

void testf_entry(void)
{
    if (cpu_is_master()) {
        COMMAND_START();
    }

    for (unsigned int i = 0; i < testf_tests_num; i++) {
        testf_run(testf_tests[i]);
    }

    if (cpu_is_master()) {
        if (testf_tests_total > 0) {
            LOG_TESTS();
        } else {
            INFO_TAG();
            printf("No tests were executed!\n");
        }
        COMMAND_END();
    }
}
