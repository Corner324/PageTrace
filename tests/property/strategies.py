"""Hypothesis strategies for pagination traces.

Planned shape (docs/testing.md, section "Property-based testing"):

    valid_trace()            -> Trace with no violations by construction
    mutate(trace, operator)  -> Trace with exactly one injected defect

Mutation operators to implement alongside their detectors:
    freeze_cursor, insert_cursor_cycle, duplicate_item, skip_page, change_next_cursor,
    drop_last_page, set_has_more_true_on_final_page, duplicate_response, corrupt_total

Filled in when the domain model (src/pagetrace/model.py) exists. Nothing to import yet.
"""
