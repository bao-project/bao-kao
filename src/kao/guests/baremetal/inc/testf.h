/*
 * Copyright (c) Bao Project and Contributors. All rights reserved
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/* bao-baremetal-test's main.c includes testf.h and calls testf_entry(). */
#include "kao.h"

static inline void testf_entry(void)
{
    kao_entry();
}
