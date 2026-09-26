const $ = (id) => document.getElementById(id);
const state = { result: null, kept: new Set(), busy: false };
const stages = ["Understanding your request", "Reading couple memory", "Discovering Paris activities", "Composing your date"];

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}
function coupleId() { return $("couple-id").value.trim(); }
function showNotice(message, error = false) {
  const el = $("notice"); el.textContent = message; el.classList.toggle("error", error); el.classList.remove("hidden");
}
function clearNotice() { $("notice").classList.add("hidden"); }
async function api(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  let data;
  try { data = await response.json(); } catch { data = {}; }
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === "string" ? detail : detail?.error || "Something went wrong. Please try again.");
  }
  return data;
}
function setBusy(value) {
  state.busy = value;
  ["generate", "proactive-button"].forEach((id) => { $(id).disabled = value; });
}
function startProgress() {
  $("progress").classList.remove("hidden");
  const list = $("progress-list");
  let index = 0;
  const draw = () => { list.innerHTML = stages.map((stage, i) => `<li class="${i < index ? "done" : i === index ? "active" : ""}">${escapeHtml(stage)}</li>`).join(""); };
  draw();
  const timer = setInterval(() => { if (index < stages.length - 1) { index++; draw(); } }, 650);
  return () => { clearInterval(timer); index = stages.length; draw(); setTimeout(() => $("progress").classList.add("hidden"), 500); };
}
function humanTime(value) { return value?.slice(0, 5) || ""; }
function money(value) { return `€${Number(value || 0).toFixed(0)}`; }
function dateTitle(plan, index) {
  const types = [...new Set(plan.activities.map((activity) => activity.type.replaceAll("_", " ")))];
  return types.length > 1 ? `${types[0]} & ${types[1]}` : types[0] || `Date ${index + 1}`;
}
function activityHtml(activity, planIndex) {
  const key = `${planIndex}:${activity.id}`;
  const kept = state.kept.has(key);
  return `<div class="activity">
    <div class="activity-time">${escapeHtml(humanTime(activity.start))}</div>
    <div><h4>${escapeHtml(activity.name)}</h4><div class="activity-meta">${escapeHtml(activity.type.replaceAll("_", " "))} · until ${escapeHtml(humanTime(activity.end))}</div>
      <p class="activity-why">${escapeHtml(activity.why)}</p>
      <div class="activity-actions"><button class="mini-button ${kept ? "kept" : ""}" type="button" data-action="keep" data-plan="${planIndex}" data-id="${escapeHtml(activity.id)}">${kept ? "✓ Keeping this" : "♡ Keep this"}</button>
      <button class="mini-button" type="button" data-action="replace" data-plan="${planIndex}" data-id="${escapeHtml(activity.id)}">Find another ↗</button></div></div>
    <div class="activity-price">${money(activity.price_per_person)} <small>/ person</small></div>
  </div>`;
}
function planHtml(plan, index) {
  return `<article class="plan-card"><div class="plan-card-head"><div><span class="plan-no">POSSIBILITY 0${index + 1}</span><h3>${escapeHtml(dateTitle(plan, index))}</h3></div><div class="plan-total"><strong>${money(plan.estimated_total_eur)}</strong><small>for two</small></div></div>
    <div class="plan-body"><p class="plan-reason">${escapeHtml(plan.reason)}</p>${plan.activities.map((item) => activityHtml(item, index)).join("")}</div>
    <div class="feedback-box"><strong>How does this feel?</strong><div class="feedback-actions" aria-label="Overall feedback">
      ${[["😍", 5, "positive"], ["🙂", 4, "positive"], ["😐", 3, "neutral"], ["👎", 1, "negative"]].map(([icon, rating, sentiment]) => `<button class="feedback-button" type="button" title="Rate ${rating} out of 5" aria-label="Rate ${rating} out of 5" data-action="feedback" data-plan="${index}" data-rating="${rating}" data-sentiment="${sentiment}">${icon}</button>`).join("")}
    </div></div></article>`;
}
function renderPlans(result, heading) {
  state.result = result; state.kept.clear();
  $("results").classList.remove("hidden");
  $("results").querySelector("h2").textContent = heading || "A date to look forward to.";
  $("plan-count").textContent = `${result.plans.length} ${result.plans.length === 1 ? "idea" : "ideas"} for you`;
  $("plan-list").innerHTML = result.plans.map(planHtml).join("");
  $("results").scrollIntoView({ behavior: "smooth", block: "start" });
}
async function generate() {
  if (state.busy) return;
  const text = $("date-idea").value.trim();
  if (!coupleId() || !text) { showNotice("Add your couple name and tell us the kind of date you want.", true); return; }
  localStorage.setItem("chandelleCouple", coupleId()); clearNotice(); setBusy(true);
  const finish = startProgress();
  try {
    const result = await api("/v1/date/request", { method: "POST", body: JSON.stringify({ couple_id: coupleId(), text }) });
    renderPlans(result);
  } catch (error) { showNotice(error.message, true); }
  finally { finish(); setBusy(false); }
}
async function replaceActivity(planIndex, activityId) {
  if (state.busy || !state.result) return;
  if (state.kept.has(`${planIndex}:${activityId}`)) { showNotice("This activity is kept. Tap ‘Keeping this’ before swapping it.", true); return; }
  const plan = state.result.plans[planIndex]; clearNotice(); setBusy(true);
  try {
    const result = await api("/v1/date/replace", { method: "POST", body: JSON.stringify({
      couple_id: coupleId(), time_window: state.result.availability, plan,
      replace_activity_id: activityId, budget_cap: state.result.budget_cap
    }) });
    renderPlans(result, "A fresh twist for your date.");
    showNotice("We found a new activity and kept the rest of your date together.");
  } catch (error) { showNotice(error.message, true); }
  finally { setBusy(false); }
}
async function submitFeedback(planIndex, rating, sentiment) {
  if (!state.result) return;
  const plan = state.result.plans[planIndex];
  const tags = plan.activities.map((item) => item.type);
  try {
    await api("/v1/date/feedback", { method: "POST", body: JSON.stringify({
      couple_id: coupleId(), date_plan_id: plan.date_plan_id, rating, sentiment,
      liked_tags: rating >= 4 ? tags : [], disliked_tags: rating === 1 ? tags : [],
      decision: rating >= 4 ? "selected" : "rejected"
    }) });
    showNotice("Saved to your couple memory. Your next suggestion will learn from this.");
    await showMemory(false);
  } catch (error) { showNotice(error.message, true); }
}
function tagsHtml(values) { return values?.length ? `<div class="memory-tags">${values.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>` : "<p>Nothing here yet.</p>"; }
async function showMemory(scroll = true) {
  if (!coupleId()) { showNotice("Add a couple name to view memory.", true); return; }
  try {
    const memory = await api(`/v1/couples/${encodeURIComponent(coupleId())}/memory`);
    const view = $("memory-view");
    view.innerHTML = `<strong>${escapeHtml(memory.couple_id)}</strong><p>Shared interests</p>${tagsHtml(memory.shared_interests)}<p>Dislikes</p>${tagsHtml(memory.dislikes)}
      <p>Typical budget: ${memory.typical_budget == null ? "Still learning" : money(memory.typical_budget) + " for two"}</p>
      <p>${memory.date_history.length} dates remembered · ${memory.feedback.length} feedback notes · ${memory.selections.length} choices</p>`;
    view.classList.remove("hidden"); if (scroll) view.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (error) { showNotice(error.message, true); }
}
async function proactive() {
  if (!coupleId() || state.busy) { if (!coupleId()) showNotice("Add a couple name first.", true); return; }
  clearNotice(); setBusy(true);
  const view = $("proactive-view"); view.classList.remove("hidden"); view.innerHTML = "Checking your next shared moment…";
  try {
    const decision = await api("/v1/proactive/check", { method: "POST", body: JSON.stringify({ couple_id: coupleId() }) });
    view.innerHTML = `<strong>${decision.triggered ? "A good moment is waiting" : "A little more time"}</strong><p>${escapeHtml(decision.reason)}</p>
      <p>${decision.candidate_count} local activities available</p>${decision.triggered ? `<div class="mini-plan"><strong>${escapeHtml(decision.result.plans[0].activities.map((item) => item.name).join(" → "))}</strong>${money(decision.result.plans[0].estimated_total_eur)} for two<button id="view-proactive-plan" class="mini-button" type="button">See the plan ↗</button></div>` : ""}`;
    if (decision.triggered) $("view-proactive-plan").addEventListener("click", () => renderPlans(decision.result, "A little nudge for you."));
  } catch (error) { view.classList.add("hidden"); showNotice(error.message, true); }
  finally { setBusy(false); }
}
$("generate").addEventListener("click", generate);
$("memory-button").addEventListener("click", () => showMemory());
$("proactive-button").addEventListener("click", proactive);
$("plan-list").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action]"); if (!button) return;
  const index = Number(button.dataset.plan), id = button.dataset.id;
  if (button.dataset.action === "keep") {
    const key = `${index}:${id}`; state.kept.has(key) ? state.kept.delete(key) : state.kept.add(key);
    $("plan-list").innerHTML = state.result.plans.map(planHtml).join("");
  } else if (button.dataset.action === "replace") replaceActivity(index, id);
  else if (button.dataset.action === "feedback") submitFeedback(index, Number(button.dataset.rating), button.dataset.sentiment);
});
document.querySelectorAll(".suggestion").forEach((button) => button.addEventListener("click", () => { $("date-idea").value = button.dataset.idea; $("date-idea").focus(); }));
$("couple-id").value = localStorage.getItem("chandelleCouple") || "demo-couple";
