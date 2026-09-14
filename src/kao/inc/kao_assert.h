/*
 * Copyright (c) Bao Project and Contributors. All rights reserved
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef KAO_ASSERT_H
#define KAO_ASSERT_H

#define EXPECTED_EQUAL(x, y)     KAO_ASSERT_OP(x, y, ==)
#define EXPECTED_NOT_EQUAL(x, y) KAO_ASSERT_OP(x, y, !=)
#define EXPECTED_TRUE(x)         KAO_ASSERT_OP(x, 0, !=)
#define EXPECTED_FALSE(x)        KAO_ASSERT_OP(x, 0, ==)
#define EXPECTED_PTR_NULL(x)     KAO_ASSERT_OP(x, NULL, ==)
#define EXPECTED_PTR_NOT_NULL(x) KAO_ASSERT_OP(x, NULL, !=)

#define EXPECTED_ARRAY_EQUAL(ptr1, ptr2, count, type)                   \
    do {                                                                \
        unsigned int intra_fails = 0;                                   \
        for (int i = 0; i < (count); i = i + 1) {                       \
            if (((const type*)(ptr1))[i] != ((const type*)(ptr2))[i]) { \
                KAO_RECORD_FAILURE();                                 \
                intra_fails++;                                          \
                if (intra_fails == 1)                                   \
                    LOG_FAILURE();                                      \
                if (KAO_LOG_LEVEL > 1) {                              \
                    printf("    Index: %d\n", i);                       \
                }                                                       \
            }                                                           \
        }                                                               \
    } while (0)

#define EXPECTED_ARRAY_NOT_EQUAL(ptr1, ptr2, count, type)               \
    do {                                                                \
        unsigned int intra_fails = 0;                                   \
        for (int i = 0; i < (count); i = i + 1) {                       \
            if (((const type*)(ptr1))[i] != ((const type*)(ptr2))[i]) { \
                intra_fails++;                                          \
            }                                                           \
        }                                                               \
        if (intra_fails == 0) {                                         \
            KAO_RECORD_FAILURE();                                     \
            LOG_FAILURE();                                              \
        }                                                               \
    } while (0)

#define KAO_ASSERT_OP(x, y, op)   \
    do {                            \
        if (!(x op y)) {            \
            KAO_RECORD_FAILURE(); \
            LOG_FAILURE();          \
        }                           \
    } while (0)

#define KAO_PASS(message)                       \
    do {                                          \
        if (KAO_LOG_LEVEL > 1) {                \
            printf("    Message: %s\n", message); \
        }                                         \
    } while (0)

#define KAO_FAIL(message)                   \
    do {                                      \
        KAO_RECORD_FAILURE();               \
        LOG_FAILURE();                        \
        printf("    Message: %s\n", message); \
    } while (0)

#endif // KAO_ASSERT_H
