/*
 * Copyright (c) Bao Project and Contributors. All rights reserved
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef KAO_COMMANDS_H
#define KAO_COMMANDS_H

#define PRINT_FUNCTION   printf
#define KAO_TAG        "[KAO-C] "

#define KAO_COMMAND(X) PRINT_FUNCTION(KAO_TAG X "\n")

#define COMMAND_START()              \
    PRINT_FUNCTION(KAO_TAG "START" \
                             "\n")
#define COMMAND_END()              \
    PRINT_FUNCTION(KAO_TAG "END" \
                             "\n")

#define COMMAND_SEND_CHAR(X)    PRINT_FUNCTION(KAO_TAG "SEND_CHAR " X "\n")
#define COMMAND_SET_TIMEOUT(X)  PRINT_FUNCTION(KAO_TAG "SET_TIMEOUT " X "\n")
#define COMMAND_CLEAR_TIMEOUT() PRINT_FUNCTION(KAO_TAG "CLEAR_TIMEOUT\n")

#endif // KAO_COMMANDS_H
