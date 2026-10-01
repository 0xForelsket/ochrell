# Exact target-match cache: authoring performance and equivalence

2026-10-01. Engineering optimization only; no optical model, recipe, fitting
rule, inverse solver or forward decoder changes.

Pre-change tracing of the balanced Old Holland Eight 94-stroke fixture observes
285 valid searches, 111 distinct exact f32 RGB triples and 174 repeated requests.
The independently traced loads serialize identically to production from_rgb.
Preserve this uncached OPJ2 as a pre-change oracle, with its source/helper hashes.

Add a bounded FIFO cache to each immutable PaletteMixerN instance. Default
capacity: 1024 entries; configurable, with zero disabling retention. Keys are
all three f32 bit patterns, after validation; never quantize adjacent colors.
Own entries per palette/decoder instance, including prepared-four mode, so
palettes or decoder settings cannot exchange answers accidentally. Keep cache
state out of saved formats. Expose hits, misses, evictions, entry count and
capacity. Retain every original TargetMatch field, including the original
solver's evaluation count on hits. No cache access in painting/forward decoding.

Keep Send + Sync; use a short lock for lookup/insertion and solve outside it.
Concurrent misses may duplicate searches; do not claim single-flight behavior.
Clearing the cache needs exclusive access. No new third-party dependency.

Verification: exact result bits (recipes, achieved color, both errors and original
evaluation count), adjacent f32 keys, rejected invalid inputs, model/decoder/load
isolation, bounded eviction, clear/disable behavior and concurrent callers.
Require identical authored job bytes, all five canvas planes and blurred height,
saved replay and unchanged cache counters during painting.

Benchmark the fixed balanced package and unchanged native renderer in one release
executable, single caller, three modes: disabled, cold empty, and warm populated.
Use the 285-request production fixture, 64 calls repeating 8 distinct targets,
and 64 deterministic unique targets (seed 0x8172991b, LCG as in the example).
Warm all requested keys before the timed warm call; report that priming cost
separately, never hide it as a free first-use gain. For each workload, discard
round zero and retain seven rounds rotating mode order. Constructors, serialization,
verification and painting stay outside authoring timers. Require every output
byte to match the disabled reference, plus exact pre-change OPJ2 equality.
Report all timings, median/range, request/hit/miss counts, cold overhead on unique
colors and limits from shared-host scheduling. Do not promise painting speedup.

Run scoped oil-mix/oil-palette tests and Clippy. Commit renderer implementation,
tests, benchmark and documentation, plus numerical report here. Keep optical
packages and self-contained measured painting files under ignored target/.
