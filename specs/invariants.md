# Invariants: the correctness contract

Status: normative. This is the most important file in the repository. Every detector implements
exactly one entry here; every test for a detector references its ID.

## ID scheme

`INV-<FAMILY>-<NNN>`. Families: `CURSOR`, `PAGE`, `OFFSET`, `ITEM`, `CONT` (continuation /
`has_more`), `TOTAL`, `TRACE` (whole-trace consistency), `RESP` (response fingerprint).

IDs are never reused. A withdrawn invariant keeps its entry with status `Withdrawn`.

## Vocabulary

- **Certainty** (what the evidence supports): `PROVEN` | `SUSPICIOUS` | `INSUFFICIENT_EVIDENCE`.
- **Severity** (how much it matters if true): `INFO` | `WARNING` | `ERROR`.
- Certainty and severity are independent axes. A finding is never a probability.
- **Evidence**: structured observed facts, e.g. `page[4].response.next_cursor = "abc"`.
  Conclusions are never evidence.

## Global preconditions

These apply to every entry below and are enforced once, in the normalizer and the engine.

1. **Observation is three-valued.** A selector either resolves to exactly one scalar
   (`OBSERVED`), or it does not (`NOT_CONFIGURED`, `NOT_FOUND`, `AMBIGUOUS` for multiple nodes,
   `NOT_SCALAR` for an object or array where a scalar is required). Only `OBSERVED` may support
   a `PROVEN` claim.
2. **JSON `null` is an observation, not an absence.** `{"next": null}` is observed with value
   `null` and means "the server declared no continuation". A selector that matched nothing is a
   different state and proves nothing.
3. **Scalar comparison uses the canonical text form.** Integer `5` and string `"5"` compare
   equal, because a query parameter can only carry text. A type-only difference is never a
   mismatch. `true` and `"true"` likewise.
4. **Non-2xx pages are excluded from body-derived reasoning.** An error response body is not a
   page of results. Such pages are skipped by every detector that reads the body, and a
   transition touching one is not checked at all. The exclusion is reported once for the whole
   trace by INV-TRACE-002 rather than by each detector separately, so a trace nobody could read
   never looks like a trace that was fine.
5. **One insufficient-evidence finding per detector per trace.** Detectors summarize
   ("3 of 12 transitions had no observable cursor") instead of emitting per-page noise.
6. **A fact is reported once.** When two detectors would describe the same observation, the
   more specific one wins and the other stays silent. Overlaps are resolved explicitly in the
   entries below, never by post-filtering.
7. **A request that could not carry a page is not a page.** `OPTIONS` and `HEAD` requests are
   dropped before pages are numbered. A browser HAR puts a CORS preflight in front of every
   cross-origin request, repeating its URL and query; left in, it is indistinguishable from a
   client that failed to advance.
8. **Messages never contain values from the trace.** A finding's message is written by
   PageTrace; every value taken from the trace travels in `evidence`, where it is escaped and
   truncated on the way out. A value interpolated into a message would bypass that, which put
   raw terminal escapes on screen and produced invalid JUnit XML.

## Entry template

```
### INV-XXX-NNN <short name>
Status: Draft | Active | Withdrawn
Preset(s): cursor | page | offset | link | any
Preconditions: what must be observable before the detector may run at all
Claim: the exact statement the finding makes when it fires
Certainty: PROVEN | SUSPICIOUS, with the condition for each
Severity: ...
Evidence: which observations are attached
Non-claim conditions: when the detector MUST stay silent or downgrade to INSUFFICIENT_EVIDENCE
Finding code: SCREAMING_SNAKE, public contract
Tests: tests/... referencing this ID
```

## Summary table

| ID | Detector | Preconditions | Allowed conclusion |
| -- | -------- | ------------- | ------------------ |
| INV-CURSOR-001 | next/request cursor mismatch | both values observable | PROVEN |
| INV-CURSOR-002 | request cursor repeated on consecutive pages | cursor preset | PROVEN stall |
| INV-CURSOR-003 | cursor cycle of length >= 2 | request cursors observable | PROVEN |
| INV-ITEM-001 | duplicate item across pages | item IDs observable | duplicate PROVEN; pagination bug only SUSPICIOUS |
| INV-RESP-001 | identical consecutive page | comparable response bodies | SUSPICIOUS |
| INV-PAGE-001 | page number does not advance by one | page semantics configured | PROVEN |
| INV-OFFSET-001 | offset jump | offset progression established then broken | PROVEN, else SUSPICIOUS |
| INV-CONT-001 | `has_more=true` and trace ends | `has_more` observable | PROVEN trace incompleteness |
| INV-CONT-002 | `has_more=true` with empty page | items and has_more observable | SUSPICIOUS |
| INV-TRACE-001 | trace ends with an unused continuation token | next cursor observable | PROVEN trace incompleteness |
| INV-TRACE-002 | requests excluded from analysis | a non-2xx page exists | INSUFFICIENT_EVIDENCE |
| INV-TOTAL-001 | total mismatch | stable total + proven termination + full item visibility | PROVEN, else SUSPICIOUS |

Things that can never be claimed from a finite trace: "pagination never terminates",
"records are missing" with an opaque cursor, "the API is at fault" for an incomplete capture.

## Entries

### INV-CURSOR-001 Continuation cursor mismatch
Status: Active
Preset(s): cursor, link
Preconditions:
- page `n+1` exists;
- `page[n].response.next_cursor` is OBSERVED and not `null`;
- `page[n+1].request.cursor` is OBSERVED;
- both pages returned a 2xx status.
Claim: page n+1 was requested with a continuation token different from the one page n returned.
Certainty: PROVEN. The mismatch is a fact about the recorded trace; PageTrace does not claim
which side caused it.
Severity: ERROR
Evidence: `page[n].response.next_cursor`, `page[n+1].request.cursor`.
Non-claim conditions:
- `next_cursor` is `null` or an empty string: the server declared termination, so the next
  request starting elsewhere is a different fact (see INV-CURSOR-002 and INV-TRACE-001);
- either value is not OBSERVED (selector missing, not configured, ambiguous, or non-scalar):
  counted toward the single INSUFFICIENT_EVIDENCE finding, never a mismatch;
- the values differ only in JSON type (`5` vs `"5"`, `true` vs `"true"`): equal by global
  precondition 3, no claim;
- `page[n+1].request.cursor` equals `page[n].request.cursor`: the client repeated the same
  request. That single fact belongs to INV-CURSOR-002; this detector stays silent to avoid
  reporting one observation twice;
- either page is non-2xx: the body may be an error envelope, no claim;
- page 0 has no incoming cursor: normal, never reported.
Finding code: CURSOR_CONTINUATION_MISMATCH
Tests: tests/unit/test_cursor_continuation.py, tests/property/test_valid_traces.py, tests/property/test_cursor_mutations.py

### INV-CURSOR-002 Request cursor stalled
Status: Active
Preset(s): cursor, link
Preconditions: `page[n].request.cursor` and `page[n+1].request.cursor` are both OBSERVED and
canonically equal; both pages are 2xx.
Claim: the same pagination state was requested twice in a row; the client did not advance.
Certainty: PROVEN that the state repeated.
Severity: ERROR
Evidence: `page[n].request.cursor`, `page[n+1].request.cursor`, and
`page[n].response.next_cursor` when observed.
Non-claim conditions:
- page n returned a non-2xx status: a retry of a failed request is ordinary client behavior,
  no claim;
- the cursor is not OBSERVED on either side of a transition: insufficient evidence, summarized
  once for the trace. One side missing is ordinary, because page 0 carries no incoming cursor,
  and a finding there would fire on every well-formed trace;
- one finding per stalled value: a run of the same cursor is a single fact, but a stall on one
  value and a later stall on another are two, and INV-CURSOR-001 stays silent on both pairs in
  the belief that this detector reports them.
Finding code: CURSOR_STALLED
Tests: tests/unit/test_cursor_cycles.py, tests/property/test_cursor_mutations.py

### INV-CURSOR-003 Cursor cycle
Status: Active
Preset(s): cursor, link
Preconditions: a request cursor value OBSERVED on page `i` is OBSERVED again on page `j`,
with `j - i >= 2`; every page in `[i, j]` is 2xx.
Claim: the request-cursor sequence returned to a state it had already visited, forming a cycle
of length `j - i`.
Certainty: PROVEN that the recorded sequence revisits a state. PageTrace does not claim that
pagination would loop forever; a finite trace cannot prove non-termination.
Severity: ERROR
Evidence: `page[i].request.cursor`, `page[j].request.cursor`, and the cursor values of the
pages between them (truncated).
Non-claim conditions:
- `j - i == 1`: that is a stall, reported by INV-CURSOR-002 instead;
- the repeated value is the page-0 starting state and `page[j-1].response.next_cursor` was
  `null` or absent: the file most likely contains two separate pagination runs concatenated,
  which PageTrace cannot distinguish from a cycle. Downgrade to SUSPICIOUS and say so;
- any page in the range is non-2xx: retries after failures are ordinary, downgrade to
  SUSPICIOUS;
- only the first cycle is reported.
Finding code: CURSOR_CYCLE
Tests: tests/unit/test_cursor_cycles.py, tests/property/test_cursor_mutations.py

### INV-ITEM-001 Duplicate item across pages
Status: Active
Preset(s): any
Preconditions: `--items` and `--id` are configured and the id selector resolves to a scalar for
the items involved; both pages are 2xx.
Claim: the same item identity was observed on two or more pages.
Certainty: the duplicate observation is PROVEN. The interpretation "pagination returned
overlapping windows" is SUSPICIOUS, because overlapping windows can be part of the API contract
or a consequence of a mutable dataset. The finding message states the observation, and names
the interpretation as a possibility only.
Severity: WARNING
Evidence: the first and the repeat occurrence, as `page[i].items[j].id`.
Non-claim conditions:
- never upgrade to a pagination-bug claim without a documented uniqueness contract; PageTrace
  has no way to learn one from a trace;
- items whose id selector yields no scalar are excluded and counted once as insufficient
  evidence, not reported per item;
- identity uses the canonical text form (global precondition 3), so an id of `5` and an id of
  `"5"` are the same item. An API that means those as different items is not one PageTrace can
  read;
- duplicates *within* one page are a different fact and are not claimed here: a single response
  containing a repeated id says nothing about pagination;
- non-2xx pages are excluded.
Finding code: DUPLICATE_ITEM_ACROSS_PAGES
Tests: tests/unit/test_items.py, tests/property/test_cursor_mutations.py

### INV-RESP-001 Identical consecutive responses
Status: Active
Preset(s): any
Preconditions: both pages are 2xx and both response bodies were parsed as JSON.
Claim: two consecutive pages returned identical response bodies.
Certainty: SUSPICIOUS. Identical bodies are consistent with a stuck paginator, with a cache, and
with a legitimately unchanged resource. Never PROVEN as a pagination defect.
Severity: WARNING
Evidence: `page[n].response.fingerprint`, `page[n+1].response.fingerprint`, item counts.
Non-claim conditions:
- both pages are empty (no items observed): trailing empty pages are common and prove nothing;
- a cursor stall (INV-CURSOR-002) already covers the pair: the stall is the more specific fact,
  so this detector stays silent for that pair;
- only the first occurrence in a run of identical pages is reported. A run is tracked by page
  index, not by a flag: pairs touching a non-2xx page are never offered to this detector, and a
  stale flag would swallow the next run of identical pages entirely.
Finding code: IDENTICAL_CONSECUTIVE_RESPONSES
Tests: tests/unit/test_sequence.py

### INV-PAGE-001 Page number does not advance by one
Status: Active
Preset(s): page
Preconditions: preset `page`; `page[n].request.page` and `page[n+1].request.page` are both
OBSERVED as integers; both pages are 2xx.
Claim: the requested page number changed by `delta` instead of 1.
Certainty: PROVEN. Only the delta is used, so 0-based and 1-based APIs are both handled without
assuming either.
Severity: ERROR
Evidence: both page numbers and the computed delta.
Non-claim conditions:
- values are not integers (a page token that merely looks numeric): insufficient evidence;
- page n is non-2xx: a retry with the same number is ordinary;
- only the first violating transition is reported;
- the direction of iteration is never assumed to be a defect on its own; a strictly decreasing
  trace still violates `delta == 1` and is reported with its actual delta, not as "backwards".
Finding code: PAGE_NUMBER_JUMP
Tests: tests/unit/test_sequence.py

### INV-OFFSET-001 Offset does not advance by the number of items returned
Status: Active
Preset(s): offset
Preconditions: preset `offset`; `request.offset` OBSERVED as an integer on both pages;
the item count of page n is observable (`--items` configured and the selector resolves to an
array); both pages are 2xx.
Claim: `offset[n+1]` is not `offset[n] + item_count[n]`.
Certainty: PROVEN only when at least one transition **before** this one satisfied
`offset[n+1] == offset[n] + item_count[n]`, which establishes that this API does use that
contract. A transition after the violation shows the contract held later, not that it was
established when the violation happened. Without an earlier witness the contract is an
assumption about the API, not an observation, and the finding is SUSPICIOUS.
Severity: ERROR
Evidence: both offsets, the item count of page n, the expected value.
Non-claim conditions:
- item count not observable: insufficient evidence, never a guess from a `limit` parameter;
- page n is non-2xx;
- the offset unit is not items (some APIs offset by bytes, tokens, or time): PageTrace cannot
  detect this, which is exactly why the first transition only establishes the contract and
  never proves a violation;
- only the first violating transition is reported.
Finding code: OFFSET_JUMP
Tests: tests/unit/test_sequence.py

### INV-CONT-001 Trace ends after `has_more=true`
Status: Active
Preset(s): any with `--has-more`
Preconditions: the `has_more` selector resolves to boolean `true` on the final 2xx response of
the trace.
Claim: the trace ended after a response that declared further pagination. The capture may be
incomplete, or pagination may have stopped prematurely.
Certainty: PROVEN, about the trace. Never about the API.
Severity: WARNING
Evidence: `page[last].response.has_more = true`, `trace.page_count`.
Non-claim conditions:
- the wording never attributes fault to the API, the client, or the recorder; PageTrace cannot
  distinguish them and says so in the message;
- `has_more` not OBSERVED on the final page: silence, not an insufficient-evidence finding.
  Every preset supplies a default selector, so a trace with no continuation flag at all is
  indistinguishable from a misconfigured one, and reporting it would fire on every trace that
  simply does not use `has_more`. INV-CURSOR-001 can afford the summary because it counts
  transitions it was asked to check;
- a truthy non-boolean value (`"true"`, `1`): treated as observed only when the configured
  selector yields a boolean, otherwise insufficient evidence. PageTrace does not invent
  truthiness rules for someone else's API.
Finding code: TRACE_ENDS_WITH_HAS_MORE
Tests: tests/unit/test_continuation.py, tests/property/test_cursor_mutations.py

### INV-CONT-002 `has_more=true` with an empty page
Status: Active
Preset(s): any with `--has-more` and `--items`
Preconditions: a 2xx page where `has_more` is boolean `true` and the items selector resolves to
an empty array.
Claim: the server declared more results while returning none on this page.
Certainty: SUSPICIOUS. Some APIs legitimately return empty intermediate pages, for example when
a filter is applied after the window is selected.
Severity: WARNING
Evidence: `page[n].response.has_more`, `page[n].response.items` length.
Non-claim conditions:
- the page is the last one in the trace: INV-CONT-001 already reports it, this stays silent;
- items selector not configured or not an array: insufficient evidence.
Finding code: EMPTY_PAGE_WITH_HAS_MORE
Tests: tests/unit/test_continuation.py, tests/property/test_cursor_mutations.py

### INV-TRACE-001 Trace ends with an unused continuation token
Status: Active
Preset(s): cursor, link
Preconditions: the final 2xx page's `next_cursor` is OBSERVED, not `null`, and not an empty
string; no further page exists.
Claim: the trace ended while the server was still offering a continuation token. The capture may
be incomplete, or pagination may have stopped prematurely.
Certainty: PROVEN, about the trace.
Severity: WARNING
Evidence: `page[last].response.next_cursor` (truncated), `trace.page_count`.
Non-claim conditions:
- INV-CONT-001 already fired for the same final page: the two describe the same stop, so only
  INV-CONT-001 is reported;
- `next_cursor` is `null` or empty: a normal termination;
- never worded as "the API failed to return the next page".
Finding code: TRACE_ENDS_WITH_CONTINUATION
Tests: tests/unit/test_continuation.py, tests/property/test_cursor_mutations.py

### INV-TOTAL-001 Declared total does not match the observed items
Status: Active
Preset(s): any with `--total`, `--items`, `--id`
Preconditions, all required:
- `total` is OBSERVED as an integer on at least one page and every page that reports it reports
  the same value (a changing total means a mutable dataset);
- the items selector resolves to an array on every 2xx page, so nothing is unseen;
- the id selector resolves for every item, so distinct items can be counted exactly;
- termination is proven: the final page has `has_more == false`, or `next_cursor` is `null` or
  empty. An incomplete capture explains any shortfall by itself.
Claim: the number of distinct item identities observed differs from the declared total.
Certainty: PROVEN when every precondition above holds. SUSPICIOUS when the total is stable and
the trace is terminated but item identity is incomplete. Silent otherwise.
Severity: WARNING
Evidence: declared total, distinct item count, raw item count, page count.
Non-claim conditions:
- never phrase the finding as "N records are missing": PageTrace does not know that `total`
  counts the same population as the items, that the dataset was stable during capture, or that
  the same filters applied to both;
- any request in the trace returned a non-2xx response: a window of items was never observed at
  all, so the comparison is at most SUSPICIOUS however tidy the remaining pages look;
- any page declares a total that is observed but is not an integer: taking the integer from the
  other pages would be choosing which observation to believe;
- the total changes between pages: report nothing, the dataset moved under the paginator;
- duplicates were found (INV-ITEM-001): distinct and raw counts are both reported, and the
  finding stays SUSPICIOUS because overlapping windows change what `total` should be compared
  against;
- the trace is not proven terminated: silent, because INV-CONT-001 or INV-TRACE-001 already
  reports the incompleteness and a count comparison on a partial trace proves nothing.
Finding code: TOTAL_COUNT_DISCREPANCY
Tests: tests/unit/test_totals.py, tests/property/test_cursor_mutations.py

### INV-TRACE-002 Requests excluded from analysis
Status: Active
Preset(s): any
Preconditions: at least one request in the trace returned a non-2xx response.
Claim: those requests were left out of every check that reads a response body, and the
transitions touching them were not checked at all.
Certainty: INSUFFICIENT_EVIDENCE, always. This entry exists so that silence can be told apart
from a clean result; it never asserts that anything is wrong.
Severity: INFO
Evidence: the index and status of up to ten excluded pages.
Non-claim conditions: never suggests why a request failed, and never treats a failure as a
pagination defect. A trace of nothing but errors produces this finding and nothing else, which
is the correct answer.
Finding code: REQUESTS_EXCLUDED_FROM_ANALYSIS
Tests: tests/unit/test_coverage.py
