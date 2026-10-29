const $ = s => document.querySelector(s);
const COLS = [["business_name","Business"],["phone","Phone"],["website","Website"],["category","Category"],["city","City"],["address","Address"],["website_status","Site status"],["source","Source"]];
const PER = 25;
let rows = [], view = [], sortKey = "business_name", sortDir = 1, page = 0, current = "", poll = null;

async function api(path, opt) {
  const r = await fetch(path, opt);
  const data = r.headers.get("content-type")?.includes("json") ? await r.json() : null;
  if (!r.ok) throw new Error(data?.error || r.statusText);
  return data;
}
const el = (tag, props = {}, kids = []) => { const e = Object.assign(document.createElement(tag), props); e.append(...kids); return e; };

async function loadRuns() {
  const runs = await api("/api/runs");
  const ul = $("#runs"); ul.replaceChildren();
  $("#noruns").hidden = runs.length > 0;
  for (const r of runs) {
    const del = el("button", { className: "icon", title: "Delete dataset", textContent: "🗑" });
    del.onclick = ev => { ev.stopPropagation(); confirmDelete(r); };
    const when = new Date(r.modified * 1000).toLocaleString();
    const li = el("li", { className: r.name === current ? "on" : "" }, [
      el("div", { className: "t" }, [el("b", { textContent: `${r.category || "?"} · ${r.city || "area"}` }),
        el("small", { textContent: `${r.records ?? "?"} records · ${when}` })]), del]);
    li.onclick = () => openRun(r.name);
    ul.append(li);
  }
}

function confirmDelete(r) {
  $("#dmsg").textContent = `Delete “${r.category} · ${r.city || "area"}” (${r.records ?? "?"} records)? This removes its CSV and report from disk.`;
  $("#dyes").onclick = async () => {
    $("#dlg").close();
    try { await api(`/api/runs/${r.name}`, { method: "DELETE" }); } catch (e) { alert(e.message); }
    if (current === r.name) { current = ""; $("#results").hidden = true; }
    loadRuns();
  };
  $("#dno").onclick = () => $("#dlg").close();
  $("#dlg").showModal();
}

async function openRun(name) {
  const d = await api(`/api/runs/${name}`);
  current = name; rows = d.rows; page = 0;
  $("#rtitle").textContent = `${d.report.run?.category || ""} · ${d.report.run?.city || ""}`;
  $("#dl").href = `/api/runs/${name}/csv`;
  const r = d.report, cov = r.coverage_before_trimming || {};
  const tiles = [["Records", r.total_records], ["With phone", `${r.pct_with_phone}%`], ["With website", `${r.pct_with_website}%`],
    ["Phone + website", `${r.pct_complete}%`], ["Duplicates merged", r.duplicates_merged], ["Invalid URLs", `${r.invalid_url_rate_pct}%`],
    ["Failed requests", r.failed_requests], ["Cost (₹)", r.estimated_cost_inr]];
  if ("pilot_passed" in r) tiles.push(["Pilot", r.pilot_passed ? "Passed" : "Not passed"]);
  $("#stats").replaceChildren(...tiles.map(([k, v]) => el("div", {}, [el("b", { textContent: v ?? "–" }), el("span", { textContent: k })])));
  $("#report").textContent = JSON.stringify(r, null, 2);
  $("#thead").replaceChildren(el("tr", {}, COLS.map(([k, label]) => {
    const th = el("th", { textContent: label }); th.onclick = () => { sortDir = sortKey === k ? -sortDir : 1; sortKey = k; draw(); }; return th; })));
  $("#results").hidden = false; draw(); loadRuns();
}

function draw() {
  const q = $("#q").value.toLowerCase();
  view = rows.filter(r => (!$("#fp").checked || r.phone) && (!$("#fw").checked || r.website) &&
    (!q || COLS.some(([k]) => (r[k] || "").toLowerCase().includes(q))));
  view.sort((a, b) => (a[sortKey] || "").localeCompare(b[sortKey] || "") * sortDir);
  const pages = Math.max(1, Math.ceil(view.length / PER)); page = Math.min(page, pages - 1);
  $("#tbody").replaceChildren(...view.slice(page * PER, (page + 1) * PER).map(r => el("tr", {}, COLS.map(([k]) => {
    const td = el("td", { title: r[k] || "" });
    if (k === "website" && r[k]) td.append(el("a", { href: r[k], textContent: r[k].replace(/^https?:\/\//, ""), target: "_blank", rel: "noopener noreferrer" }));
    else if (k === "phone" && r[k]) td.append(el("a", { href: "tel:" + r[k], textContent: r[k] }));
    else td.textContent = r[k] || "";
    return td; }))));
  $("#count").textContent = `${view.length} of ${rows.length} rows`;
  $("#page").textContent = `Page ${page + 1} / ${pages}`;
  $("#prev").disabled = page === 0; $("#next").disabled = page >= pages - 1;
}

async function tick() {
  const j = await api("/api/job");
  if (j.status === "idle") return;
  $("#jobcard").hidden = false;
  $("#jobtitle").textContent = `Current execution: ${j.label}`;
  const s = $("#jobstate"); s.textContent = j.status; s.className = "pill " + j.status;
  const secs = Math.round(((j.ended || Date.now() / 1000) - j.started));
  const enriching = j.total > 0;
  $("#jobinfo").textContent = (enriching ? `Checking websites: ${j.done} of ${j.total}` : "Collecting records…") + ` · ${secs}s elapsed`;
  $("#barfill").style.width = (j.status === "finished" ? 100 : enriching ? Math.round(100 * j.done / j.total) : 5) + "%";
  const pre = $("#log"), stick = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 20;
  pre.textContent = j.log.join("\n"); if (stick) pre.scrollTop = pre.scrollHeight;
  const running = j.status === "running";
  $("#cancel").hidden = !running; $("#go").disabled = running;
  $("#pill").textContent = running ? "Running" : "Idle"; $("#pill").className = "pill " + (running ? "running" : "");
  if (!running && poll) { clearInterval(poll); poll = null; loadRuns(); if (j.status === "finished") openRun(j.run); }
}
const startPolling = () => { if (!poll) poll = setInterval(() => tick().catch(() => {}), 1500); tick(); };

$("#f").onsubmit = async ev => {
  ev.preventDefault(); $("#err").hidden = true;
  const b = Object.fromEntries(new FormData(ev.target)); 
  for (const k of ["skip_enrich", "require_phone", "require_website", "pilot"]) b[k] = ev.target[k].checked;
  try { await api("/api/job", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) }); startPolling(); }
  catch (e) { $("#err").textContent = e.message; $("#err").hidden = false; }
};
$("#cancel").onclick = () => api("/api/job", { method: "DELETE" }).then(tick);
$("#q").oninput = $("#fp").onchange = $("#fw").onchange = () => { page = 0; draw(); };
$("#prev").onclick = () => { page--; draw(); }; $("#next").onclick = () => { page++; draw(); };
loadRuns(); api("/api/job").then(j => { if (j.status === "running") startPolling(); });
