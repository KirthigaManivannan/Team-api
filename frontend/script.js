
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

  for (const kid of kids.flat()) {
    if (kid != null && kid !== false) {
      el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    }
  }

  return el;
}

const TYPE_LABELS = {
  email: "Email",
  digital_pdf: "Digital PDF",
  scanned_pdf: "Scanned PDF (OCR)",
  image: "Image (OCR)"
};

const STATUS_LABELS = {
  valid: "Looks good",
  needs_review: "Needs review",
  invalid: "Has errors"
};

let items = [];
let activeId = null;
let queued = [];
let nextId = 1;
let toastTimer;

function notify(msg, kind = "info") {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast " + (kind === "error" ? "error" : "");
  t.hidden = false;

  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), 4500);
}

async function api(path, opts) {
  let res;

  try {
    res = await fetch(path, opts);
  } catch {
    throw new Error("Cannot reach the server. Check that the app is running.");
  }

  let body = null;

  try {
    body = await res.json();
  } catch {
    /* not JSON */
  }

  if (!res.ok) {
    let d = body && body.detail;

    if (Array.isArray(d)) {
      d = d.map((x) => x.msg).join("; ");
    }

    throw new Error(d || `Request failed (${res.status}).`);
  }

  return body;
}

const postJSON = (path, data) =>
  api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });

function postFile(path, file) {
  const fd = new FormData();
  fd.append("file", file);
  return api(path, { method: "POST", body: fd });
}

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
    if (!OK_EXT.test(f.name)) {
      notify(`"${f.name}" is not supported. Use PDF, PNG or JPG.`, "error");
      continue;
    }

    if (f.size > 10 * 1024 * 1024) {
      notify(`"${f.name}" is larger than 10 MB.`, "error");
      continue;
    }

    queued.push(f);
  }

  renderQueue();
}

function renderQueue() {
  const ul = $("#file-list");
  ul.replaceChildren();

  queued.forEach((f, i) => {
    ul.append(
      h(
        "li",
        {},
        h("span", {}, f.name),
        h(
          "button",
          {
            type: "button",
            "aria-label": "Remove " + f.name,
            onclick: () => {
              queued.splice(i, 1);
              renderQueue();
            }
          },
          "Remove"
        )
      )
    );
  });

  $("#run-docs").disabled = queued.length === 0;
}

const drop = $("#drop");

$("#file-input").onchange = (e) => {
  addFiles(e.target.files);
  e.target.value = "";
};

["dragenter", "dragover"].forEach((ev) =>
  drop.addEventListener(ev, (e) => {
    e.preventDefault();
    drop.classList.add("over");
  })
);

["dragleave", "drop"].forEach((ev) =>
  drop.addEventListener(ev, (e) => {
    e.preventDefault();
    drop.classList.remove("over");
  })
);

drop.addEventListener("drop", (e) => addFiles(e.dataTransfer.files));

/* ---------- processing ---------- */

function newItem(label) {
  const it = {
    id: nextId++,
    label,
    status: "processing",
    step: "Reading the content…",
    data: null,
    text: "",
    error: null,
    edited: new Set(),
    view: "fields",
    checks: {},
    dupKey: null
  };

  items.push(it);
  activeId = it.id;
  render();

  return it;
}

async function runExtract(it, textResult) {
  it.text = textResult.text;
  it.inputType = textResult.input_type;
  it.warnings = textResult.warnings || [];

  it.step = "Classifying and extracting fields…";
  render();

  it.data = await postJSON("/extract", {
    filename: textResult.filename,
    text: textResult.text
  });

  it.status = "done";
  render();

  await runInvoiceChecks(it);
}

function fail(it, e) {
  it.status = "error";
  it.error = e.message;
  render();
  notify(e.message, "error");
}

async function processFile(file) {
  const it = newItem(file.name);

  try {
    await runExtract(it, await postFile("/document/upload", file));
  } catch (e) {
    fail(it, e);
  }

  return it;
}

$("#run-docs").onclick = async () => {
  const files = queued;
  queued = [];
  renderQueue();

  setBusy(true);

  const batch = [];

  for (const f of files) {
    batch.push(await processFile(f));
  }

  await runMatching(batch);

  setBusy(false);
};

$("#run-email").onclick = async () => {
  const body = $("#e-body").value;

  if (!body.trim()) {
    notify("Paste the email message first.", "error");
    return;
  }

  const subject = $("#e-subject").value;

  setBusy(true);

  const it = newItem(subject || "Pasted email");

  try {
    const r = await postJSON("/email/submit", {
      subject,
      sender: $("#e-from").value,
      recipient: $("#e-to").value,
      body
    });

    await runExtract(it, r);
  } catch (e) {
    fail(it, e);
  }

  setBusy(false);
};

$("#eml-input").onchange = async (e) => {
  const file = e.target.files[0];
  e.target.value = "";

  if (!file) return;

  setBusy(true);

  const it = newItem(file.name);

  try {
    const r = await postFile("/email/upload", file);

    await runExtract(it, r);

    for (const att of r.attachments || []) {
      const ai = newItem(att.filename + " (attachment)");

      if (att.error) {
        fail(ai, new Error(`${att.filename}: ${att.error}`));
      } else {
        try {
          await runExtract(ai, {
            filename: att.filename,
            text: att.text,
            input_type: att.input_type
          });
        } catch (err) {
          fail(ai, err);
        }
      }
    }

    activeId = it.id;
    render();
  } catch (err) {
    fail(it, err);
  }

  setBusy(false);
};

function setBusy(b) {
  $("#run-email").disabled = b;
  $("#run-docs").disabled = b || queued.length === 0;
}

/* ---------- rendering ---------- */

function render() {
  $("#export-csv").hidden = !items.some(
    (x) => x.status === "done" && x.data
  );

  const sw = $("#switcher");
  sw.replaceChildren();

  if (items.length > 1) {
    items.forEach((it) => {
      sw.append(
        h(
          "button",
          {
            type: "button",
            "aria-pressed": String(it.id === activeId),
            onclick: () => {
              activeId = it.id;
              render();
            }
          },
          it.label
        )
      );
    });
  }

  const box = $("#result");
  box.replaceChildren();

  const it = items.find((x) => x.id === activeId);

  if (!it) {
    box.append(
      h(
        "p",
        { class: "empty" },
        "Add a document or an email to see the extracted fields here."
      )
    );
    return;
  }

  if (it.status === "processing") {
    box.append(
      h(
        "div",
        { class: "busy" },
        h("div", { class: "spin", "aria-hidden": "true" }),
        h(
          "div",
          {},
          h("strong", {}, it.label),
          h("div", {}, it.step)
        )
      )
    );

    return;
  }

  if (it.status === "error") {
    box.append(
      h(
        "div",
        { class: "err" },
        h("strong", {}, `Could not process ${it.label}`),
        h("p", {}, it.error)
      )
    );

    return;
  }

  box.append(renderResult(it));
}

function coerce(type, raw) {
  raw = raw.trim();

  if (raw === "") return null;

  if (type === "number" && /^[-+]?[\d.,]+$/.test(raw)) {
    const n = Number(raw.replace(/,/g, ""));
    if (Number.isFinite(n)) return n;
  }

  return raw;
}

function exportObject(it) {
  const d = it.data;

  return {
    filename: d.filename,
    document_type: d.document_type,
    classification_confidence: d.classification_confidence,
    fields: d.fields,
    line_items: d.line_items,
    validation: {
      status: d.validation.status,
      missing_fields: d.validation.missing_fields,
      uncertain_fields: d.validation.uncertain_fields,
      issues: d.validation.issues
    },
    user_edited_fields: [...it.edited],
    model: d.model
  };
}

function renderResult(it) {
  const d = it.data;
  const v = d.validation;

  const issueFor = {};

  for (const i of v.issues) {
    if (
      i.severity !== "info" &&
      (!issueFor[i.field] || i.severity === "error")
    ) {
      issueFor[i.field] = i;
    }
  }

  const jsonPre = h(
    "pre",
    { class: "out" },
    JSON.stringify(exportObject(it), null, 2)
  );

  const refreshJson = () => {
    jsonPre.textContent = JSON.stringify(exportObject(it), null, 2);
  };

  const cell = (spec, getVal, setVal, path) => {
    const val = getVal();

    const inp = h("input", {
      type: "text",
      value: val == null ? "" : String(val),
      placeholder: "Not found",
      "aria-label": spec.label,
      class: issueFor[path] ? "flag-" + issueFor[path].severity : ""
    });

    if (it.edited.has(path)) inp.classList.add("edited");

    inp.addEventListener("input", () => {
      setVal(coerce(spec.type, inp.value));
      it.edited.add(path);
      inp.classList.add("edited");
      refreshJson();
    });

    const td = h("td", {}, inp);

    if (issueFor[path]) {
      td.append(
        h("div", { class: "sub" }, issueFor[path].message)
      );
    }

    return td;
  };

  const fieldRows = d.field_specs.map((s) =>
    h(
      "tr",
      {},
      h(
        "td",
        { class: "k" },
        s.label,
        s.required
          ? h("span", { class: "req", title: "Required" }, " *")
          : null
      ),
      cell(
        s,
        () => d.fields[s.key],
        (x) => (d.fields[s.key] = x),
        s.key
      )
    )
  );

  const parts = [
    h(
      "div",
      { class: "head" },
      h(
        "div",
        {},
        h("div", { class: "name" }, d.filename),
        h("div", { class: "doctype" }, d.document_type)
      ),
      h(
        "div",
        { class: "pills" },
        h(
          "span",
          { class: "pill " + v.status },
          STATUS_LABELS[v.status] || v.status
        ),
        it.inputType
          ? h("span", { class: "pill" }, TYPE_LABELS[it.inputType] || it.inputType)
          : null,
        d.classification_confidence != null
          ? h(
              "span",
              { class: "pill" },
              Math.round(d.classification_confidence * 100) + "% sure of type"
            )
          : null
      )
    )
  ];

  const shown = v.issues.filter((i) => i.severity !== "info");
  const info = v.issues.filter((i) => i.severity === "info");

  if (shown.length || info.length || (it.warnings || []).length) {
    const ul = h("ul", { class: "issues" });

    (it.warnings || []).forEach((w) => {
      ul.append(h("li", {}, w));
    });

    shown.forEach((i) => {
      ul.append(h("li", { class: i.severity }, i.message));
    });

    if (info.length) {
      ul.append(
        h(
          "li",
          {},
          h(
            "details",
            {},
            h("summary", {}, `${info.length} optional field(s) not found`),
            info.map((i) => h("div", {}, i.message))
          )
        )
      );
    }

    parts.push(ul);
  } else {
    parts.push(
      h(
        "ul",
        { class: "issues" },
        h(
          "li",
          {},
          "No problems found. Please still compare the values with the original."
        )
      )
    );
  }

  const checksPanel = renderChecks(it);

  if (checksPanel) parts.push(checksPanel);

  parts.push(
    h(
      "div",
      { class: "tablewrap" },
      h(
        "table",
        {},
        h(
          "thead",
          {},
          h("tr", {}, h("th", {}, "Field"), h("th", {}, "Value (editable)"))
        ),
        h("tbody", {}, fieldRows)
      )
    )
  );

  if (d.item_specs.length) {
    parts.push(h("div", { class: "sub" }, "Line items"));

    if (!d.line_items.length) {
      parts.push(h("p", { class: "empty" }, "No line items were found."));
    } else {
      const head = h(
        "tr",
        {},
        d.item_specs.map((s) => h("th", {}, s.label))
      );

      const rows = d.line_items.map((row, i) =>
        h(
          "tr",
          {},
          d.item_specs.map((s) =>
            cell(
              s,
              () => row[s.key],
              (x) => (row[s.key] = x),
              `line_items[${i}].${s.key}`
            )
          )
        )
      );

      parts.push(
        h(
          "div",
          { class: "tablewrap" },
          h("table", {}, h("thead", {}, head), h("tbody", {}, rows))
        )
      );
    }
  }

  const textPre = h("pre", { class: "out text" }, it.text);
  textPre.hidden = true;

  const tabJson = h(
    "button",
    {
      class: "tab",
      role: "tab",
      "aria-selected": "true",
      type: "button"
    },
    "JSON"
  );

  const tabText = h(
    "button",
    {
      class: "tab",
      role: "tab",
      "aria-selected": "false",
      type: "button"
    },
    "Extracted text"
  );

  const show = (which) => {
    tabJson.setAttribute("aria-selected", String(which === "json"));
    tabText.setAttribute("aria-selected", String(which === "text"));
    jsonPre.hidden = which !== "json";
    textPre.hidden = which !== "text";
  };

  tabJson.onclick = () => show("json");
  tabText.onclick = () => show("text");

  const copy = async () => {
    const txt = JSON.stringify(exportObject(it), null, 2);

    try {
      await navigator.clipboard.writeText(txt);
      notify("JSON copied.");
    } catch {
      const r = document.createRange();
      r.selectNodeContents(jsonPre);
      getSelection().removeAllRanges();
      getSelection().addRange(r);
      notify(
        "Select and copy the JSON manually (clipboard blocked).",
        "error"
      );
    }
  };

  const download = () => {
    const blob = new Blob(
      [JSON.stringify(exportObject(it), null, 2)],
      { type: "application/json" }
    );

    const a = h("a", {
      href: URL.createObjectURL(blob),
      download:
        (d.filename.replace(/\.[^.]+$/, "") || "extraction") + ".json"
    });

    document.body.append(a);
    a.click();
    a.remove();

    setTimeout(() => URL.revokeObjectURL(a.href), 1000);

    notify("JSON downloaded.");
  };

  parts.push(
    h(
      "div",
      { class: "viewtabs", role: "tablist" },
      tabJson,
      tabText,
      h("span", { class: "sp" }),
      h("button", { class: "btn", type: "button", onclick: copy }, "Copy JSON"),
      h(
        "button",
        { class: "btn primary", type: "button", onclick: download },
        "Download JSON"
      )
    ),
    jsonPre,
    textPre
  );

  parts.push(
    h(
      "p",
      { class: "note" },
      "Warnings reflect the original extraction. Fields you edit are listed under user_edited_fields in the JSON."
    )
  );

  return h("div", {}, parts);
}

/* ---------- Gmail extraction results ---------- */

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

/* Refresh Gmail results */
document
  .querySelector("#refresh-gmail")
  .addEventListener("click", loadGmailResults);

/* Load Gmail results when website opens */
loadGmailResults();

/* ---------- Gmail processing history ---------- */

async function loadGmailHistory() {
  const tableBody = document.querySelector("#gmail-history");

  tableBody.replaceChildren();

  const loadingRow = document.createElement("tr");
  const loadingCell = document.createElement("td");

  loadingCell.colSpan = 4;
  loadingCell.textContent = "Loading history.";

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

/* Refresh Gmail history */
document
  .querySelector("#refresh-history")
  .addEventListener("click", loadGmailHistory);

/* Load Gmail history when website opens */
loadGmailHistory();

/* ---------- Automatic invoice checks ---------- */

const hasValue = (v) => v != null && String(v).trim() !== "";

function toNum(v) {
  if (typeof v === "number") {
    return Number.isFinite(v) ? v : null;
  }

  if (typeof v === "string" && v.trim() !== "") {
    const n = Number(v.replace(/,/g, ""));
    return Number.isFinite(n) ? n : null;
  }

  return null;
}

const matches = [];

/* Run duplicate and due-date checks for invoices. */
async function runInvoiceChecks(it) {
  if (!it.data || it.data.document_type !== "Invoice") return;

  const f = it.data.fields || {};

  await Promise.all([
    checkDuplicate(it, f),
    checkDueDate(it, f)
  ]);
}

async function checkDuplicate(it, f) {
  const need = [
    ["invoice_number", "invoice number"],
    ["supplier_name", "supplier name"],
    ["invoice_date", "invoice date"]
  ];

  const missing = need
    .filter(([k]) => !hasValue(f[k]))
    .map(([, label]) => label);

  if (missing.length) {
    it.checks.duplicate = {
      state: "skipped",
      message: `Not checked: ${missing.join(", ")} not found in the document.`
    };

    render();
    return;
  }

  const payload = {
    invoice_number: String(f.invoice_number).trim(),
    supplier_name: String(f.supplier_name).trim(),
    invoice_date: String(f.invoice_date).trim()
  };

  const key = JSON.stringify(payload);

  if (it.dupKey === key) return;

  it.dupKey = key;

  it.checks.duplicate = { state: "pending" };
  render();

  try {
    it.checks.duplicate = {
      state: "done",
      ...(await postJSON("/invoices/check-duplicate", payload))
    };
  } catch (e) {
    it.checks.duplicate = {
      state: "error",
      message: e.message
    };
  }

  render();
}

async function checkDueDate(it, f) {
  if (!hasValue(f.due_date)) {
    it.checks.due = {
      state: "skipped",
      message: "Not checked: no due date found in the document."
    };

    render();
    return;
  }

  it.checks.due = { state: "pending" };
  render();

  try {
    const body = {
      invoice_number: hasValue(f.invoice_number)
        ? String(f.invoice_number).trim()
        : null,
      due_date: String(f.due_date).trim()
    };

    it.checks.due = {
      state: "done",
      ...(await postJSON("/payment/check-due-date", body))
    };
  } catch (e) {
    it.checks.due = {
      state: "error",
      message: e.message
    };
  }

  render();
}

/* ---------- Purchase order and invoice matching ---------- */

function matchPayload(it) {
  const f = it.data.fields || {};

  const supplier = hasValue(f.supplier_name)
    ? String(f.supplier_name).trim()
    : "";

  const total = toNum(f.total_amount);

  const missing = [];

  if (!supplier) missing.push("supplier name");
  if (total == null) missing.push("total amount");

  const all = it.data.line_items || [];

  const lines = all
    .map((r) => ({
      description: hasValue(r.description)
        ? String(r.description).trim()
        : "",
      quantity: toNum(r.quantity),
      unit_price: toNum(r.unit_price),
      line_total: toNum(r.line_total)
    }))
    .filter(
      (r) =>
        r.description &&
        r.quantity != null &&
        r.quantity >= 0
    );

  return {
    missing,
    dropped: all.length - lines.length,
    doc: {
      fields: {
        supplier_name: supplier,
        currency: hasValue(f.currency)
          ? String(f.currency).trim()
          : null,
        total_amount: total
      },
      line_items: lines
    }
  };
}

async function runMatching(batch) {
  const done = batch.filter(
    (x) => x.status === "done" && x.data
  );

  const pos = done.filter(
    (x) => x.data.document_type === "Purchase Order"
  );

  const invs = done.filter(
    (x) => x.data.document_type === "Invoice"
  );

  if (pos.length === 1 && invs.length === 1) {
    await matchPair(pos[0], invs[0]);
  }
}

async function matchPair(po, inv) {
  let m = matches.find(
    (x) => x.poId === po.id && x.invId === inv.id
  );

  if (!m) {
    m = { poId: po.id, invId: inv.id };
    matches.push(m);
  }

  const a = matchPayload(po);
  const b = matchPayload(inv);

  m.dropped = a.dropped + b.dropped;
  m.data = null;
  m.message = "";

  const missing = [
    ...a.missing.map((x) => "purchase order " + x),
    ...b.missing.map((x) => "invoice " + x)
  ];

  if (missing.length) {
    m.state = "skipped";
    m.message = `Not compared: ${missing.join(", ")} not found.`;
    render();
    return;
  }

  m.state = "pending";
  render();

  try {
    m.data = await postJSON("/match/po-invoice", {
      purchase_order: a.doc,
      invoice: b.doc
    });

    m.state = "done";
  } catch (e) {
    m.state = "error";
    m.message = e.message;
  }

  render();
}

/* ---------- Automatic checks display ---------- */

const badge = (text, kind) =>
  h("span", { class: "badge " + kind }, text);

const KIND = {
  Match: "good",
  Mismatch: "bad",
  "Needs Review": "warn"
};

function checkRow(title, state, badgeEl, message, extra) {
  return h(
    "div",
    { class: "check" },
    h(
      "div",
      { class: "check-head" },
      h("strong", {}, title),
      state === "pending"
        ? h("span", {
            class: "spin small",
            "aria-hidden": "true"
          })
        : badgeEl
    ),
    message
      ? h("div", { class: "check-msg" }, message)
      : null,
    extra || null
  );
}

function dupRow(c) {
  const t = "Duplicate invoice check";

  if (!c || c.state === "pending") {
    return checkRow(t, "pending", null, "Checking…");
  }

  if (c.state === "skipped") {
    return checkRow(t, c.state, badge("Skipped", ""), c.message);
  }

  if (c.state === "error") {
    return checkRow(t, c.state, badge("Failed", "bad"), c.message);
  }

  return checkRow(
    t,
    c.state,
    c.duplicate
      ? badge("Duplicate", "bad")
      : badge("New invoice", "good"),
    c.message
  );
}

function dueRow(c) {
  const t = "Payment due date";

  if (!c || c.state === "pending") {
    return checkRow(t, "pending", null, "Checking…");
  }

  if (c.state === "skipped") {
    return checkRow(t, c.state, badge("Skipped", ""), c.message);
  }

  if (c.state === "error") {
    return checkRow(t, c.state, badge("Failed", "bad"), c.message);
  }

  const kind = {
    Overdue: "bad",
    "Due Today": "warn",
    Upcoming: "good",
    "Invalid Date": "warn"
  }[c.status] || "";

  return checkRow(
    t,
    c.state,
    badge(c.status, kind),
    c.message + (c.due_date ? ` (due ${c.due_date})` : "")
  );
}

function matchRow(m) {
  const po = items.find((x) => x.id === m.poId);
  const inv = items.find((x) => x.id === m.invId);

  const t = `PO–Invoice match: ${
    po ? po.label : "PO"
  } ↔ ${inv ? inv.label : "invoice"}`;

  if (m.state === "pending") {
    return checkRow(t, "pending", null, "Comparing…");
  }

  if (m.state === "skipped") {
    return checkRow(t, m.state, badge("Skipped", ""), m.message);
  }

  if (m.state === "error") {
    return checkRow(t, m.state, badge("Failed", "bad"), m.message);
  }

  const d = m.data;
  const c = d.checks || {};

  const lines = [
    ["Supplier name", c.supplier_name],
    ["Currency", c.currency],
    ["Total amount", c.total_amount]
  ].map(([label, v]) =>
    h(
      "li",
      {},
      label + ": ",
      badge(v || "n/a", KIND[v] || "")
    )
  );

  for (const li of c.line_items || []) {
    lines.push(
      h(
        "li",
        {},
        `Item “${li.description}”: `,
        badge(li.status, KIND[li.status] || ""),
        li.message ? " " + li.message : ""
      )
    );
  }

  const extra = h(
    "div",
    {},
    h("ul", { class: "match-list" }, lines),
    (d.issues || []).length
      ? h(
          "ul",
          { class: "issues" },
          d.issues.map((x) =>
            h("li", { class: "warning" }, x)
          )
        )
      : null,
    m.dropped
      ? h(
          "div",
          { class: "check-msg" },
          `${m.dropped} line item(s) without a description or quantity were left out of the comparison.`
        )
      : null
  );

  return checkRow(
    t,
    m.state,
    badge(d.status, KIND[d.status] || ""),
    null,
    extra
  );
}

function renderChecks(it) {
  const rows = [];

  const isInvoice = it.data.document_type === "Invoice";

  if (isInvoice) {
    rows.push(dupRow(it.checks.duplicate));
    rows.push(dueRow(it.checks.due));
  }

  const mine = matches.filter(
    (m) => m.poId === it.id || m.invId === it.id
  );

  mine.forEach((m) => rows.push(matchRow(m)));

  if (!rows.length) return null;

  const rerun = h(
    "button",
    {
      class: "btn",
      type: "button",
      onclick: async () => {
        if (isInvoice) {
          await runInvoiceChecks(it);
        }

        for (const m of mine) {
          const po = items.find((x) => x.id === m.poId);
          const inv = items.find((x) => x.id === m.invId);

          if (po && inv) {
            await matchPair(po, inv);
          }
        }
      }
    },
    "Re-run checks with edited values"
  );

  return h(
    "div",
    { class: "checks" },
    h("div", { class: "sub" }, "Automatic checks"),
    rows,
    rerun
  );
}

/* ---------- CSV export ---------- */

function csvCell(v) {
  if (v == null) return "";

  let s = typeof v === "object"
    ? JSON.stringify(v)
    : String(v);

  if (
    typeof v !== "number" &&
    /^([=+@\t\r]|-(?!\d))/.test(s)
  ) {
    s = "'" + s;
  }

  return /[",\r\n]/.test(s)
    ? '"' + s.replace(/"/g, '""') + '"'
    : s;
}

function buildCsv(docs) {
  const fieldKeys = [];
  const itemKeys = [];

  const add = (list, k) => {
    if (!list.includes(k)) list.push(k);
  };

  for (const d of docs) {
    (d.field_specs || []).forEach((s) => add(fieldKeys, s.key));
    (d.item_specs || []).forEach((s) => add(itemKeys, s.key));
  }

  const rows = [[
    "filename",
    "document_type",
    "validation_status",
    ...fieldKeys,
    "line_no",
    ...itemKeys.map((k) => "item_" + k)
  ]];

  for (const d of docs) {
    const base = [
      d.filename,
      d.document_type,
      d.validation && d.validation.status,
      ...fieldKeys.map((k) => (d.fields || {})[k])
    ];

    const lines = d.line_items || [];

    if (!lines.length) {
      rows.push([
        ...base,
        "",
        ...itemKeys.map(() => "")
      ]);
    } else {
      lines.forEach((row, i) => {
        rows.push([
          ...base,
          i + 1,
          ...itemKeys.map((k) => row[k])
        ]);
      });
    }
  }

  return (
    "\ufeff" +
    rows.map((r) => r.map(csvCell).join(",")).join("\r\n") +
    "\r\n"
  );
}

function exportCsv() {
  const docs = items
    .filter((x) => x.status === "done" && x.data)
    .map((x) => x.data);

  if (!docs.length) {
    notify("Extract a document first.", "error");
    return;
  }

  const blob = new Blob(
    [buildCsv(docs)],
    { type: "text/csv;charset=utf-8" }
  );

  const a = h("a", {
    href: URL.createObjectURL(blob),
    download: "extracted-documents.csv"
  });

  document.body.append(a);
  a.click();
  a.remove();

  setTimeout(() => URL.revokeObjectURL(a.href), 1000);

  notify(`CSV with ${docs.length} document(s) downloaded.`);
}

$("#export-csv").onclick = exportCsv;

/* ---------- Application version ---------- */

fetch("/health")
  .then((r) => r.json())
  .then((j) => {
    $("#version").textContent = "v" + j.version;
  })
  .catch(() => {});
