// MiniDash customer page: DOM and API calls. Pure logic lives in logic.js (tested in Node).
// Server data is always placed with textContent, never innerHTML.

import {
  cityName,
  errorMessage,
  formatDay,
  formatHours,
  formatMoney,
  formatTime,
  kitchenOpen,
  scheduleHint,
  statusInfo,
  suggestedDelivery,
  timeline,
  wallTimeToEpoch,
  zonedDate,
} from "./logic.js";

const POLL_MS = 3000;
const STORE_KEY = "minidash.orders";
const MINUTE = 60_000;

const state = {
  config: null,
  clockOffset: 0, // server time minus browser time, from GET /config
  restaurants: [],
  selected: null,
  menu: [],
  cart: new Map(), // menu item id -> { item, quantity }
  mode: "now",
  orderIds: [],
  orders: new Map(), // order id -> latest order from the API
  orderErrors: new Map(),
  newestId: null,
  pollTimer: null,
};

const $ = (id) => document.getElementById(id);

/** Create an element; strings become text nodes, so nothing is parsed as HTML. */
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (value !== false && value != null) node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child != null && child !== false) node.append(child);
  }
  return node;
}

class ApiError extends Error {
  constructor(message, code, status) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "content-type": "application/json", ...(options.headers ?? {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = body?.error ?? {};
    const detail = Array.isArray(body?.detail) ? body.detail[0]?.msg : null;
    throw new ApiError(error.message ?? detail ?? `Request failed (${response.status})`, error.code, response.status);
  }
  return body;
}

// The page's sense of "now" is the server's clock, so hints agree with the server.
const nowMs = () => Date.now() + state.clockOffset;
const tz = () => state.config.business_timezone;

// ---- Remembering orders placed from this browser -------------------------------------------

function loadOrderIds() {
  try {
    const ids = JSON.parse(localStorage.getItem(STORE_KEY) ?? "[]");
    return Array.isArray(ids) ? ids.filter(Number.isInteger) : [];
  } catch {
    return []; // storage blocked or corrupt: start empty for this visit
  }
}

function saveOrderIds() {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(state.orderIds));
  } catch {
    // Storage blocked: the list still works in memory until the page is closed.
  }
}

// ---- Restaurants and menu ------------------------------------------------------------------

function renderRestaurants() {
  const list = $("restaurant-list");
  list.replaceChildren(
    ...state.restaurants.map((r) => {
      const open = kitchenOpen(r, nowMs(), nowMs(), tz());
      return el(
        "li",
        {},
        el(
          "button",
          {
            class: "restaurant",
            type: "button",
            "aria-pressed": String(state.selected?.id === r.id),
            onclick: () => selectRestaurant(r),
          },
          el("span", { class: "restaurant-name" }, r.name),
          el("span", { class: "restaurant-meta" }, `${r.cuisine}, ${formatHours(r.opens_at, r.closes_at)}`),
          el(
            "span",
            { class: `restaurant-meta ${open ? "open-now" : "closed-now"}` },
            open ? "Open now" : "Closed now",
          ),
        ),
      );
    }),
  );
}

async function selectRestaurant(restaurant) {
  if (state.selected?.id !== restaurant.id) state.cart.clear();
  state.selected = restaurant;
  $("menu-heading").textContent = `${restaurant.name} menu`;
  $("menu-empty").textContent = "Loading the menu…";
  $("menu-list").replaceChildren();
  renderRestaurants();
  renderCart();
  renderSchedule();
  try {
    state.menu = await api(`/restaurants/${restaurant.id}/menu`);
    $("menu-empty").textContent = state.menu.length ? "" : "This restaurant has no dishes yet.";
    renderMenu();
  } catch (error) {
    $("menu-empty").textContent = errorMessage(error.code, state.config, error.message);
  }
}

function renderMenu() {
  $("menu-list").replaceChildren(
    ...state.menu.map((item) => {
      const quantity = state.cart.get(item.id)?.quantity ?? 0;
      return el(
        "li",
        { class: "menu-item" },
        el("span", { class: "menu-item-name" }, item.name),
        el("span", { class: "price num" }, formatMoney(item.price_cents)),
        el(
          "span",
          { class: "stepper" },
          el(
            "button",
            {
              type: "button",
              "aria-label": `Remove one ${item.name}`,
              disabled: quantity === 0,
              onclick: () => changeQuantity(item, -1),
            },
            "−",
          ),
          el("output", { class: "num", "aria-label": `${item.name} quantity` }, String(quantity)),
          el(
            "button",
            { type: "button", "aria-label": `Add one ${item.name}`, onclick: () => changeQuantity(item, 1) },
            "+",
          ),
        ),
      );
    }),
  );
}

function changeQuantity(item, delta) {
  const quantity = Math.max(0, Math.min(50, (state.cart.get(item.id)?.quantity ?? 0) + delta));
  if (quantity === 0) state.cart.delete(item.id);
  else state.cart.set(item.id, { item, quantity });
  renderMenu();
  renderCart();
}

function renderCart() {
  const lines = [...state.cart.values()];
  $("cart-empty").hidden = lines.length > 0;
  $("cart").replaceChildren(
    ...lines.map(({ item, quantity }) =>
      el(
        "li",
        {},
        el("span", {}, `${quantity} × ${item.name}`),
        el("span", { class: "num" }, formatMoney(quantity * item.price_cents)),
      ),
    ),
  );
  const total = lines.reduce((sum, { item, quantity }) => sum + quantity * item.price_cents, 0);
  const totalNode = $("cart-total");
  totalNode.hidden = lines.length === 0;
  totalNode.replaceChildren(el("span", {}, "Total"), el("span", { class: "num" }, formatMoney(total)));
}

// ---- Scheduling ----------------------------------------------------------------------------

function chosenDeliveryMs() {
  const date = $("schedule-date").value;
  const time = $("schedule-time").value;
  if (!date || !time) return null;
  return wallTimeToEpoch(date, time, tz());
}

function renderSchedule() {
  const later = state.mode === "later";
  $("schedule-fields").hidden = !later;
  const deliveryMs = later ? chosenDeliveryMs() : null;
  $("place").textContent =
    later && deliveryMs != null ? `Schedule for ${formatTime(deliveryMs, tz())}` : "Place order";
  if (!later) return;

  const restaurant = state.selected;
  const hint = $("hint");
  hint.classList.remove("warn");
  if (!restaurant) {
    $("timeline").replaceChildren();
    $("timeline").setAttribute("aria-label", "Choose a restaurant to see its hours.");
    hint.textContent = "Choose a restaurant to see when it can deliver.";
    return;
  }
  renderTimeline(restaurant, deliveryMs);
  if (deliveryMs == null) {
    hint.textContent = "Pick a date and a time.";
    return;
  }
  const result = scheduleHint({ deliveryMs, nowMs: nowMs(), restaurant, timeZone: tz(), rules: state.config });
  if (result.ok) {
    const releaseMs = deliveryMs - state.config.release_before_minutes * MINUTE;
    hint.textContent = `${restaurant.name} starts your order at ${formatTime(releaseMs, tz())}.`;
  } else {
    hint.textContent = errorMessage(result.code, state.config);
    hint.classList.add("warn");
  }
}

function renderTimeline(restaurant, deliveryMs) {
  const centerMs = deliveryMs ?? nowMs() + state.config.min_lead_minutes * MINUTE;
  const shape = timeline({ centerMs, timeZone: tz(), restaurant, nowMs: nowMs(), rules: state.config, deliveryMs });
  const pct = (x) => `${(x * 100).toFixed(3)}%`;
  const box = (cls, from, to) => {
    const node = el("div", { class: cls });
    node.style.left = pct(from);
    node.style.width = pct(Math.max(0, to - from));
    return node;
  };
  const parts = shape.open.map(({ from, to }) => box("tl-open", from, to));
  if (shape.tooSoonUntil > 0) parts.push(box("tl-soon", 0, shape.tooSoonUntil));
  if (shape.kitchen) parts.push(box("tl-kitchen", shape.kitchen.from, shape.kitchen.to));
  if (shape.delivery != null) {
    const marker = el("div", { class: "tl-delivery" });
    marker.style.left = pct(shape.delivery);
    parts.push(marker);
  }
  for (const { at, label } of shape.ticks) {
    const tick = el("span", { class: "tl-tick" }, label);
    tick.style.left = pct(at);
    parts.push(tick);
  }
  $("timeline").replaceChildren(...parts);

  let label = `${restaurant.name} is open ${formatHours(restaurant.opens_at, restaurant.closes_at)}.`;
  if (deliveryMs != null) {
    const releaseMs = deliveryMs - state.config.release_before_minutes * MINUTE;
    label += ` The kitchen has your order from ${formatTime(releaseMs, tz())} to ${formatTime(deliveryMs, tz())}.`;
  }
  $("timeline").setAttribute("aria-label", label);
}

function setMode(mode) {
  state.mode = mode;
  if (mode === "later" && !$("schedule-date").value) {
    const suggestion = suggestedDelivery(nowMs(), state.config, tz());
    $("schedule-date").value = suggestion.date;
    $("schedule-time").value = suggestion.time;
  }
  renderSchedule();
}

function setDateLimits() {
  const today = zonedDate(nowMs(), tz());
  const last = zonedDate(nowMs() + state.config.max_horizon_days * 24 * 60 * MINUTE, tz());
  $("schedule-date").min = today;
  $("schedule-date").max = last;
  $("zone-note").textContent = `${cityName(tz())} time, when the restaurants are.`;
}

// ---- Placing an order ----------------------------------------------------------------------

async function placeOrder() {
  const formError = $("form-error");
  formError.textContent = "";
  if (!state.selected) return void (formError.textContent = "Choose a restaurant first.");
  if (state.cart.size === 0) return void (formError.textContent = "Add at least one dish.");
  const address = $("address").value.trim();
  if (!address) return void (formError.textContent = "Enter a delivery address.");

  const body = {
    restaurant_id: state.selected.id,
    items: [...state.cart.values()].map(({ item, quantity }) => ({ menu_item_id: item.id, quantity })),
    address,
  };
  if (state.mode === "later") {
    const deliveryMs = chosenDeliveryMs();
    if (deliveryMs == null) return void (formError.textContent = "Pick a date and a time.");
    body.scheduled_for = new Date(deliveryMs).toISOString();
  }

  const button = $("place");
  button.disabled = true;
  try {
    const order = await api("/orders", { method: "POST", body: JSON.stringify(body) });
    state.orderIds = [order.id, ...state.orderIds.filter((id) => id !== order.id)];
    state.orders.set(order.id, order);
    state.newestId = order.id;
    saveOrderIds();
    state.cart.clear();
    renderMenu();
    renderCart();
    renderOrders();
    schedulePoll();
  } catch (error) {
    formError.textContent = errorMessage(error.code, state.config, error.message);
  } finally {
    button.disabled = false;
  }
}

// ---- Tracking orders -----------------------------------------------------------------------

function restaurantName(id) {
  return state.restaurants.find((r) => r.id === id)?.name ?? `Restaurant ${id}`;
}

function orderDetails(order) {
  const zone = tz();
  const at = (iso) => Date.parse(iso);
  const lines = [];
  if (order.scheduled_for) {
    lines.push(`Delivery ${formatDay(at(order.scheduled_for), zone)}, ${formatTime(at(order.scheduled_for), zone)}`);
    if (order.released_at) lines.push(`Went to the kitchen at ${formatTime(at(order.released_at), zone)}`);
    else if (order.status === "CANCELLED") lines.push("Cancelled before it went to the kitchen");
    else lines.push(`Goes to the kitchen at ${formatTime(at(order.release_at), zone)}`);
  } else {
    lines.push(`Placed ${formatDay(at(order.created_at), zone)}, ${formatTime(at(order.created_at), zone)}`);
  }
  return lines;
}

function renderOrders() {
  const known = state.orderIds.filter((id) => state.orders.has(id));
  $("tracker-empty").hidden = known.length > 0;
  $("orders").replaceChildren(
    ...known.map((id) => {
      const order = state.orders.get(id);
      const info = statusInfo(order.status);
      const items = order.items.map((i) => `${i.quantity} × ${i.name}`).join(", ");
      const error = state.orderErrors.get(id);
      return el(
        "li",
        { class: `order${id === state.newestId ? " is-new" : ""}`, "data-order-id": String(id) },
        el(
          "div",
          { class: "order-head" },
          el("span", { class: "order-title" }, `Order ${id}, ${restaurantName(order.restaurant_id)}`),
          el("span", { class: `status status-${info.tone}` }, info.label),
        ),
        ...orderDetails(order).map((line) => el("p", { class: "detail" }, line)),
        el("p", { class: "detail" }, `${items}. ${formatMoney(order.total_cents)}`),
        order.status === "SCHEDULED"
          ? el("button", { class: "secondary", type: "button", onclick: () => cancelOrder(id) }, "Cancel order")
          : null,
        error ? el("p", { class: "error" }, error) : null,
      );
    }),
  );
  state.newestId = null;
}

async function refreshOrders() {
  const open = state.orderIds.filter((id) => !statusInfo(state.orders.get(id)?.status ?? "").final);
  await Promise.all(
    open.map(async (id) => {
      try {
        state.orders.set(id, await api(`/orders/${id}`));
      } catch (error) {
        if (error.status === 404) {
          state.orderIds = state.orderIds.filter((x) => x !== id);
          saveOrderIds();
        }
      }
    }),
  );
  renderOrders();
}

function schedulePoll() {
  clearTimeout(state.pollTimer);
  const waiting = state.orderIds.some((id) => !statusInfo(state.orders.get(id)?.status ?? "").final);
  if (!waiting) return;
  state.pollTimer = setTimeout(async () => {
    await refreshOrders();
    schedulePoll();
  }, POLL_MS);
}

async function cancelOrder(id) {
  state.orderErrors.delete(id);
  try {
    state.orders.set(id, await api(`/orders/${id}/cancel`, { method: "POST" }));
  } catch (error) {
    state.orderErrors.set(id, errorMessage(error.code, state.config, error.message));
    try {
      state.orders.set(id, await api(`/orders/${id}`));
    } catch {
      // keep the last known state; the next poll will try again
    }
  }
  renderOrders();
  schedulePoll();
}

// ---- Start ---------------------------------------------------------------------------------

async function start() {
  try {
    state.config = await api("/config");
    state.clockOffset = Date.parse(state.config.now) - Date.now();
    state.restaurants = await api("/restaurants");
  } catch (error) {
    $("form-error").textContent = `MiniDash could not load (${error.message}). Reload the page to try again.`;
    return;
  }
  setDateLimits();
  renderRestaurants();
  renderCart();

  for (const radio of document.querySelectorAll('input[name="when"]')) {
    radio.addEventListener("change", () => setMode(radio.value));
  }
  $("schedule-date").addEventListener("input", renderSchedule);
  $("schedule-time").addEventListener("input", renderSchedule);
  $("place").addEventListener("click", placeOrder);

  state.orderIds = loadOrderIds();
  await refreshOrders();
  schedulePoll();
  setInterval(() => {
    renderRestaurants();
    if (state.mode === "later") renderSchedule();
  }, MINUTE);
  document.body.dataset.ready = "true";
}

start();
