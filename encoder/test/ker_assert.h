/* Copyright 2026 Eckstein GmbH Apache-2.0; see LICENSE.txt at the repository root.
 * MODIFICATION NOTICE: new file, not present in upstream OpenArm.
 *
 * Minimal check harness for the host unit tests. No framework, so the tests
 * build with nothing but a C compiler on any machine that can build the
 * firmware sources. */
#ifndef KER_ASSERT_H
#define KER_ASSERT_H
#include <stdio.h>
static int ker_checks, ker_fails;
#define CHECK(cond, ...) do {                                        \
    ker_checks++;                                                    \
    if (!(cond)) { ker_fails++;                                      \
      printf("  FAIL %s:%d: ", __FILE__, __LINE__);                  \
      printf(__VA_ARGS__); printf("\n"); }                           \
  } while (0)
#define SECTION(name) printf("- %s\n", name)
static int ker_report(const char *suite) {
  printf("%s: %d checks, %d failures\n", suite, ker_checks, ker_fails);
  return ker_fails != 0;
}
#endif
