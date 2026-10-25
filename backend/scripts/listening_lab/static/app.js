const $ = (id) => document.getElementById(id);
const names = { u1: "You", u2: "Maya", u3: "Alex", u4: "Sam" };
let activeUser = "u1";
let state = null;
let polling = false;
let lastMessageId = null;
let wasPollOpen = false;
let splitDraft = "";

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}
function user(id) { return state?.users.find((person) => person.id === id); }
function displayName(id) { return id === activeUser ? "You" : (user(id)?.name === "You" ? "Jordan" : user(id)?.name) ?? "Member"; }
function avatar(id, extra = "") {
  const person = user(id);
  return `<span class="avatar ${extra}" style="background:${escapeHtml(person?.color ?? "#7968e9")}">${escapeHtml((person?.name === "You" ? "J" : person?.name?.[0]) ?? "?")}</span>`;
}
function sourceFor(field, userId = null) {
  const id = state?.template?.sources?.[`${field}:${userId ?? "group"}`];
  if (id === "predicted") return `<span class="field-source predicted">✦ Predicted by Muse from the chat and notes</span>`;
  const source = state?.messages.find((message) => message.id === id);
  return source ? `<span class="field-source">From ${escapeHtml(displayName(source.user_id))}'s message</span>` : "";
}
function field(label, value, source = "", own = false) {
  const empty = value === null || value === undefined || value === "" || (Array.isArray(value) && value.length === 0);
  const shown = empty ? "Waiting for chat…" : Array.isArray(value) ? value.join(", ") : value;
  return `<div class="field"><span class="field-label">${escapeHtml(label)}</span><span class="field-value ${empty ? "missing" : ""} ${own ? "own" : ""}">${escapeHtml(shown)}${source}</span></div>`;
}

function renderUsers() {
  $("user-switcher").innerHTML = (state?.users ?? []).map((person) =>
    `<button class="user-chip ${activeUser === person.id ? "selected" : ""}" data-user="${person.id}" type="button">${avatar(person.id)}<span>${escapeHtml(activeUser === person.id ? "You" : person.name === "You" ? "Jordan" : person.name)}</span></button>`
  ).join("");
  $("user-switcher").querySelectorAll("[data-user]").forEach((button) => button.addEventListener("click", () => {
    activeUser = button.dataset.user;
    render();
  }));
  const person = user(activeUser);
  $("composer-avatar").textContent = person?.name === "You" ? "J" : person?.name?.[0] ?? "?";
  $("composer-avatar").style.background = person?.color ?? "#7968e9";
}

function categoryName(t) { return t?.topic === "Custom" ? (t.custom_label || "Custom") : (t?.topic ?? ""); }
function photoStyle(image) { return image?.url ? `style="background-image:url('${escapeHtml(image.url)}')"` : ""; }

function planSummary() {
  const t = state.template, w = t.where;
  const place = w.destination ? w.destination.name : w.search_area ? `Around ${w.search_area}` : "—";
  const agreed = t.when.agreed ? `${t.when.agreed.label}${t.when.agreed.date ? ` (${t.when.agreed.date})` : ""}` : "";
  const times = agreed || state.users.map((p) => {
    const v = t.when.flexibility[p.id];
    return `${displayName(p.id)}: ${v === null ? "flexible" : v?.map((x) => x.label).join(", ") ?? "—"}`;
  }).join(" · ");
  const bits = Object.entries(t.cluster).filter(([, v]) => v && (!Array.isArray(v) || v.length)).map(([k, v]) => `${k.replace("_", " ")}: ${Array.isArray(v) ? v.join(", ") : v}`);
  return `<b>${escapeHtml(t.title)}</b><br>${escapeHtml(place)}<br>${escapeHtml(times)}${bits.length ? `<br>${escapeHtml(bits.join(" · "))}` : ""}`;
}
function pollCard() {
  const poll = state?.poll;
  if (!state?.template || (!poll.open && !state.confirmed)) return "";
  const chips = state.users.map((p) => {
    const v = poll.votes[p.id], out = state.attendance?.[p.id]?.status === "not_going";
    return `<span class="vote-chip ${out ? "out" : v === true ? "yes" : v === false ? "no" : ""}">${avatar(p.id)}${escapeHtml(displayName(p.id))} ${out ? "not going" : v === true ? "✓" : v === false ? "✗" : "…"}</span>`;
  }).join("");
  const mine = poll.votes[activeUser];
  const canVote = poll.voters?.includes(activeUser) ?? true;
  if (state.confirmed) return `<div class="poll-card done"><strong>✓ Plan confirmed</strong><p>${planSummary()}</p><div class="vote-row">${chips}</div>${payCard()}</div>`;
  return `<div class="poll-card"><strong>Ready — does everyone agree?</strong><p>${planSummary()}</p><div class="vote-row">${chips}</div>
    ${canVote ? `<div class="poll-actions"><button type="button" data-vote="yes" class="${mine === true ? "picked" : ""}">Yes, I'm in</button><button type="button" data-vote="no" class="no ${mine === false ? "picked" : ""}">No, change it</button></div>` : `<p class="small">${escapeHtml(displayName(activeUser))} said they can't go, so they don't vote. If that changes, say so in the chat.</p>`}
    <div class="poll-foot"><span>${poll.yes} of ${poll.needed} yes needed (${poll.total} attending) · Muse keeps listening; any change to the plan resets the votes</span>
    <label>Needs <select id="threshold">${[0.4, 0.5, 0.6].map((v) => `<option value="${v}" ${v === poll.threshold ? "selected" : ""}>${v * 100}%</option>`).join("")}</select></label></div></div>`;
}

// ---- Paying for the confirmed plan: real transfers through Capital One Nessie (sandbox) ----
const money = (cents) => `$${(cents / 100).toFixed(2)}`;
function payCard() {
  if (!state.nessie_configured) return `<p class="small pay-note">Add NESSIE_API_KEY to backend/.env to collect payments with Capital One Nessie.</p>`;
  const payee = state.template.initiator, s = state.split;
  if (!s) {
    return activeUser === payee
      ? `<div class="pay-box"><strong>Collect everyone's share</strong><div class="pay-entry"><span>$</span><input id="split-total" type="number" min="1" step="0.01" inputmode="decimal" placeholder="Total cost" value="${escapeHtml(splitDraft)}"><button type="button" id="split-button">Split with the group</button></div><p class="small">Split evenly with everyone who voted yes. Shares are paid to ${escapeHtml(displayName(payee))} through Capital One Nessie.</p></div>`
      : `<div class="pay-box"><p class="small">Waiting for ${escapeHtml(displayName(payee))} to add the total cost.</p></div>`;
  }
  const owed = Object.entries(s.shares);
  if (!owed.length) return `<div class="pay-box"><p class="small">Nobody else voted yes, so there's nothing to split.</p></div>`;
  const rows = owed.map(([uid, cents]) => {
    const paid = s.paid[uid];
    const action = paid ? `<span class="paid">Paid ✓ <small>Nessie #${escapeHtml(String(paid.id).slice(-6))} · ${escapeHtml(paid.status)}</small></span>`
      : uid === activeUser ? `<button type="button" data-pay="${uid}">Pay ${money(cents)}</button>` : `<span class="unpaid">Not paid yet</span>`;
    return `<div class="pay-row">${avatar(uid)}<span class="pay-name">${escapeHtml(displayName(uid))}</span><b>${money(cents)}</b>${action}</div>`;
  }).join("");
  return `<div class="pay-box"><strong>${money(s.total_cents)} total · paid to ${escapeHtml(displayName(payee))}</strong><div class="pay-rows">${rows}</div><div class="poll-foot"><span>${Object.keys(s.paid).length} of ${owed.length} paid · Capital One Nessie</span><span id="my-balance"></span></div></div>`;
}
async function loadBalance() {
  const el = $("my-balance");
  if (!el) return;
  try {
    const payload = await (await fetch(`/api/balance?user_id=${activeUser}`, { cache: "no-store" })).json();
    if (payload.balance !== undefined && $("my-balance") === el) el.textContent = `Your balance: $${Number(payload.balance).toFixed(2)}`;
  } catch { /* balance is a nice-to-have */ }
}

function renderMessages() {
  const messages = state?.messages ?? [];
  $("chat-count").textContent = `${messages.length} message${messages.length === 1 ? "" : "s"}`;
  const hadNewMessage = messages.at(-1)?.id !== lastMessageId;
  lastMessageId = messages.at(-1)?.id ?? null;
  const t = state?.template;
  const started = t ? `<div class="planner-card"><span class="planner-photo" ${photoStyle(t.category_image)} title="${escapeHtml(t.category_image?.source ?? "")}"></span><div><strong>${escapeHtml(t.title)}</strong><small>${escapeHtml(displayName(t.initiator))} started a ${escapeHtml(categoryName(t))} planner · Muse is listening</small></div></div>` : "";
  $("messages").innerHTML = started + (messages.length ? messages.map((message) => {
    const mine = message.user_id === activeUser;
    return `<div class="message-row ${mine ? "mine" : ""}">${mine ? "" : avatar(message.user_id)}<div class="message-body"><div class="message-meta">${escapeHtml(displayName(message.user_id))} · ${escapeHtml(new Date(message.sent_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }))}</div><div class="bubble">${escapeHtml(message.text)}</div><div class="message-status">${escapeHtml(message.status === "listening" ? "Muse listening…" : message.status === "queued" ? "Queued" : message.status === "error" ? "Extraction failed" : "Processed")}</div></div></div>`;
  }).join("") : t ? "" : `<div class="empty-chat"><span>✦</span><h2>Start a plan to begin</h2><p>Tap + below and choose Planner.</p></div>`);
  if (messages.length) $("messages").insertAdjacentHTML("beforeend", pollCard());
  if (state?.split && state.nessie_configured) loadBalance();
  const pollOpen = Boolean(state?.poll?.open);
  if (hadNewMessage || (pollOpen && !wasPollOpen)) $("messages").scrollTop = $("messages").scrollHeight;
  wasPollOpen = pollOpen;
  $("message-input").disabled = !state?.template || state.confirmed;
  $("send-button").disabled = !state?.template || state.confirmed;
  $("message-input").placeholder = state?.confirmed ? "Plan confirmed" : state?.template ? `Message as ${displayName(activeUser)}…` : "Start a plan with + to chat…";
}

function renderReadiness() {
  if (!state?.template) {
    $("readiness").innerHTML = `<div class="readiness"><strong>No active session</strong><p style="margin-top:8px">Tap + in the chat and choose Planner to start listening.</p></div>`;
    return;
  }
  const required = 2; // a settled time + a location
  if (state.template && !state.messages.length) seenValues = {};
  const done = Math.max(0, required - state.missing.length);
  const status = state.confirmed ? "Confirmed" : state.processing ? "Muse is listening" : state.queued ? `${state.queued} queued` : state.error ? "Needs retry" : state.ready ? "Ready — vote in chat" : `${state.missing.length} required items missing`;
  const text = state.confirmed ? "The group template is locked for this simulation." : state.ready ? "All required fields are present. Vote in the chat to confirm." : state.missing.length ? `Still needed: ${state.missing.join(" · ")}` : "Waiting for Muse to finish this batch.";
  $("readiness").innerHTML = `<div class="readiness ${state.confirmed ? "confirmed" : ""}"><div class="readiness-top"><strong>${escapeHtml(status)}</strong><span class="small">${done} / ${required} required</span></div><div class="progress"><span style="width:${Math.round(100 * done / required)}%"></span></div><p>${escapeHtml(text)}</p></div>`;
}

let seenValues = {};
function row(key, type, req, value, src = "") {
  const filled = value !== null && value !== undefined && value !== "" && !(Array.isArray(value) && !value.length);
  const text = filled ? (Array.isArray(value) ? value.join(", ") : value) : "—";
  const sig = JSON.stringify(value), changed = filled && key in seenValues && seenValues[key] !== sig;
  seenValues[key] = sig;
  const cls = req === "Required" && !filled ? "need" : "";
  return `<div class="tpl-row ${filled ? "filled" : ""} ${changed ? "flash" : ""} ${cls}"><div class="tpl-head"><code>${escapeHtml(key)}</code><span class="tpl-req ${req.split(":")[0].toLowerCase()}">${escapeHtml(req)}</span></div><div class="tpl-type">${escapeHtml(type)}</div><div class="tpl-val ${filled ? "" : "empty"}">${escapeHtml(text)}</div>${src}</div>`;
}
function perUser(key, type, req, map, fmt) {
  const t = state.template;
  const items = state.users.map((p) => {
    const has = Object.hasOwn(map, p.id);
    const v = has ? fmt(map[p.id]) : null;
    const sig = JSON.stringify(v), k = key + p.id, changed = has && k in seenValues && seenValues[k] !== sig;
    seenValues[k] = sig;
    return `<div class="tpl-user ${has ? "filled" : ""} ${changed ? "flash" : ""} ${activeUser === p.id ? "own" : ""}">${avatar(p.id)}<b>${escapeHtml(displayName(p.id))}</b><span class="${has ? "" : "empty"}">${escapeHtml(has ? v : "—")}</span>${has ? sourceFor(key, p.id) : ""}</div>`;
  }).join("");
  const done = state.users.filter((p) => Object.hasOwn(map, p.id)).length;
  return `<div class="tpl-row ${req === "Required" && done < state.users.length ? "need" : ""}"><div class="tpl-head"><code>${escapeHtml(key)}</code><span class="tpl-req ${req.split(":")[0].toLowerCase()}">${escapeHtml(req)}</span><span class="small">${done}/${state.users.length}</span></div><div class="tpl-type">${escapeHtml(type)}</div>${items}</div>`;
}
function attendanceRow() {
  const label = { going: "Going", not_going: "Not going", conditional: "Conditional" };
  const items = state.users.map((p) => {
    const a = state.attendance?.[p.id] ?? { status: "conditional", condition: "hasn't responded yet", inferred: true };
    const text = `${label[a.status]}${a.condition ? ` · ${a.condition}` : ""}${a.inferred && a.status === "going" ? " (from chat)" : ""}`;
    return `<div class="tpl-user att-${a.status} ${activeUser === p.id ? "own" : ""}">${avatar(p.id)}<b>${escapeHtml(displayName(p.id))}</b><span>${escapeHtml(text)}</span></div>`;
  }).join("");
  return `<div class="tpl-row"><div class="tpl-head"><code>attendance</code><span class="tpl-req optional">Optional</span></div><div class="tpl-type">Dict[User, going | not_going | conditional]. Members not heard from yet count as conditional.</div>${items}</div>`;
}
function pickerHtml(target) {
  return `<div class="picker"><input class="place-input" data-target="${target}" placeholder="Search Google Maps…" autocomplete="off"><div class="place-results"></div></div>`;
}
function destinationRow(w) {
  const d = w.destination;
  const body = d
    ? `<div class="tpl-val"><a href="https://www.google.com/maps/place/?q=place_id:${encodeURIComponent(d.place_id)}" target="_blank" rel="noreferrer">${escapeHtml(d.name)}</a><div class="tpl-type">${escapeHtml(d.address)} · ${d.lat.toFixed(4)}, ${d.lng.toFixed(4)}</div></div>`
    : `<div class="tpl-val empty">${w.destination_hint ? `Muse heard "<b>${escapeHtml(w.destination_hint)}</b>" <button type="button" class="hint-btn" data-hint="${escapeHtml(w.destination_hint)}">Find on Google Maps</button>` : "Pick the exact place on Google Maps"}</div>`;
  return `<div class="tpl-row ${d ? "filled" : ""}"><div class="tpl-head"><code>where.destination</code><span class="tpl-req conditional">Conditional: fixed location</span></div><div class="tpl-type">Google Maps place (exact)</div>${body}${pickerHtml("destination")}</div>`;
}
function originsRow(w) {
  const items = state.users.map((p) => {
    const o = w.origins[p.id];
    const action = activeUser === p.id ? `<button type="button" class="hint-btn" data-geo="${p.id}">📍 ${o ? "Update" : "Use my location"}</button>` : "";
    return `<div class="tpl-user ${o ? "filled" : ""} ${activeUser === p.id ? "own" : ""}">${avatar(p.id)}<b>${escapeHtml(displayName(p.id))}</b><span class="${o ? "" : "empty"}">${escapeHtml(o ? o.label : "—")}</span>${action}</div>`;
  }).join("");
  return `<div class="tpl-row"><div class="tpl-head"><code>where.origins</code><span class="tpl-req optional">Optional</span></div><div class="tpl-type">Dict[User, Location | Null] · from device geolocation, not chat</div>${items}</div>`;
}
function renderTemplate() {
  const t = state?.template;
  $("topic-badge").textContent = t ? categoryName(t) : "No category";
  if (!t) { $("universal").innerHTML = ""; $("cluster").innerHTML = ""; seenValues = {}; return; }
  const w = t.where, c = t.cluster;
  $("universal").innerHTML = `<h3 class="section-heading">1. UNIVERSAL FIELDS</h3>`
    + row("title", "String", "Required: set by initiator", t.title)
    + attendanceRow()
    + row("when.agreed", "TimeWindow the group settled on", "Required: agreed time, or everyone's availability", t.when.agreed ? `${t.when.agreed.label}${t.when.agreed.date ? ` · ${t.when.agreed.date}` : ""}` : null, sourceFor("when.agreed"))
    + perUser("when.flexibility", "Dict[User, List[TimeWindow] | Null]", "Optional", t.when.flexibility, (v) => v === null ? "Flexible" : v.map((x) => x.label).join(", "))
    + destinationRow(w)
    + row("where.search_area", "City or surrounding area", "Conditional: flexible search", w.search_area, sourceFor("where.search_area"))
    + originsRow(w)
    + perUser("budget", "Dict[User, Number | Null]", "Optional", t.budget, (v) => v === null ? "No limit" : `$${v}`)
    + perUser("preferences", "Dict[User, List[String]]", "Optional", t.preferences, (v) => v.join(", ") || "—")
    + perUser("hard_constraints", "Dict[User, List[String]]", "Optional: must be respected", t.hard_constraints, (v) => v.join(", ") || "—")
    ;
  const rows = t.topic === "Dining" ? row("meal_type", "breakfast | lunch | dinner | snack | brunch | coffee", "Optional", c.meal_type, sourceFor("meal_type")) + row("cuisine", "List[String]", "Optional", c.cuisine, sourceFor("cuisine"))
    : t.topic === "Travel" ? row("trip_type", "flight | bus | train | …", "Optional", c.trip_type, sourceFor("trip_type")) + row("accommodation", "hotel | Airbnb | hostel | none", "Optional", c.accommodation, sourceFor("accommodation"))
    : t.topic === "Custom" ? row("event_type", "Short description of this custom event", "Optional", c.event_type, sourceFor("event_type"))
    : row("activity_type", "movie | bowling | shopping | concert | …", "Optional", c.activity_type, sourceFor("activity_type"));
  $("cluster").innerHTML = `<h3 class="section-heading">2. CLUSTER · ${escapeHtml(categoryName(t).toUpperCase())}</h3>${t.category_image ? `<div class="cluster-photo" ${photoStyle(t.category_image)}><span>${escapeHtml(t.category_image.source || "")}</span></div>` : ""}${rows}`;
}

function renderSummary() {
  const t = state?.template;
  $("session-summary").innerHTML = t ? `<strong>${escapeHtml(t.title)}</strong><small>Started by ${escapeHtml(displayName(t.initiator))}</small><small>${escapeHtml(categoryName(t))}${t.where.destination || t.where.search_area ? " · " + escapeHtml(t.where.destination || t.where.search_area) : ""}</small>` : "<small>No active plan</small>";
}

function renderNotes() {
  if (!state?.template) { $("notes").innerHTML = ""; return; }
  $("notes").innerHTML = `<h3 class="section-heading">MUSE NOTES · VAULT (.md)</h3><pre class="notes">${escapeHtml(state.notes || "(empty — Muse hasn't taken notes yet)")}</pre>`;
}

function renderDebug() {
  if (!state) return;
  const m = state.metrics;
  const metric = (label, value) => `<span class="metric"><b>${escapeHtml(value)}</b> ${escapeHtml(label)}</span>`;
  const decisions = state.decisions.slice(-5).reverse().map((decision) => `<div class="decision ${decision.accepted ? "accepted" : "rejected"}">${escapeHtml(decision.accepted ? `${decision.field} updated` : `${decision.field ?? "Update"}: ${decision.reason}`)}</div>`).join("");
  $("debug").innerHTML = `<div class="debug-card"><h3 class="section-heading" style="margin-top:0">MUSE DEBUG</h3><div class="metric-row">${metric("calls", m.calls)}${metric("batches", m.batches)}${metric("messages", m.messages_processed)}${metric("input tokens", m.prompt_tokens)}${metric("output tokens", m.completion_tokens)}${metric("reasoning tokens", m.reasoning_tokens)}${metric("last ms", m.last_latency_ms ?? "—")}</div>${state.error ? `<div class="error-box">${escapeHtml(state.error)}</div><button id="retry" type="button" class="retry-button">Retry failed batch</button>` : ""}${decisions ? `<h3 class="section-heading">RECENT DECISIONS</h3>${decisions}` : ""}</div>`;
  $("retry")?.addEventListener("click", async () => { try { renderState(await post("/api/retry", {})); } catch (error) { showError(error.message); } });
}

function render() {
  if (!state) return;
  $("model-pill").textContent = state.muse_configured ? "● Muse Spark 1.3 connected" : "○ Muse key missing";
  $("model-pill").classList.toggle("off", !state.muse_configured);
  renderUsers(); if (document.activeElement?.id !== "split-total") renderMessages(); renderReadiness(); if (!document.activeElement?.classList?.contains("place-input")) renderTemplate();
  renderNotes(); renderSummary(); renderDebug();
}
function renderState(next) { state = next; render(); }
function showError(message) { $("chat-error").textContent = message; }
async function post(path, data) {
  const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}
async function poll() {
  if (polling) return;
  polling = true;
  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    const next = await response.json();
    if (JSON.stringify(next) !== JSON.stringify(state)) renderState(next);
  }
  catch (error) { showError(`Dashboard server unavailable: ${error.message}`); }
  finally { polling = false; }
}
const closeMenu = () => { $("plus-menu").hidden = true; };
const openModal = () => { closeMenu(); $("start-modal").hidden = false; $("title").focus(); };
const closeModal = () => { $("start-modal").hidden = true; };
$("plus-button").addEventListener("click", (event) => { event.stopPropagation(); $("plus-menu").hidden = !$("plus-menu").hidden; });
document.addEventListener("click", (event) => { if (!event.target.closest(".plus-wrap")) closeMenu(); });
$("open-planner").addEventListener("click", openModal);
$("modal-close").addEventListener("click", closeModal);
$("modal-cancel").addEventListener("click", closeModal);
$("start-modal").addEventListener("click", (event) => { if (event.target === $("start-modal")) closeModal(); });
$("session-form").addEventListener("submit", async (event) => {
  event.preventDefault(); showError("");
  try {
    renderState(await post("/api/session", { title: $("title").value, topic: document.querySelector("input[name=topic]:checked").value, custom_label: $("custom-label").value, location: $("location").value, location_kind: modalPlace ? "destination" : "search_area", place_id: modalPlace?.place_id ?? "", user_id: activeUser }));
    $("title").value = ""; $("location").value = ""; $("custom-label").value = ""; modalPlace = null;
    closeModal(); $("message-input").focus();
  } catch (error) { showError(error.message); }
});
$("composer").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = $("message-input");
  const text = input.value.trim();
  if (!text) return;
  showError("");
  try { renderState(await post("/api/messages", { user_id: activeUser, text })); input.value = ""; input.focus(); }
  catch (error) { showError(error.message); }
});
void poll();
setInterval(() => void poll(), 500);

// ---- Google Maps place search (proxied through the lab server) ----
let modalPlace = null, pickerTimer = null, pickerToken = null;
document.addEventListener("input", (event) => {
  const input = event.target;
  if (!input.classList?.contains("place-input") && input.id !== "location") return;
  if (input.id === "location") modalPlace = null;
  clearTimeout(pickerTimer);
  const box = input.nextElementSibling;
  pickerToken ??= crypto.randomUUID();
  pickerTimer = setTimeout(async () => {
    const q = input.value.trim();
    if (q.length < 2) { box.innerHTML = ""; return; }
    try {
      const response = await fetch(`/api/places?q=${encodeURIComponent(q)}&token=${pickerToken}`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error);
      box.innerHTML = payload.results.map((r) => `<button type="button" class="place-option" data-place="${escapeHtml(r.place_id)}" data-label="${escapeHtml(r.main)}"><b>${escapeHtml(r.main)}</b><small>${escapeHtml(r.secondary)}</small></button>`).join("") || `<div class="place-empty">No matches</div>`;
    } catch (error) { box.innerHTML = `<div class="place-empty">${escapeHtml(error.message)}</div>`; }
  }, 250);
});
document.addEventListener("click", async (event) => {
  const option = event.target.closest(".place-option");
  const hint = event.target.closest("[data-hint]");
  const geo = event.target.closest("[data-geo]");
  const vote = event.target.closest("[data-vote]");
  const pay = event.target.closest("[data-pay]");
  const splitButton = event.target.closest("#split-button");
  try {
    if (option) {
      const box = option.parentElement, input = box.previousElementSibling;
      pickerToken = null;
      if (input.id === "location") { modalPlace = { place_id: option.dataset.place }; input.value = option.dataset.label; box.innerHTML = ""; return; }
      renderState(await post("/api/destination", { place_id: option.dataset.place }));
    } else if (hint) {
      const input = hint.closest(".tpl-row").querySelector(".place-input");
      input.value = hint.dataset.hint; input.focus(); input.dispatchEvent(new Event("input", { bubbles: true }));
    } else if (geo) {
      navigator.geolocation.getCurrentPosition(
        async (pos) => { try { renderState(await post("/api/origin", { user_id: geo.dataset.geo, lat: pos.coords.latitude, lng: pos.coords.longitude })); } catch (error) { showError(error.message); } },
        (error) => showError(`Location unavailable: ${error.message}`));
    } else if (splitButton) {
      renderState(await post("/api/split", { user_id: activeUser, total: Number($("split-total").value) }));
      splitDraft = "";
    } else if (pay) {
      pay.disabled = true; pay.textContent = "Sending…";
      try { renderState(await post("/api/pay", { user_id: pay.dataset.pay })); } catch (error) { render(); throw error; }
    } else if (vote) {
      renderState(await post("/api/vote", { user_id: activeUser, approve: vote.dataset.vote === "yes" }));
    }
  } catch (error) { showError(error.message); }
});
document.addEventListener("change", async (event) => {
  if (event.target.id !== "threshold") return;
  try { renderState(await post("/api/threshold", { value: Number(event.target.value) })); } catch (error) { showError(error.message); }
});

// ---- Category cards: photo widgets from SerpApi Google Images (fetched and cached by the lab server) ----
const CAT_EMOJI = { Dining: "🍽", Travel: "✈️", Entertainment: "🎟", Custom: "✨" };
function setCardPhoto(cat, image) {
  const el = document.querySelector(`.cat-photo[data-cat="${cat}"]`);
  if (!el) return;
  el.style.backgroundImage = image?.url ? `url('${image.url}')` : "";
  el.classList.toggle("has-photo", Boolean(image?.url));
  el.title = image?.source ? `Photo: ${image.source}` : "";
}
fetch("/api/categories").then((r) => r.json()).then((payload) => {
  for (const [cat, image] of Object.entries(payload.images ?? {})) setCardPhoto(cat, image);
}).catch(() => {});
const syncCustom = () => {
  const custom = document.querySelector("input[name=topic]:checked").value === "Custom";
  $("custom-wrap").hidden = !custom;
  if (custom) $("custom-label").focus();
};
document.querySelectorAll("input[name=topic]").forEach((r) => r.addEventListener("change", syncCustom));
let customTimer = null;
$("custom-label").addEventListener("input", () => {
  clearTimeout(customTimer);
  const label = $("custom-label").value.trim();
  $("custom-name").textContent = label || "Custom";
  customTimer = setTimeout(async () => {
    if (label.length < 3) { setCardPhoto("Custom", null); return; }
    try {
      const payload = await (await fetch(`/api/category-image?q=${encodeURIComponent(label)}`)).json();
      if ($("custom-label").value.trim() === label) setCardPhoto("Custom", payload.image);
    } catch { /* the card keeps its emoji */ }
  }, 700);
});
document.addEventListener("input", (event) => { if (event.target.id === "split-total") splitDraft = event.target.value; });
