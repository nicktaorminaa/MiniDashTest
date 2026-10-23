// Pure helpers for the MiniDash page: no DOM, no network, no clock of their own.
// Tested with Node's built-in runner (tests/js/logic.test.mjs, run from pytest).
//
// Times the customer types are wall-clock times in the restaurant time zone (from GET /config),
// whatever zone the browser is in. Every calculation below works on epoch milliseconds.

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

export function formatMoney(cents) {
  return `$${(cents / 100).toFixed(2)}`;
}

/** Wall-clock parts of an instant in a time zone. */
export function zonedParts(epochMs, timeZone) {
  const fmt = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  const parts = Object.fromEntries(
    fmt.formatToParts(new Date(epochMs)).map((p) => [p.type, p.value]),
  );
  return {
    year: Number(parts.year),
    month: Number(parts.month),
    day: Number(parts.day),
    hour: Number(parts.hour),
    minute: Number(parts.minute),
    second: Number(parts.second),
  };
}

function offsetMs(epochMs, timeZone) {
  const whole = Math.floor(epochMs / 1000) * 1000;
  const p = zonedParts(whole, timeZone);
  return Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second) - whole;
}

/** "YYYY-MM-DD" of an instant in a time zone. */
export function zonedDate(epochMs, timeZone) {
  const p = zonedParts(epochMs, timeZone);
  return `${p.year}-${String(p.month).padStart(2, "0")}-${String(p.day).padStart(2, "0")}`;
}

/** "HH:MM" of an instant in a time zone. */
export function zonedTime(epochMs, timeZone) {
  const p = zonedParts(epochMs, timeZone);
  return `${String(p.hour).padStart(2, "0")}:${String(p.minute).padStart(2, "0")}`;
}

export function addDays(dateStr, days) {
  const [y, m, d] = dateStr.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d) + days * DAY).toISOString().slice(0, 10);
}

/**
 * Wall-clock date and time in a time zone -> epoch ms.
 * Matches Python's zoneinfo with fold=0: a time that happens twice (clocks go back) means the
 * first one; a time that is skipped (clocks go forward) is read with the earlier offset, so it
 * lands just after the gap.
 */
export function wallTimeToEpoch(dateStr, timeStr, timeZone) {
  const [y, m, d] = dateStr.split("-").map(Number);
  const [hh, mm] = timeStr.split(":").map(Number);
  const guess = Date.UTC(y, m - 1, d, hh, mm);
  const before = guess - offsetMs(guess - 12 * HOUR, timeZone);
  const after = guess - offsetMs(guess + 12 * HOUR, timeZone);
  const matches = (epoch) => {
    const p = zonedParts(epoch, timeZone);
    return p.year === y && p.month === m && p.day === d && p.hour === hh && p.minute === mm;
  };
  const valid = [before, after].filter(matches);
  return valid.length ? Math.min(...valid) : before;
}

function hhmmToMinutes(value) {
  const [h, m] = value.split(":").map(Number);
  return h * 60 + m;
}

/** Same rule as the server's kitchen_open_for_window: [start, end] inside one opening interval. */
export function kitchenOpen(restaurant, startMs, endMs, timeZone) {
  const opens = hhmmToMinutes(restaurant.opens_at);
  const closes = hhmmToMinutes(restaurant.closes_at);
  if (opens === closes) return true;
  const startDay = zonedDate(startMs, timeZone);
  for (const day of [addDays(startDay, -1), startDay]) {
    const closeDay = closes > opens ? day : addDays(day, 1);
    const openAt = wallTimeToEpoch(day, restaurant.opens_at, timeZone);
    const closeAt = wallTimeToEpoch(closeDay, restaurant.closes_at, timeZone);
    if (openAt <= startMs && endMs <= closeAt) return true;
  }
  return false;
}

/**
 * Advice about a chosen delivery time, using the server's rules. The server still decides;
 * this only lets the page warn before the customer presses the button.
 * Returns { ok: true } or { ok: false, code } with the same codes the API uses.
 */
export function scheduleHint({ deliveryMs, nowMs, restaurant, timeZone, rules }) {
  const lead = deliveryMs - nowMs;
  if (lead < rules.min_lead_minutes * MINUTE) return { ok: false, code: "SCHEDULE_TOO_SOON" };
  if (lead > rules.max_horizon_days * DAY) return { ok: false, code: "SCHEDULE_TOO_FAR" };
  const releaseMs = deliveryMs - rules.release_before_minutes * MINUTE;
  if (!kitchenOpen(restaurant, releaseMs, deliveryMs, timeZone)) {
    return { ok: false, code: "RESTAURANT_CLOSED" };
  }
  return { ok: true };
}

/** What to tell the customer for an API error code. */
export function errorMessage(code, rules, fallback = "Something went wrong. Try again.") {
  const messages = {
    SCHEDULE_TOO_SOON: `Pick a time at least ${rules.min_lead_minutes} minutes from now.`,
    SCHEDULE_TOO_FAR: `Pick a time within the next ${rules.max_horizon_days} days.`,
    SCHEDULE_TIMEZONE_REQUIRED: "Pick a date and a time.",
    RESTAURANT_CLOSED:
      `The kitchen starts your order ${rules.release_before_minutes} minutes before delivery, ` +
      "and the restaurant has to be open for all of that time. Pick a later time, or one " +
      "earlier in the evening.",
    ORDER_NOT_CANCELLABLE: "This order has already gone to the kitchen, so it can't be cancelled.",
    ITEM_NOT_ON_MENU: "One of the items is no longer on the menu. Remove it and try again.",
    RESTAURANT_NOT_FOUND: "That restaurant is no longer available.",
    ORDER_NOT_FOUND: "That order no longer exists.",
  };
  return messages[code] ?? fallback;
}

/** Customer-facing wording for an order status. */
export function statusInfo(status) {
  const table = {
    SCHEDULED: { label: "Scheduled", tone: "waiting", final: false },
    PLACED: { label: "Sent to the kitchen", tone: "active", final: false },
    PREPARING: { label: "Being prepared", tone: "active", final: false },
    READY: { label: "Ready for the driver", tone: "active", final: false },
    PICKED_UP: { label: "On the way", tone: "active", final: false },
    DELIVERED: { label: "Delivered", tone: "done", final: true },
    CANCELLED: { label: "Cancelled", tone: "stopped", final: true },
  };
  return table[status] ?? { label: status, tone: "active", final: false };
}

export function formatTime(epochMs, timeZone) {
  return new Intl.DateTimeFormat("en-US", { timeZone, hour: "numeric", minute: "2-digit" }).format(
    new Date(epochMs),
  );
}

export function formatDay(epochMs, timeZone) {
  return new Intl.DateTimeFormat("en-US", {
    timeZone,
    weekday: "short",
    month: "short",
    day: "numeric",
  }).format(new Date(epochMs));
}

/** First quarter-hour at least `min_lead_minutes + 15` minutes away: a sensible default. */
export function suggestedDelivery(nowMs, rules, timeZone) {
  const earliest = nowMs + (rules.min_lead_minutes + 15) * MINUTE;
  const slot = Math.ceil(earliest / (15 * MINUTE)) * 15 * MINUTE;
  return { date: zonedDate(slot, timeZone), time: zonedTime(slot, timeZone) };
}

/** Every opening interval, as [openMs, closeMs], that touches the days around an instant. */
function openSpans(restaurant, aroundMs, timeZone) {
  if (restaurant.opens_at === restaurant.closes_at) return [[-Infinity, Infinity]];
  const opens = hhmmToMinutes(restaurant.opens_at);
  const closes = hhmmToMinutes(restaurant.closes_at);
  const day = zonedDate(aroundMs, timeZone);
  return [-2, -1, 0, 1].map((n) => {
    const openDay = addDays(day, n);
    const closeDay = closes > opens ? openDay : addDays(openDay, 1);
    return [
      wallTimeToEpoch(openDay, restaurant.opens_at, timeZone),
      wallTimeToEpoch(closeDay, restaurant.closes_at, timeZone),
    ];
  });
}

/**
 * Shapes for the timeline around a delivery time, as fractions (0..1) of the window
 * [centerMs - hoursEachSide, centerMs + hoursEachSide]. Zoomed in so the kitchen window is
 * easy to see. Positions use real time, so a daylight-saving night shows the repeated hour.
 */
export function timeline({ centerMs, hoursEachSide = 3, timeZone, restaurant, nowMs, rules, deliveryMs }) {
  const fromMs = centerMs - hoursEachSide * HOUR;
  const toMs = centerMs + hoursEachSide * HOUR;
  const pos = (epoch) => Math.min(1, Math.max(0, (epoch - fromMs) / (toMs - fromMs)));

  const open = openSpans(restaurant, centerMs, timeZone)
    .filter(([a, b]) => b > fromMs && a < toMs)
    .map(([a, b]) => ({ from: pos(a), to: pos(b) }));

  // Ticks on whole local hours. Every real offset is a multiple of 15 minutes.
  const ticks = [];
  const label = new Intl.DateTimeFormat("en-US", { timeZone, hour: "numeric" });
  for (let t = Math.ceil(fromMs / (15 * MINUTE)) * 15 * MINUTE; t <= toMs; t += 15 * MINUTE) {
    if (zonedParts(t, timeZone).minute === 0) ticks.push({ at: pos(t), label: label.format(new Date(t)) });
  }

  const result = {
    open,
    ticks,
    tooSoonUntil: pos(nowMs + rules.min_lead_minutes * MINUTE),
    kitchen: null,
    delivery: null,
  };
  if (deliveryMs != null) {
    result.delivery = pos(deliveryMs);
    result.kitchen = { from: pos(deliveryMs - rules.release_before_minutes * MINUTE), to: result.delivery };
  }
  return result;
}

/** "18:00" -> "6:00 PM" (a clock reading, not an instant). */
export function formatClock(hhmm) {
  const [h, m] = hhmm.split(":").map(Number);
  const suffix = h < 12 ? "AM" : "PM";
  const hour12 = h % 12 === 0 ? 12 : h % 12;
  return `${hour12}:${String(m).padStart(2, "0")} ${suffix}`;
}

export function formatHours(opensAt, closesAt) {
  if (opensAt === closesAt) return "Open 24 hours";
  return `${formatClock(opensAt)} – ${formatClock(closesAt)}`;
}

/** "America/New_York" -> "New York". */
export function cityName(timeZone) {
  return timeZone.split("/").pop().replaceAll("_", " ");
}
