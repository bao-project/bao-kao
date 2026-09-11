/*
 * Copyright (c) Bao Project and Contributors. All rights reserved
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "kao.h"

unsigned int kao_tests_total;
unsigned int kao_tests_failed;
unsigned int kao_failures;

static void kao_run(const struct kao_test* test)
{
    if (cpu_is_master()) {
        if (KAO_LOG_LEVEL > 1) {
            printf("\n");
            INFO_TAG();
            printf("Running [%s] %s\n", test->id, test->name);
        }
        kao_tests_total++;
        kao_failures = 0;
    }

    test->fn();

    if (cpu_is_master()) {
        if (kao_failures) {
            kao_tests_failed++;
            if (KAO_LOG_LEVEL > 0) {
                FAIL_TAG();
                printf("[%s] %s\n", test->id, test->name);
            }
        } else if (KAO_LOG_LEVEL > 0) {
            SUCC_TAG();
            printf("[%s] %s\n", test->id, test->name);
        }
    }
}

void kao_entry(void)
{
    if (cpu_is_master()) {
        COMMAND_START();
    }

    for (unsigned int i = 0; i < kao_tests_num; i++) {
        kao_run(kao_tests[i]);
    }

    if (cpu_is_master()) {
        if (kao_tests_total > 0) {
            LOG_TESTS();
        } else {
            INFO_TAG();
            printf("No tests were executed!\n");
        }
        COMMAND_END();
    }
}
