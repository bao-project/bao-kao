# Bao Kao

Bao Kao (kao) builds, deploys and runs test guests on top of the Bao hypervisor
for a target platform, and reports the results printed by the tests over the
platform serial port.

## Layout expected by kao

kao lives in the `tests/kao` directory of the project under test and, by
default, expects the tests next to it:

```
 project
 ├── src
 ├── tests
 │   ├── kao                       (this repository, git submodule)
 │   ├── tests
 │   │   ├── src                   (test sources, any layout)
 │   │   │   ├── boot.c
 │   │   │   └── irq.c
 │   │   └── envs
 │   │       ├── baremetal         (one directory per environment)
 │   │       │   ├── qemu-aarch64-virt.yaml
 │   │       │   └── zcu104.yaml
 │   │       └── dual
 │   │           └── qemu-aarch64-virt.yaml
 │   └── tests.mk
```

The project decides how `src` is organized and which parts apply to a build.
Without further options kao considers the whole `src` tree. With `--tests-src`
(repeatable, a directory scanned non-recursively or a single file, always
under `src`) the project hands kao exactly the sources for the current
platform. `--tests-root` and `--envs` override the default locations. Tests
run in the order the sources are given.

An environment is a Bao configuration (the VMs, their images and platform
resources) described in YAML. An environment is available for a platform when
`tests/envs/<env>/<platform>.yaml` (or `<env>/<platform>/<platform>.yaml`)
exists. kao renders the YAML into the Bao `config.c` at build time.

## Writing tests

A test is an ordinary C function registered with `KAO_TEST`:

```c
#include "kao.h"

static void timer_irq(void)
{
    ...
    EXPECTED_TRUE(irq_en_timer);
}
KAO_TEST(00_00_01_00, timer_irq, TAGS(irq, timer), ENVS(baremetal), "Timer interrupt is handled");
```

The macro arguments are:

1. The ID: a token of letters, digits and underscores (`101`, `00_00_01_00`,
   `boot_smp`). kao does not interpret it; the project defines its own scheme
   and is responsible for assigning IDs. kao only refuses duplicates.
2. The function that runs the test: `static void fn(void)`. The registration
   line redeclares it, so a non-static function or another signature is a
   compile error. Tests that are not selected for a run are left out of the
   guest binary.
3. The tags, `TAGS(a, b, ...)` or a `"a, b"` string. A test can have no tags.
4. The environments the test can run in, `ENVS(a, b, ...)` or a string. At
   least one is required.
5. A description string.

Tags shared by every test in a file can be declared once, optionally, anywhere
at file scope:

```c
FILE_TAGS(arch, armv8);
```

Each test in that file then carries those tags in addition to its own. Tags
are matched case-insensitively; kao lower-cases them at discovery and on the
command line. What tags mean, and which ones a project requires, is the
project's convention; kao only matches them.

Assertions (`EXPECTED_EQUAL`, `EXPECTED_TRUE`, `KAO_FAIL`, ...) are declared in
`kao_assert.h`, and `kao_commands.h` provides the commands understood by kao
(`COMMAND_SET_TIMEOUT`, `COMMAND_SEND_CHAR`, ...). Every CPU of the guest runs
the test function; only failures recorded on the master CPU count.

kao owns the test framework under `src/kao/`: the harness `kao.c` and the
headers in `inc/`, shared by every guest, and one folder per supported guest
under `guests/` with the hook that guest's build system expects. For
[bao-baremetal-test](https://github.com/bao-project/bao-baremetal-test) that
is `guests/baremetal/src/bao-test.mk`, which its `setup.mk` includes through
`TESTF_TESTS_DIR`. Nothing is copied: kao builds a pinned checkout of the guest
with `TESTF_TESTS_DIR` pointing at that folder, the project's test sources are
included from where they live, and only the two files kao generates go to the
work directory (`KAO_GEN_DIR`).

Discovery is done by the C preprocessor: kao writes `kao_all.c`, which
includes every candidate source, and the guest's `kao-discover` target
preprocesses it with `KAO_DISCOVERY` defined, where `KAO_TEST` expands to one
marker line per test. For every environment kao then generates `kao_tests.c`,
a single file that includes the sources holding selected tests and ends with
the table the harness iterates. Descriptors and test functions are static, so
the compiler drops whatever that table does not reference. Because the
selected sources are compiled as one unit, static names and file-level macros
must be unique across test files.

Other guests follow the same shape: a folder under `guests/` with whatever
that build system needs (a `sources.mk`, a `CMakeLists.txt`, a Makefile) to
compile `kao.c` and `kao_tests.c` and to run the discovery preprocess,
plus a small port of the harness entry and `cpu_is_master`.

## Running

From the project under test:

```sh
make tests PLATFORM=qemu-aarch64-virt
```

or directly:

```sh
python3 tests/kao/src/kao.py -p qemu-aarch64-virt --hyp-srcs . -t
```

Selecting tests:

```sh
-t                       # all tests
-t 00_00_01_00,00_00_01_01   # by ID, exactly as registered
-x 00_00_01_01           # exclude IDs
--tags irq,timer         # tests carrying all of the listed tags
--exclude-tags slow      # drop tests carrying any of the listed tags
--env baremetal    # only these environments
--generate-id-readme   # print the discovered tests and exit (needs the toolchain)
```

A selected test runs once in every environment it declares that the platform
provides, unless `--env` narrows the list. Tests whose environments are all
unavailable for the platform are skipped with a warning.

Other useful options: `-l` (test log level), `-e` (serial echo filtering),
`--tests-root`, `--tests-src`, `--envs`, `--plat-virt-args`,
`--serial-port`, `--no-firmware-build`, `--no-toolchain-build`, `--wrkdir`.
Run with `-h` for the full list.

## Driving kao from a project

A project's build system typically knows which sources apply to a platform
and can pass them on. Bao's `tests/tests.mk`, for example, selects the generic
tests plus the arch and platform subtrees that match `ARCH`, `ARCH_SUB`,
`ARCH_PROFILE` and `PLATFORM`, and checks its own ID convention with a script
before invoking kao:

```make
kao_src_dirs=$(wildcard $(kao_tests)/src/00_generic) \
    $(wildcard $(kao_tests)/src/01_arch/*_$(ARCH)) \
    $(wildcard $(kao_tests)/src/02_platform/*_$(PLATFORM))

tests:
	python3 $(kao_script) -p $(PLATFORM) -t $(KAO_TESTS) --hyp-srcs $(cur_dir) \
	    $(addprefix --tests-src , $(kao_src_dirs)) $(KAO_ARGS)
```
