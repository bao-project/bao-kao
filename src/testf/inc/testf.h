/*
 * Copyright (c) Bao Project and Contributors. All rights reserved
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef TESTF_H
#define TESTF_H

#include "testf_commands.h"
#include <stdio.h>

#ifndef TESTF_LOG_LEVEL
#define TESTF_LOG_LEVEL 2
#endif

#if defined(no_rte) || defined(__clang_analyzer__) || defined(__CPPCHECK__)
#include <stdbool.h>
static inline bool cpu_is_master(void)
{
    return true;
}
#else
#include <cpu.h>
#endif

struct testf_test {
    const char* id;
    const char* name;
    void (*fn)(void);
    const char* tags;
    const char* envs;
    const char* description;
};

extern unsigned int testf_tests_total;
extern unsigned int testf_tests_failed;
extern unsigned int testf_failures;

extern const struct testf_test* const testf_tests[];
extern const unsigned int testf_tests_num;

#define TAGS(...) #__VA_ARGS__
#define ENVS(...) #__VA_ARGS__

/*
 * Discovery builds only run the preprocessor: every registration becomes one marker
 * line that kao reads back to learn the tests in the sources it was given.
 *
 * Real builds compile a single generated file that includes the selected sources
 * and ends with the table of selected descriptors. Descriptors and test functions
 * are static, so whatever the table does not reference is dropped by the compiler.
 * The redeclaration rejects non-static test functions and wrong signatures.
 */
#ifdef TESTF_DISCOVERY
#define BAO_TEST(id, fn, tags, envs, desc) \
    @BAO_TEST@ id @ fn @ tags @ envs @ desc @ __FILE__ @ __LINE__ @
/* Optional, once per file: tags every test registered in this file carries. */
#define FILE_TAGS(...) @BAO_FILE_TAGS@ #__VA_ARGS__ @ __FILE__ @
#else
#define BAO_TEST(id, fn, tags, envs, desc)                                  \
    static void fn(void);                                                   \
    static const struct testf_test __attribute__((unused)) testf_test_##id = \
        { #id, #fn, fn, tags, envs, desc }
#define FILE_TAGS(...) extern const int testf_file_tags_declared
#endif

#define RED()         printf("\033[1;31m")
#define GREEN()       printf("\033[1;32m")
#define YELLOW()      printf("\033[1;33m")
#define COLOR_RESET() printf("\033[0m")

#define INFO_TAG()     \
    YELLOW();          \
    printf("[INFO] "); \
    COLOR_RESET();

#define FAIL_TAG()        \
    RED();                \
    printf("[FAILURE] "); \
    COLOR_RESET();

#define SUCC_TAG()        \
    GREEN();              \
    printf("[SUCCESS] "); \
    COLOR_RESET();

#if (TESTF_LOG_LEVEL > 0)
#define LOG_FAILURE()                                                 \
    do {                                                              \
        FAIL_TAG();                                                   \
        printf("\n    File: %s\n    Line: %u\n", __FILE__, __LINE__); \
    } while (0)
#else
#define LOG_FAILURE()
#endif

#define TESTF_RECORD_FAILURE() \
    do {                       \
        if (cpu_is_master()) { \
            testf_failures++;  \
        }                      \
    } while (0)

#define LOG_NOT_SUCCESS()                                                      \
    do {                                                                       \
        FAIL_TAG();                                                            \
        printf("Total:%u Passed:%u Failed:%u\n", testf_tests_total,            \
            testf_tests_total - testf_tests_failed, testf_tests_failed);       \
    } while (0)

#define LOG_SUCCESS()                                                          \
    do {                                                                       \
        SUCC_TAG();                                                            \
        printf("Total:%u Passed:%u Failed:%u\n", testf_tests_total,            \
            testf_tests_total - testf_tests_failed, testf_tests_failed);       \
    } while (0)

#define LOG_TESTS()                                                                \
    do {                                                                           \
        if (TESTF_LOG_LEVEL > 1) {                                                 \
            printf("\n");                                                          \
            INFO_TAG();                                                            \
            printf("Final Report\n");                                              \
            if (testf_tests_failed)                                                \
                LOG_NOT_SUCCESS();                                                 \
            else                                                                   \
                LOG_SUCCESS();                                                     \
        }                                                                          \
        printf("[TESTF-C] TOTAL#%u SUCCESS#%u FAIL#%u\n\n", testf_tests_total,     \
            testf_tests_total - testf_tests_failed, testf_tests_failed);           \
    } while (0)

#include "testf_assert.h"

void testf_entry(void);

#endif // TESTF_H
