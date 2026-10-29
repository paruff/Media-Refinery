# Review backlog: written deferrals (G20, #128)

Fixed in G20: #103 cookie `Secure`/`max_age`, `/ui/logout`, login throttle, opt-in Host allow-list;
#105 loopback compose bind. Everything below is **deferred**; Minor items in each issue are deferred
with the same reason as the Important ones for that issue. Only `music` is on by default, so none of
these affect the default pipeline unless noted. The matching type must close its Important items
before promotion (see PROMOTION.md).

## Important items, still open

| Issue | Item | Deferral reason / trigger |
|-------|------|---------------------------|
| #96 | `convert.py:36` failed repair leaves partial `*_fixed`, no fallback to original | video is parked; fix before promoting video |
| #100 | Chapter starts/duration not verified; late parts and gaps (R-PIPE-6) undetected | audiobooks parked; both block audiobook promotion |
| #103 | UI before→after diff (path, codecs, tags, artwork) | spec gap; UI shows path pair only. Needs a spec decision, not a quick fix |
| #107 | CI container never proves `/health`; `make ci` lacks 80 % floor; `security.yml` `continue-on-error` | CI hygiene, not user data; smoke job (G12) partly covers `/health`. Next CI pass |
| #108 | `_prune_old_errors` blanks `error_log` of error/quarantined rows older than 30 d | data-loss of diagnostics only; highest-value follow-up, first fix after this PR |
| #108 | Watcher drops failed imports, no re-stat after hash | can affect music ingest; second follow-up |
| #108 | `get_event_loop`, blocking `os.walk` in `startup_scan` | same watcher pass |
| #108 | Video fingerprint silently disabled when frame count is 0/-1 | video parked |
| #108 | D3 regression test can skip via `importorskip` | make hard imports in the CI pass |
| #108 | `_execute_normalization_plan` early return on existing output | video/legacy path; fix with orchestrator work |

## Non-blocking Minors

All other unchecked Minor items in #96-#105, #107, #108 stay open in their issues as the tracker.
Not scheduled; pick up when the relevant type is promoted or when hit in practice.
