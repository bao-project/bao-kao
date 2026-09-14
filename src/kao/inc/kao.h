/*
 * Copyright (c) Bao Project and Contributors. All rights reserved
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef KAO_H
#define KAO_H

#include "kao_commands.h"
#include <stdio.h>

#ifndef KAO_LOG_LEVEL
#define KAO_LOG_LEVEL 2
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

struct kao_test {
    const char* id;
    const char* name;
    void (*fn)(void);
    const char* tags;
    const char* envs;
    const char* description;
};

extern unsigned int kao_tests_total;
extern unsigned int kao_tests_failed;
extern unsigned int kao_failures;

extern const struct kao_test* const kao_tests[];
extern const unsigned int kao_tests_num;

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
#ifdef KAO_DISCOVERY
#define KAO_TEST(id, fn, tags, envs, desc) \
    @KAO_TEST@ id @ fn @ tags @ envs @ desc @ __FILE__ @ __LINE__ @
/* Optional, once per file: tags every test registered in this file carries. */
#define FILE_TAGS(...) @KAO_FILE_TAGS@ #__VA_ARGS__ @ __FILE__ @
#else
#define KAO_TEST(id, fn, tags, envs, desc)                                  \
    static void fn(void);                                                   \
    static const struct kao_test __attribute__((unused)) kao_test_##id = \
        { #id, #fn, fn, tags, envs, desc }
#define FILE_TAGS(...) extern const int kao_file_tags_declared
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

#if (KAO_LOG_LEVEL > 0)
#define LOG_FAILURE()                                                 \
    do {                                                              \
        FAIL_TAG();                                                   \
        printf("\n    File: %s\n    Line: %u\n", __FILE__, __LINE__); \
    } while (0)
#else
#define LOG_FAILURE()
#endif

#define KAO_RECORD_FAILURE() \
    do {                       \
        if (cpu_is_master()) { \
            kao_failures++;  \
        }                      \
    } while (0)

#define LOG_NOT_SUCCESS()                                                      \
    do {                                                                       \
        FAIL_TAG();                                                            \
        printf("Total:%u Passed:%u Failed:%u\n", kao_tests_total,            \
            kao_tests_total - kao_tests_failed, kao_tests_failed);       \
    } while (0)

#define LOG_SUCCESS()                                                          \
    do {                                                                       \
        SUCC_TAG();                                                            \
        printf("Total:%u Passed:%u Failed:%u\n", kao_tests_total,            \
            kao_tests_total - kao_tests_failed, kao_tests_failed);       \
    } while (0)

/*
 * Log levels: 0 prints the final report only, 1 adds one line per test and
 * where a failure happened, 2 adds the "Running" lines and the messages of
 * KAO_PASS. The [KAO-C] lines are the protocol with kao and are not part of
 * what a person is meant to read.
 */
#define LOG_TESTS()                                                                \
    do {                                                                           \
        printf("\n");                                                              \
        if (kao_tests_failed)                                                      \
            LOG_NOT_SUCCESS();                                                     \
        else                                                                       \
            LOG_SUCCESS();                                                         \
        printf("[KAO-C] TOTAL#%u SUCCESS#%u FAIL#%u\n\n", kao_tests_total,         \
            kao_tests_total - kao_tests_failed, kao_tests_failed);                 \
    } while (0)

#include "kao_assert.h"

void kao_entry(void);

#endif // KAO_H
