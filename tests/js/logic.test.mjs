// Tests for src/minidash/web/logic.js. Run: node --test tests/js/
// pytest runs this file under several browser time zones (tests/test_web_logic_js.py),
// so nothing here may depend on the machine's own zone.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  errorMessage,
  formatMoney,
  kitchenOpen,
  openIntervals,
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

test("openIntervals splits hours that cross midnight", () => {
  assert.deepEqual(openIntervals("11:00", "22:00"), [[660, 1320]]);
  assert.deepEqual(openIntervals("18:00", "02:00"), [[0, 120], [1080, 1440]]);
  assert.deepEqual(openIntervals("00:00", "00:00"), [[0, 1440]]);
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

test("timeline positions are fractions of the business day", () => {
  const t = timeline({
    dateStr: "2026-10-23",
    timeZone: NY,
    restaurant: PASTA,
    nowMs: NOW,
    rules: RULES,
    deliveryMs: ny("2026-10-23", "18:00"),
  });
  assert.deepEqual(t.open, [{ from: 11 / 24, to: 22 / 24 }]);
  assert.equal(t.tooSoonUntil, 14.75 / 24);
  assert.equal(t.delivery, 18 / 24);
  assert.deepEqual(t.kitchen, { from: 17.5 / 24, to: 18 / 24 });
});

test("timeline on the 25-hour fall-back day uses real time", () => {
  const t = timeline({
    dateStr: "2026-11-01",
    timeZone: NY,
    restaurant: ALL_DAY,
    nowMs: NOW,
    rules: RULES,
    deliveryMs: ny("2026-11-01", "12:00"),
  });
  assert.equal(t.delivery, 13 / 25); // noon is 13 real hours after midnight that day
  assert.equal(t.tooSoonUntil, 0); // "now" is before this day
});

test("timeline has no kitchen window when the delivery is on another day", () => {
  const t = timeline({
    dateStr: "2026-10-24",
    timeZone: NY,
    restaurant: PASTA,
    nowMs: NOW,
    rules: RULES,
    deliveryMs: ny("2026-10-23", "18:00"),
  });
  assert.equal(t.kitchen, null);
  assert.equal(t.delivery, null);
});
