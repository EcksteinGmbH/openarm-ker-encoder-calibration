# Copyright 2026 Eckstein GmbH
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# ---------------------------------------------------------------------------
# MODIFICATION NOTICE
# New file, not present in upstream OpenArm. PlatformIO pre-script that stamps
# the commit into the image, so GET_FW_VER (protocol-spec.md section 4.6, SUB
# 0x02) identifies exactly what a module is running. A build outside git, or
# from a dirty tree, says so rather than claiming a commit.
# ---------------------------------------------------------------------------
import subprocess

Import("env")


def _git(*args):
    return subprocess.check_output(("git",) + args, stderr=subprocess.DEVNULL).decode().strip()


try:
    short = _git("rev-parse", "--short=4", "HEAD")
    dirty = 1 if _git("status", "--porcelain") else 0
    env.Append(CPPDEFINES=[("KER_GIT_HASH", "0x" + short), ("KER_GIT_DIRTY", str(dirty))])
    print("ker: build stamped %s%s" % (short, " (dirty)" if dirty else ""))
except Exception:
    print("ker: no git metadata; GET_FW_VER will report hash 0000, dirty")
