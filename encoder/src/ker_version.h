// Copyright 2026 Eckstein GmbH
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
// ---------------------------------------------------------------------------
// MODIFICATION NOTICE
// New file, not present in upstream OpenArm. Added by the calibrated-encoder
// fork: what GET_FW_VER reports (protocol-spec.md section 4.6, SUB 0x02).
// tools/pio_version.py overrides KER_GIT_HASH and KER_GIT_DIRTY from the working
// tree at build time; the defaults below are what a build outside git reports.
// ---------------------------------------------------------------------------

#ifndef KER_VERSION_H
#define KER_VERSION_H

#define KER_FW_MAJOR 1
#define KER_FW_MINOR 0
#define KER_FW_PATCH 0

#ifndef KER_GIT_HASH
#define KER_GIT_HASH 0x0000      /* first 4 hex digits of the commit; 0 = unknown */
#endif
#ifndef KER_GIT_DIRTY
#define KER_GIT_DIRTY 1          /* pessimistic: an unidentified build is "dirty" */
#endif

/* The protocol version GET_PROTO_VER reports. Spec v6 did not change the
 * protocol, so this stays 5. */
#define KER_PROTO_VER 5

#endif /* KER_VERSION_H */
