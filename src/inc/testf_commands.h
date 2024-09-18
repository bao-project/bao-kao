/*
 * Copyright (c) Bao Project and Contributors. All rights reserved
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef TESTF_COMMANDS_H
#define TESTF_COMMANDS_H

#define PRINT_FUNCTION printf
#define TESTF_TAG "[TESTF-C] "

#define TESTF_COMMAND(X) PRINT_FUNCTION(TESTF_TAG X "\n")

#define COMMAND_START()     PRINT_FUNCTION(TESTF_TAG "START" "\n")
#define COMMAND_END()       PRINT_FUNCTION(TESTF_TAG "END" "\n")
#define COMMAND_SEND_CHAR(X) PRINT_FUNCTION(TESTF_TAG "SEND_CHAR " X "\n")

#endif // TESTF_COMMANDS_H