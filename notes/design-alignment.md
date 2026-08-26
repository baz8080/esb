# Aligning the design language with uisce

2026-08-26. The owner reviewed both home pages side by side and picked a winner
per element, so the two sites read as one product before the same language is
applied to lifts. What esb absorbed:

- **Banner** takes uisce's format: `**August 2026 so far:** 978 faults and
  1,122 planned outages` — the bold month-and-colon prefix, the long month
  name, and " so far" only while the viewed month is still collecting
  (`D.observed_iso` month == viewed month). The old trailing "in Aug 2026" and
  the all-bold single `<strong>` went with it.
- **National heading** takes uisce's format: "The national picture in August
  2026", filled per month, replacing the static "Nationally this month" which
  read wrong on every past month.
- **Footer**: "How the grade is worked out" and "The other figure: Customer
  Minutes Lost" merged into one disclosure, "How these numbers are worked out",
  and every disclosure was tightened for a lay reader — the measured detail
  (1,460-outage back-dating check, 8 revisions, the 30-minute poll mechanics)
  lives in `notes/grading.md`, not the page. The final line is now the shared
  format: "Source code · not affiliated with ESB Networks or the CRU."
- **The horizon left the footer** — an owner decision, reversing the earlier
  "the exact horizon stays in the footer" note. "Built twice daily … Data to
  Wed 26 Aug, 06:04 UTC." was removed; the age chip stays, and the exact
  horizon survives as the chip's hover `title` and, in full, in each county
  page's sub line (which is a cold-entry surface and keeps its no-JS text).
- **Search behaviour moved upstream** to statusui (`searchHits`/`bindSearch`);
  this page keeps only the markup, the index build and the pick handler. uisce
  gets the same box in place of its sort control.
- `site.css` shrank: `--row-cols`/`--stats-cols` (identical to base),
  `.stats .cml` and the mobile legend-order override all moved into (or were
  already in) statusui's base.css, because uisce wanted the same values.

esb's own layout was the reference for the county rows (chevron, two-line
percentage stat, right-aligned counts) and the county-page card
(legend → tall bar → tiles), so nothing changed here on those.

## The county page got a way in from the app — 2026-08-26

The app never linked to `c/<slug>.html`. The page linked into the app ("open the interactive view"), so it was a one-way trip, and the missing leg was the one that matters: a reader already looking at Cork had no way to reach Cork's durable address.

`renderCounty` now carries a link on its own line under the heading, above the month tabs — the placement lifts uses and uisce adopted at the same time. The rule that styles it, `.chead + .sub`, is promoted to statusui's `base.css`; this repo and lifts had been carrying it byte for byte and uisce is now a third consumer. The local copy stays until the pin moves — `uv.lock` can only track statusui's `main`, so deleting it here would unstyle the line on the deployed site until rollout.

Placed above the tabs rather than below despite the risk of reading as a tab modifier: the `margin-bottom: 16px` on `.sub` separates them, and matching the other two sites was worth more than the residual ambiguity.

**Wording: "Every month for County Cork on one page", not "permalink".** The label makes a promise, so it has to match what is actually on the other side. This view is one month at a time; the page — since it became an archive earlier the same day — is every month plus the outage history. Naming that difference gives a reader a reason to follow the link.

**uisce says the same sentence**, because its county page stands in the same relation to its county view: one month there, every month here. It briefly said "Every notice ever recorded in Co. Carlow" instead and that was wrong — its page caps the notice list at 60 and prints "older notices not shown here", so the label was contradicted by the page it landed on. Two categories, not three: esb and uisce name the months; lifts says "Permanent link to Athy station", because its page carries the same months and cases its view does and naming *that* for its content would promise something the reader is already looking at. Same placement on all three.

"Permalink" was rejected here for two reasons: it undersells a page that now has more than the view, and it is blogging-era vocabulary a general audience mostly does not hold. The county is in the link text because a screen reader lists links stripped of their context.

The overview row's `<a href>` already pointed at the page with the click suppressed, so a crawler and a "copy link address" always reached it; this closes the gap for a reader who has already drilled in.

Guarded by `tests/test_permalink_affordance.py`.
