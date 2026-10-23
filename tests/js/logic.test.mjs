// Tests for src/minidash/web/logic.js. Run: node --test tests/js/
// pytest runs this file under several browser time zones (tests/test_web_logic_js.py),
// so nothing here may depend on the machine's own zone.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  cityName,
  errorMessage,
  formatClock,
  formatHours,
  formatMoney,
  kitchenOpen,
  scheduleHint,
  statusInfo,
  suggestedDelivery,
  timeline,
  wallTimeToEpoch,
  zonedDate,
  zonedTime,
} from "../../src/minidash/web/logic.js";

const NY = "America/New_York";
const RULES = { min_lead_minutes: 45, max_horizon_days: 7, release_before_minutes: 30 };
const PASTA = { opens_at: "11:00", closes_at: "22:00" };
const NOODLES = { opens_at: "18:00", closes_at: "02:00" };
const ALL_DAY = { opens_at: "00:00", closes_at: "00:00" };
const NOW = Date.UTC(2026, 9, 23, 18, 0); // Fri 23 Oct 2026, 14:00 New York (same as conftest)
const MIN = 60_000;

const ny = (date, time) => wallTimeToEpoch(date, time, NY);
const hint = (deliveryMs, restaurant = PASTA) =>
  scheduleHint({ deliveryMs, nowMs: NOW, restaurant, timeZone: NY, rules: RULES });

test("formatMoney", () => {
  assert.equal(formatMoney(1450), "$14.50");
  assert.equal(formatMoney(5), "$0.05");
  assert.equal(formatMoney(0), "$0.00");
});

test("wall time in New York to an instant, whatever zone this process is in", () => {
  assert.equal(ny("2026-10-23", "16:00"), Date.UTC(2026, 9, 23, 20, 0)); // EDT, UTC-4
  assert.equal(ny("2026-12-01", "09:30"), Date.UTC(2026, 11, 1, 14, 30)); // EST, UTC-5
  assert.equal(zonedDate(NOW, NY), "2026-10-23");
  assert.equal(zonedTime(NOW, NY), "14:00");
});

test("a time that happens twice (1 Nov 2026, clocks go back) means the first one", () => {
  assert.equal(ny("2026-11-01", "01:30"), Date.UTC(2026, 10, 1, 5, 30)); // 01:30 EDT
});

test("a time that is skipped (14 Mar 2027, clocks go forward) lands after the gap", () => {
  assert.equal(ny("2027-03-14", "02:30"), Date.UTC(2027, 2, 14, 7, 30)); // = 03:30 EDT
});

test("the same rule in a zone east of UTC (Berlin fall-back, 25 Oct 2026)", () => {
  assert.equal(wallTimeToEpoch("2026-10-25", "02:30", "Europe/Berlin"), Date.UTC(2026, 9, 25, 0, 30));
});

test("lead-time boundaries match the server: 44:59 no, 45:00 yes", () => {
  assert.deepEqual(hint(NOW + 45 * MIN - 1000), { ok: false, code: "SCHEDULE_TOO_SOON" });
  assert.deepEqual(hint(NOW + 45 * MIN), { ok: true });
  assert.deepEqual(hint(NOW + 46 * MIN), { ok: true });
});

test("horizon boundaries match the server: 7 days yes, one second more no", () => {
  const sevenDays = 7 * 24 * 60 * MIN;
  // 7 days ahead is Fri 30 Oct 14:00, inside Pasta Palace's hours
  assert.deepEqual(hint(NOW + sevenDays), { ok: true });
  assert.deepEqual(hint(NOW + sevenDays + 1000), { ok: false, code: "SCHEDULE_TOO_FAR" });
});

test("kitchen window must sit inside opening hours", () => {
  assert.deepEqual(hint(ny("2026-10-23", "22:00")), { ok: true }); // delivery at closing
  assert.deepEqual(hint(ny("2026-10-23", "22:15")), { ok: false, code: "RESTAURANT_CLOSED" });
  assert.deepEqual(hint(ny("2026-10-23", "18:15"), NOODLES), { ok: false, code: "RESTAURANT_CLOSED" });
  assert.deepEqual(hint(ny("2026-10-23", "18:30"), NOODLES), { ok: true });
  assert.deepEqual(hint(ny("2026-10-24", "01:30"), NOODLES), { ok: true }); // after midnight
  assert.deepEqual(hint(ny("2026-10-24", "02:15"), NOODLES), { ok: false, code: "RESTAURANT_CLOSED" });
  assert.equal(kitchenOpen(ALL_DAY, ny("2026-10-23", "03:00"), ny("2026-10-23", "03:30"), NY), true);
});

test("fall-back night: closing at the first 01:30 is not the second 01:30", () => {
  const start = Date.UTC(2026, 10, 1, 6, 0); // 01:00 EST, after the first 01:30 EDT
  assert.equal(kitchenOpen({ opens_at: "18:00", closes_at: "01:30" }, start, start + 30 * MIN, NY), false);
});

test("error messages use the server's numbers and fall back for unknown codes", () => {
  assert.match(errorMessage("SCHEDULE_TOO_SOON", RULES), /45 minutes/);
  assert.match(errorMessage("SCHEDULE_TOO_FAR", { ...RULES, max_horizon_days: 3 }), /3 days/);
  assert.match(errorMessage("RESTAURANT_CLOSED", RULES), /30 minutes before delivery/);
  assert.equal(errorMessage("SOMETHING_NEW", RULES, "Server said no"), "Server said no");
});

test("status wording", () => {
  assert.equal(statusInfo("SCHEDULED").label, "Scheduled");
  assert.equal(statusInfo("PLACED").label, "Sent to the kitchen");
  assert.equal(statusInfo("CANCELLED").final, true);
  assert.equal(statusInfo("SCHEDULED").final, false);
});

test("suggested delivery is a quarter hour at least an hour away", () => {
  assert.deepEqual(suggestedDelivery(NOW, RULES, NY), { date: "2026-10-23", time: "15:00" });
  assert.deepEqual(suggestedDelivery(NOW + 1 * MIN, RULES, NY), { date: "2026-10-23", time: "15:15" });
});

test("opening hours and city wording", () => {
  assert.equal(formatClock("00:00"), "12:00 AM");
  assert.equal(formatClock("12:30"), "12:30 PM");
  assert.equal(formatClock("18:00"), "6:00 PM");
  assert.equal(formatHours("18:00", "02:00"), "6:00 PM – 2:00 AM");
  assert.equal(formatHours("00:00", "00:00"), "Open 24 hours");
  assert.equal(cityName("America/New_York"), "New York");
});

test("timeline zooms to six hours around the delivery", () => {
  const delivery = ny("2026-10-23", "18:00");
  const t = timeline({ centerMs: delivery, timeZone: NY, restaurant: PASTA, nowMs: NOW, rules: RULES, deliveryMs: delivery });
  assert.deepEqual(t.open, [{ from: 0, to: 1 }]); // 15:00-21:00 is all inside 11:00-22:00
  assert.equal(t.delivery, 0.5);
  assert.deepEqual(t.kitchen, { from: 2.5 / 6, to: 0.5 });
  assert.equal(t.tooSoonUntil, 0); // 14:45 is before the window starts
  assert.deepEqual(t.ticks.map((x) => x.label), ["3 PM", "4 PM", "5 PM", "6 PM", "7 PM", "8 PM", "9 PM"]);
  assert.equal(t.ticks[1].at, 1 / 6);
});

test("timeline shows an opening edge and the too-soon zone inside the window", () => {
  // Late Night Noodles opens 18:00. Delivery 18:30, so the window is 15:30-21:30.
  const delivery = ny("2026-10-23", "18:30");
  const now = ny("2026-10-23", "17:00"); // too soon until 17:45
  const t = timeline({ centerMs: delivery, timeZone: NY, restaurant: NOODLES, nowMs: now, rules: RULES, deliveryMs: delivery });
  assert.deepEqual(t.open, [{ from: 2.5 / 6, to: 1 }]);
  assert.equal(t.tooSoonUntil, 2.25 / 6);
  assert.deepEqual(t.kitchen, { from: 2.5 / 6, to: 0.5 });
});

test("timeline window that ends exactly at opening shows no open time", () => {
  const delivery = ny("2026-10-23", "15:00"); // window 12:00-18:00, opens at 18:00
  const t = timeline({ centerMs: delivery, timeZone: NY, restaurant: NOODLES, nowMs: NOW, rules: RULES, deliveryMs: delivery });
  assert.deepEqual(t.open, []);
});

test("timeline on the fall-back night shows 1 AM twice, an hour apart", () => {
  const center = ny("2026-11-01", "01:30"); // 05:30 UTC
  const t = timeline({ centerMs: center, timeZone: NY, restaurant: ALL_DAY, nowMs: NOW, rules: RULES, deliveryMs: null });
  assert.deepEqual(t.ticks.map((x) => x.label), ["11 PM", "12 AM", "1 AM", "1 AM", "2 AM", "3 AM"]);
  assert.deepEqual(t.open, [{ from: 0, to: 1 }]);
  assert.equal(t.kitchen, null);
  assert.equal(t.delivery, null);
});
