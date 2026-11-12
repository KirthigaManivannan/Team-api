"use strict";
const $ = (s, r = document) => r.querySelector(s);

/* Build DOM nodes without innerHTML: document content is untrusted. */
function h(tag, props = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "value") el.value = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  return el;
}

const TYPE_LABELS = { email: "Email", digital_pdf: "Digital PDF", scanned_pdf: "Scanned PDF (OCR)", image: "Image (OCR)" };
const STATUS_LABELS = { valid: "Looks good", needs_review: "Needs review", invalid: "Has errors" };

let items = [];      // one entry per document being processed
let activeId = null;
let queued = [];     // files chosen but not yet processed
let nextId = 1;
let toastTimer;

function notify(msg, kind = "info") {
  const t = $("#toast");
  t.textContent = msg; t.className = "toast " + (kind === "error" ? "error" : ""); t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => (t.hidden = true), 4500);
}

async function api(path, opts) {
  let res;
  try { res = await fetch(path, opts); }
  catch { throw new Error("Cannot reach the server. Check that the app is running."); }
  let body = null;
  try { body = await res.json(); } catch { /* not JSON */ }
  if (!res.ok) {
    let d = body && body.detail;
    if (Array.isArray(d)) d = d.map((x) => x.msg).join("; ");
    throw new Error(d || `Request failed (${res.status}).`);
  }
  return body;
}

const postJSON = (path, data) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
function postFile(path, file) { const fd = new FormData(); fd.append("file", file); return api(path, { method: "POST", body: fd }); }

/* ---------- input handling ---------- */
function switchTab(which) {
  for (const t of ["doc", "email"]) {
    $("#tab-" + t).setAttribute("aria-selected", String(t === which));
    $("#pane-" + t).hidden = t !== which;
  }
}
$("#tab-doc").onclick = () => switchTab("doc");
$("#tab-email").onclick = () => switchTab("email");

const OK_EXT = /\.(pdf|png|jpe?g)$/i;
function addFiles(list) {
  for (const f of list) {
    if (!OK_EXT.test(f.name)) { notify(`"${f.name}" is not supported. Use PDF, PNG or JPG.`, "error"); continue; }
    if (f.size > 10 * 1024 * 1024) { notify(`"${f.name}" is larger than 10 MB.`, "error"); continue; }
    queued.push(f);
  }
  renderQueue();
}
function renderQueue() {
  const ul = $("#file-list"); ul.replaceChildren();
  queued.forEach((f, i) => ul.append(h("li", {}, h("span", {}, f.name), h("button", { type: "button", "aria-label": "Remove " + f.name, onclick: () => { queued.splice(i, 1); renderQueue(); } }, "Remove"))));
  $("#run-docs").disabled = queued.length === 0;
}
const drop = $("#drop");
$("#file-input").onchange = (e) => { addFiles(e.target.files); e.target.value = ""; };
["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", (e) => addFiles(e.dataTransfer.files));

/* ---------- processing ---------- */
function newItem(label) {
  const it = { id: nextId++, label, status: "processing", step: "Reading the content…", data: null, text: "", error: null, edited: new Set(), view: "fields" };
  items.push(it); activeId = it.id; render(); return it;
}

async function runExtract(it, textResult) {
  it.text = textResult.text; it.inputType = textResult.input_type; it.warnings = textResult.warnings || [];
  it.step = "Classifying and extracting fields…"; render();
  it.data = await postJSON("/extract", { filename: textResult.filename, text: textResult.text });
  it.status = "done"; render();
}
function fail(it, e) { it.status = "error"; it.error = e.message; render(); notify(e.message, "error"); }

async function processFile(file) {
  const it = newItem(file.name);
  try { await runExtract(it, await postFile("/document/upload", file)); } catch (e) { fail(it, e); }
}

$("#run-docs").onclick = async () => {
  const files = queued; queued = []; renderQueue();
  setBusy(true);
  for (const f of files) await processFile(f);
  setBusy(false);
};

$("#run-email").onclick = async () => {
  const body = $("#e-body").value;
  if (!body.trim()) { notify("Paste the email message first.", "error"); return; }
  const subject = $("#e-subject").value;
  setBusy(true);
  const it = newItem(subject || "Pasted email");
  try {
    const r = await postJSON("/email/submit", { subject, sender: $("#e-from").value, recipient: $("#e-to").value, body });
    await runExtract(it, r);
  } catch (e) { fail(it, e); }
  setBusy(false);
};

$("#eml-input").onchange = async (e) => {
  const file = e.target.files[0]; e.target.value = "";
  if (!file) return;
  setBusy(true);
  const it = newItem(file.name);
  try {
    const r = await postFile("/email/upload", file);
    await runExtract(it, r);
    for (const att of r.attachments || []) {
      const ai = newItem(att.filename + " (attachment)");
      if (att.error) fail(ai, new Error(`${att.filename}: ${att.error}`));
      else { try { await runExtract(ai, { filename: att.filename, text: att.text, input_type: att.input_type }); } catch (err) { fail(ai, err); } }
    }
    activeId = it.id; render();
  } catch (err) { fail(it, err); }
  setBusy(false);
};

function setBusy(b) { $("#run-email").disabled = b; $("#run-docs").disabled = b || queued.length === 0; }

/* ---------- rendering ---------- */
function render() {
  const sw = $("#switcher"); sw.replaceChildren();
  if (items.length > 1) items.forEach((it) => sw.append(h("button", { type: "button", "aria-pressed": String(it.id === activeId), onclick: () => { activeId = it.id; render(); } }, it.label)));
  const box = $("#result"); box.replaceChildren();
  const it = items.find((x) => x.id === activeId);
  if (!it) { box.append(h("p", { class: "empty" }, "Add a document or an email to see the extracted fields here.")); return; }
  if (it.status === "processing") { box.append(h("div", { class: "busy" }, h("div", { class: "spin", "aria-hidden": "true" }), h("div", {}, h("strong", {}, it.label), h("div", {}, it.step)))); return; }
  if (it.status === "error") { box.append(h("div", { class: "err" }, h("strong", {}, `Could not process ${it.label}`), h("p", {}, it.error))); return; }
  box.append(renderResult(it));
}

function coerce(type, raw) {
  raw = raw.trim();
  if (raw === "") return null;
  if (type === "number" && /^[-+]?[\d.,]+$/.test(raw)) { const n = Number(raw.replace(/,/g, "")); if (Number.isFinite(n)) return n; }
  return raw;
}

function exportObject(it) {
  const d = it.data;
  return {
    filename: d.filename, document_type: d.document_type, classification_confidence: d.classification_confidence,
    fields: d.fields, line_items: d.line_items,
    validation: { status: d.validation.status, missing_fields: d.validation.missing_fields, uncertain_fields: d.validation.uncertain_fields, issues: d.validation.issues },
    user_edited_fields: [...it.edited], model: d.model,
  };
}

function renderResult(it) {
  const d = it.data, v = d.validation;
  const issueFor = {};
  for (const i of v.issues) if (i.severity !== "info" && (!issueFor[i.field] || i.severity === "error")) issueFor[i.field] = i;
  const jsonPre = h("pre", { class: "out" }, JSON.stringify(exportObject(it), null, 2));
  const refreshJson = () => { jsonPre.textContent = JSON.stringify(exportObject(it), null, 2); };

  const cell = (spec, getVal, setVal, path) => {
    const val = getVal();
    const inp = h("input", { type: "text", value: val == null ? "" : String(val), placeholder: "Not found", "aria-label": spec.label,
      class: issueFor[path] ? "flag-" + issueFor[path].severity : "" });
    if (it.edited.has(path)) inp.classList.add("edited");
    inp.addEventListener("input", () => { setVal(coerce(spec.type, inp.value)); it.edited.add(path); inp.classList.add("edited"); refreshJson(); });
    const td = h("td", {}, inp);
    if (issueFor[path]) td.append(h("div", { class: "sub" }, issueFor[path].message));
    return td;
  };

  const fieldRows = d.field_specs.map((s) => h("tr", {}, h("td", { class: "k" }, s.label, s.required ? h("span", { class: "req", title: "Required" }, " *") : null),
    cell(s, () => d.fields[s.key], (x) => (d.fields[s.key] = x), s.key)));

  const parts = [
    h("div", { class: "head" },
      h("div", {}, h("div", { class: "name" }, d.filename), h("div", { class: "doctype" }, d.document_type)),
      h("div", { class: "pills" },
        h("span", { class: "pill " + v.status }, STATUS_LABELS[v.status] || v.status),
        it.inputType ? h("span", { class: "pill" }, TYPE_LABELS[it.inputType] || it.inputType) : null,
        d.classification_confidence != null ? h("span", { class: "pill" }, Math.round(d.classification_confidence * 100) + "% sure of type") : null)),
  ];

  const shown = v.issues.filter((i) => i.severity !== "info");
  const info = v.issues.filter((i) => i.severity === "info");
  if (shown.length || info.length || (it.warnings || []).length) {
    const ul = h("ul", { class: "issues" });
    (it.warnings || []).forEach((w) => ul.append(h("li", {}, w)));
    shown.forEach((i) => ul.append(h("li", { class: i.severity }, i.message)));
    if (info.length) ul.append(h("li", {}, h("details", {}, h("summary", {}, `${info.length} optional field(s) not found`), info.map((i) => h("div", {}, i.message)))));
    parts.push(ul);
  } else parts.push(h("ul", { class: "issues" }, h("li", {}, "No problems found. Please still compare the values with the original.")));

  parts.push(h("div", { class: "tablewrap" }, h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Field"), h("th", {}, "Value (editable)"))), h("tbody", {}, fieldRows))));

  if (d.item_specs.length) {
    parts.push(h("div", { class: "sub" }, "Line items"));
    if (!d.line_items.length) parts.push(h("p", { class: "empty" }, "No line items were found."));
    else {
      const head = h("tr", {}, d.item_specs.map((s) => h("th", {}, s.label)));
      const rows = d.line_items.map((row, i) => h("tr", {}, d.item_specs.map((s) => cell(s, () => row[s.key], (x) => (row[s.key] = x), `line_items[${i}].${s.key}`))));
      parts.push(h("div", { class: "tablewrap" }, h("table", {}, h("thead", {}, head), h("tbody", {}, rows))));
    }
  }

  const textPre = h("pre", { class: "out text" }, it.text);
  textPre.hidden = true;
  const tabJson = h("button", { class: "tab", role: "tab", "aria-selected": "true", type: "button" }, "JSON");
  const tabText = h("button", { class: "tab", role: "tab", "aria-selected": "false", type: "button" }, "Extracted text");
  const show = (which) => { tabJson.setAttribute("aria-selected", String(which === "json")); tabText.setAttribute("aria-selected", String(which === "text")); jsonPre.hidden = which !== "json"; textPre.hidden = which !== "text"; };
  tabJson.onclick = () => show("json"); tabText.onclick = () => show("text");

  const copy = async () => {
    const txt = JSON.stringify(exportObject(it), null, 2);
    try { await navigator.clipboard.writeText(txt); notify("JSON copied."); }
    catch { const r = document.createRange(); r.selectNodeContents(jsonPre); getSelection().removeAllRanges(); getSelection().addRange(r); notify("Select and copy the JSON manually (clipboard blocked).", "error"); }
  };
  const download = () => {
    const blob = new Blob([JSON.stringify(exportObject(it), null, 2)], { type: "application/json" });
    const a = h("a", { href: URL.createObjectURL(blob), download: (d.filename.replace(/\.[^.]+$/, "") || "extraction") + ".json" });
    document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    notify("JSON downloaded.");
  };
  parts.push(h("div", { class: "viewtabs", role: "tablist" }, tabJson, tabText, h("span", { class: "sp" }),
    h("button", { class: "btn", type: "button", onclick: copy }, "Copy JSON"), h("button", { class: "btn primary", type: "button", onclick: download }, "Download JSON")), jsonPre, textPre);
  parts.push(h("p", { class: "note" }, "Warnings reflect the original extraction. Fields you edit are listed under user_edited_fields in the JSON."));
  return h("div", {}, parts);
}

fetch("/health").then((r) => r.json()).then((j) => ($("#version").textContent = "v" + j.version)).catch(() => {});

// Gmail extraction results

async function loadGmailResults() {
  const container = document.querySelector("#gmail-results");

  container.textContent = "Loading Gmail results...";

  try {
    const response = await fetch("/gmail/results?limit=50");

    if (!response.ok) {
      throw new Error("Unable to retrieve Gmail results.");
    }

    const data = await response.json();

    container.replaceChildren();

    if (data.results.length === 0) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "No Gmail documents have been saved yet.";
      container.appendChild(empty);
      return;
    }

    data.results.forEach((item) => {
      const card = document.createElement("article");
      card.className = "gmail-result";

      const heading = document.createElement("h3");
      heading.textContent = item.subject || "No subject";

      const sender = document.createElement("p");
      sender.textContent = "From: " + (item.sender || "Unknown");

      const filename = document.createElement("p");
      filename.textContent = "File: " + item.filename;

      const type = document.createElement("p");
      type.textContent = "Document type: " + (item.document_type || "Unknown");

      const status = document.createElement("p");
      status.textContent =
        "Validation: " + (item.validation?.status || "Not available");

      const fieldsTitle = document.createElement("h4");
      fieldsTitle.textContent = "Extracted fields";

      const fieldsList = document.createElement("ul");

      Object.entries(item.fields || {}).forEach(([key, value]) => {
        const li = document.createElement("li");
        li.textContent = `${key}: ${value ?? ""}`;
        fieldsList.appendChild(li);
      });

      card.append(
        heading,
        sender,
        filename,
        type,
        status,
        fieldsTitle,
        fieldsList
      );

      container.appendChild(card);
    });

  } catch (error) {
    container.textContent = error.message;
  }
}

// Refresh button
document
  .querySelector("#refresh-gmail")
  .addEventListener("click", loadGmailResults);

// Load results when the website opens
loadGmailResults();

// Gmail processing history

async function loadGmailHistory() {
  const tableBody = document.querySelector("#gmail-history");

  tableBody.replaceChildren();

  const loadingRow = document.createElement("tr");
  const loadingCell = document.createElement("td");
  loadingCell.colSpan = 4;
  loadingCell.textContent = "Loading history...";
  loadingRow.appendChild(loadingCell);
  tableBody.appendChild(loadingRow);

  try {
    const response = await fetch("/gmail/history?limit=100");

    if (!response.ok) {
      throw new Error("Unable to load Gmail history.");
    }

    const data = await response.json();

    tableBody.replaceChildren();

    if (data.history.length === 0) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 4;
      cell.textContent = "No Gmail processing history available yet.";
      row.appendChild(cell);
      tableBody.appendChild(row);
      return;
    }

    data.history.forEach((item) => {
      const row = document.createElement("tr");

      const subject = document.createElement("td");
      subject.textContent = item.subject || "No subject";

      const status = document.createElement("td");
      status.textContent = item.status || "Unknown";
      status.className = "history-status";

      const processedAt = document.createElement("td");
      processedAt.textContent = item.processed_at || "-";

      const messageId = document.createElement("td");
      messageId.textContent = item.message_id || "-";

      row.append(subject, status, processedAt, messageId);
      tableBody.appendChild(row);
    });

  } catch (error) {
    tableBody.replaceChildren();

    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 4;
    cell.textContent = error.message;
    row.appendChild(cell);
    tableBody.appendChild(row);
  }
}

// Refresh history button
document
  .querySelector("#refresh-history")
  .addEventListener("click", loadGmailHistory);

// Load history when website opens
loadGmailHistory();
