/* This site's own script, inlined after statusui's shared ui.js in both
   index.html and the county pages, so anything both pages need lives here
   rather than being copied into each template. */

/* How old the data behind this page is, said as an age rather than a timestamp.
   "Data to 26 Aug, 06:04 UTC" asked every reader to do timezone arithmetic to
   answer the only question they were asking, which is "is this current?".

   The build clock stays out of it: a reader cares where the record stops, not
   when the site was assembled.

   The worry a relative stamp raises is that a normal overnight gap reads as
   neglect - pushes land at local midnight and noon, so data ~14h old is
   healthy. Softening the wording does not fix that, because the problem is not
   that 14 is a large number: it is that a large number from a healthy schedule
   is indistinguishable from a collector that died. So state the age plainly in
   one unit and let a separate, explicit warning carry "something is wrong". The
   reassurance is the absence of that warning, which costs no words on a normal
   render. `staleHours` is STALE_AFTER from render.py, and the check runs on the
   reader's clock rather than the build's, so a page served from cache long
   after it was built still says so.

   One unit all the way up, as every relative-time library does. Mirrors the
   same reasoning in uisce's freshness(). */
function freshness(iso, staleHours) {
  var mins = Math.round((Date.now() - Date.parse(iso)) / 60000);
  // a reader's clock can be wrong and a cached page can be older than it says;
  // neither may ever render as "in 20 minutes"
  if (mins < 2) return "Updated just now";
  var age;
  if (mins < 60) {
    age = mins + " minutes ago";
  } else if (mins < 24 * 60) {
    // round, not floor, for the display: flooring reports 11h59m as "11 hours",
    // and understating the page's own age is the one direction it must not round
    var h = Math.round(mins / 60);
    age = h + " hour" + (h === 1 ? "" : "s") + " ago";
  } else {
    var d = Math.round(mins / (24 * 60));
    age = d + " day" + (d === 1 ? "" : "s") + " ago";
  }
  // gated on the exact elapsed minutes, not on the rounded hours: rounding
  // first would trip the warning half an hour before STALE_AFTER
  if (mins < staleHours * 60) return "Updated " + age;
  return '<span class="stale">Updated ' + age + " - collection has stopped</span>";
}

/* The county pages carry no data.js, so their stamp travels on the element the
   build wrote it into. The separator rides with the age rather than sitting in
   the markup, so a page whose script never ran reads "Data to ..." on its own
   instead of opening on a stray bullet. */
function bindStamp(el) {
  if (!el) return;
  var iso = el.getAttribute("data-observed");
  el.innerHTML = freshness(iso, +el.getAttribute("data-stale-hours")) + " · ";
}
