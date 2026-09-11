# Engineering principles (the constitution)

Priority order: correctness > simplicity > maintainability > performance > development speed.

1. **Never claim more than the trace proves.**
2. Proven facts, suspicion, and insufficient evidence are three different states. Never a number.
3. Core analysis is deterministic and side-effect free: same normalized trace, same findings,
   same order, same evidence. No clock, no randomness, no environment in the core.
4. PageTrace never performs network requests.
5. A runtime dependency needs a concrete failure mode it prevents. Record it in an ADR.
6. No speculative abstractions: no plugins, no DI, no interfaces with one implementation.
7. Machine-readable output is a compatibility surface: finding codes, exit codes, flags, schema.
8. Security diagnostics never dump arbitrary HAR content. Headers and bodies stop at the parser.
9. AI review is never a merge gate. Merge is decided by spec, tests, static analysis, and CI.
10. A fixed bug always leaves a regression oracle behind.
