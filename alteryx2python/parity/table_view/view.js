"use strict";

const PAGE_SIZE = 50;
const get = (id) => document.getElementById(id);
const sideNames = ["Alteryx", "Python Phase 1"];

function element(tag, text) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  return node;
}

async function loadTable(key) {
  if (key === null) return { available: false, rows: [], fields: [] };
  const encoded = window.checkpointTables?.[key];
  if (!encoded) throw new Error("A captured data file is missing. Keep the generated tables folder together.");
  if (typeof DecompressionStream !== "function") {
    throw new Error("This browser cannot decompress the captured data.");
  }
  const compressed = Uint8Array.from(atob(encoded), (char) => char.charCodeAt(0));
  const stream = new Blob([compressed]).stream().pipeThrough(new DecompressionStream("gzip"));
  const { columns, types, rows } = await new Response(stream).json();
  const occurrences = new Map();
  const fields = columns.map((name, index) => {
    const occurrence = (occurrences.get(name) ?? 0) + 1;
    occurrences.set(name, occurrence);
    return { id: JSON.stringify([name, occurrence]), name, index, type: types[index] };
  });
  return { available: true, fields, rows };
}

function boundColumns(left, right) {
  const columns = new Map();
  [left, right].forEach((side, sideIndex) => {
    side.fields.forEach((field) => {
      if (!columns.has(field.id)) columns.set(field.id, [null, null]);
      columns.get(field.id)[sideIndex] = field;
    });
  });
  return [...columns.values()];
}

function valueKey(cell, coarse, isKey) {
  if (!cell) return null;
  const [kind, value, numeric, normalized] = cell;
  if (coarse && normalized && !(isKey && (kind === "null" || (kind === "string" && value === "")))) {
    return normalized;
  }
  if (numeric?.startsWith("numeric:")) return numeric;
  return normalized ? [kind, value] : cell;
}

function rowKey(row, indexes, coarse, keys) {
  return JSON.stringify(indexes.map((index) => valueKey(row[index], coarse, keys.has(index))));
}

function buckets(rows, indexes, coarse, keys) {
  const groups = new Map();
  rows.forEach((row, index) => {
    const signature = rowKey(row, indexes, coarse, keys);
    if (!groups.has(signature)) groups.set(signature, { indexes: [], next: 0 });
    groups.get(signature).indexes.push(index);
  });
  return groups;
}

function alignedRows(left, right, common, keys, coarse) {
  const indexes = [0, 1].map((side) => common.map((column) => column[side].index));
  const selected = [0, 1].map((side) => keys.map((column) => column[side].index));
  const keyIndexes = selected.map((list) => new Set(list));
  const rightByValue = buckets(right, indexes[1], coarse, keyIndexes[1]);
  const used = new Set();
  const pairs = left.map((row, index) => {
    if (!common.length) return [index, null];
    const group = rightByValue.get(rowKey(row, indexes[0], coarse, keyIndexes[0]));
    const paired = group && group.next < group.indexes.length ? group.indexes[group.next++] : null;
    if (paired !== null) used.add(paired);
    return [index, paired];
  });
  if (keys.length) {
    const leftByKey = buckets(left, selected[0], coarse, keyIndexes[0]);
    const rightByKey = buckets(right, selected[1], coarse, keyIndexes[1]);
    for (const [key, group] of leftByKey) {
      const other = rightByKey.get(key);
      // A repeated key does not identify which of several changed rows corresponds.
      if (group.indexes.length === 1 && other?.indexes.length === 1) {
        const paired = other.indexes[0];
        if (pairs[group.indexes[0]][1] !== null || used.has(paired)) continue;
        pairs[group.indexes[0]][1] = paired;
        used.add(paired);
      }
    }
  }
  right.forEach((_, index) => {
    if (!used.has(index)) pairs.push([null, index]);
  });
  return pairs;
}

function cellAt(table, rowIndex, field) {
  return rowIndex === null || !field ? undefined : table.rows[rowIndex][field.index];
}

function sameCell(left, right, coarse, isKey) {
  const a = valueKey(left, coarse, isKey);
  const b = valueKey(right, coarse, isKey);
  return a === b || (Array.isArray(a) && Array.isArray(b)
    && a.length === b.length && a.every((value, index) => value === b[index]));
}

function differencesOnly(tables, columns, pairs, coarse, keys) {
  const changed = new Set(columns.filter((column) => !column[0] || !column[1]));
  const rows = [];
  for (const pair of pairs) {
    let different = pair.includes(null);
    for (const column of columns) {
      if (!sameCell(cellAt(tables[0], pair[0], column[0]), cellAt(tables[1], pair[1], column[1]), coarse, keys.has(column))) {
        changed.add(column);
        different = true;
      }
    }
    if (different) rows.push(pair);
  }
  return { rows, columns: columns.filter((column) => changed.has(column)) };
}

function writeCell(node, cell) {
  if (!cell || cell[0] === "null") {
    node.append(element("span", cell ? "NULL" : "—"));
    return;
  }
  const [kind, value] = cell;
  const text = String(value);
  node.title = kind;
  if (text.length > 180 || text.includes("\n")) {
    const details = element("details");
    details.append(element("summary", text.slice(0, 100) + (text.length > 100 ? "…" : "")));
    details.append(element("pre", text));
    node.append(details);
  } else {
    const span = element("span", text === "" ? '""' : text);
    node.append(span);
  }
}

function describeValueDifference(node, cell, other) {
  if (!other) return;
  if (cell[0] !== other[0]) {
    node.append(element("small", cell[0]));
  } else if (cell[0] === "string" && cell[1].trim() === other[1].trim()) {
    const visible = cell[1].length <= 120
      ? JSON.stringify(cell[1]).replaceAll(" ", "·").replaceAll("\u00a0", "\\u00a0")
      : `${cell[1].length - cell[1].trimStart().length} leading and ${cell[1].length - cell[1].trimEnd().length} trailing whitespace characters`;
    node.append(element("small", visible));
  }
}

function tableSection(tables, side, columns, pairs, keys) {
  const section = element("section");
  section.append(element("h2", `${sideNames[side]} · ${tables[side].available ? tables[side].rows.length + " rows" : "capture unavailable"}`));
  if (!tables[side].available) return section;

  const wrapper = element("div");
  wrapper.className = "scroll";
  wrapper.tabIndex = 0;
  wrapper.setAttribute("aria-label", sideNames[side] + " rows");
  const table = element("table");
  table.setAttribute("aria-label", sideNames[side] + " captured rows");
  const header = table.createTHead().insertRow();
  const rowHeader = element("th", "Original row");
  rowHeader.scope = "col";
  header.append(rowHeader);
  columns.forEach((column) => {
    const field = column[side];
    const th = element("th", (field ?? column[1 - side]).name);
    th.scope = "col";
    th.title = field?.type ?? "";
    th.append(element("small", field ? "Column " + (field.index + 1) : "Missing field"));
    if (!column[0] || !column[1]) th.dataset.result = "unmatched";
    header.append(th);
  });
  const body = table.createTBody();
  pairs.forEach((pair) => {
    const index = pair[side];
    const row = body.insertRow();
    const th = element("th", index === null ? "—" : String(index + 1));
    th.scope = "row";
    const unpaired = pair.includes(null);
    if (unpaired) {
      th.dataset.result = "unmatched";
      th.append(element("small", "Unpaired row"));
    }
    row.append(th);
    columns.forEach((column) => {
      const cell = cellAt(tables[side], index, column[side]);
      const other = cellAt(tables[1 - side], pair[1 - side], column[1 - side]);
      const td = row.insertCell();
      if (unpaired || !cell || !other) {
        td.dataset.result = "unmatched";
        td.setAttribute("aria-description", "Unmatched");
      } else if (!sameCell(cell, other, false, keys.has(column))) {
        const coarseMatch = sameCell(cell, other, true, keys.has(column));
        td.dataset.result = coarseMatch ? "coarse-match" : "unmatched";
        td.setAttribute("aria-description", coarseMatch ? "Coarse match" : "Different value");
      }
      writeCell(td, cell);
      if (cell && other && td.dataset.result) describeValueDifference(td, cell, other);
    });
  });
  wrapper.append(table);
  section.append(wrapper);
  if (!pairs.length) {
    const empty = element("p", "No rows in this view.");
    empty.className = "empty";
    section.append(empty);
  }
  return section;
}

function showTables(config, tables) {
  const columns = boundColumns(...tables);
  const common = columns.filter((column) => column[0] && column[1]);
  let view = config.preserveRowOrder ? "original" : "aligned";
  let pairs = [];
  let filteredColumns = null;
  let page = 0;
  const configured = config.alignmentKeys ?? [];
  const defaults = common.filter((column) => configured.includes(column[0].name));
  const keys = new Set(defaults.length === configured.length &&
    new Set(defaults.map((column) => column[0].name)).size === configured.length ? defaults : []);

  function render() {
    const totalPages = Math.max(1, Math.ceil(pairs.length / PAGE_SIZE));
    const slice = pairs.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
    const sections = tables.map((_, side) => {
      const visible = filteredColumns ?? (view === "aligned" ? columns : columns.filter((column) => column[side])
        .sort((left, right) => left[side].index - right[side].index));
      return tableSection(tables, side, visible, slice, keys);
    });
    get("tables").replaceChildren(...sections);
    const fieldCount = filteredColumns ? ` · ${filteredColumns.length} differing columns` : "";
    get("page").textContent = `Page ${page + 1} of ${totalPages} · ${pairs.length} row pairs${fieldCount}`;
    get("previous").disabled = page === 0;
    get("next").disabled = page + 1 >= totalPages;
  }

  function update() {
    const coarse = config.hasCoarseRules && !get("include-representation").checked;
    const [left, right] = tables.map((table) => table.rows);
    pairs = view === "aligned" ? alignedRows(left, right, common, [...keys], config.hasCoarseRules)
      : Array.from({ length: Math.max(left.length, right.length) }, (_, index) =>
        [index < left.length ? index : null, index < right.length ? index : null]);
    const differences = get("only-differences").checked ? differencesOnly(tables, columns, pairs, coarse, keys) : null;
    filteredColumns = differences?.columns ?? null;
    if (differences) pairs = differences.rows;
    get("keys").hidden = view !== "aligned" || !common.length;
    page = 0;
    render();
  }

  common.forEach((column) => {
    const label = element("label");
    const field = element("input");
    field.type = "checkbox";
    field.checked = keys.has(column);
    field.addEventListener("change", () => {
      if (field.checked) keys.add(column);
      else keys.delete(column);
      update();
    });
    label.append(field, " " + column[0].name + " · column " + (column[0].index + 1));
    get("key-fields").append(label);
  });
  get("view").value = view;
  get("view").addEventListener("change", (event) => { view = event.target.value; update(); });
  get("only-differences").addEventListener("change", update);
  get("include-representation").addEventListener("change", update);
  get("previous").addEventListener("click", () => { page -= 1; render(); });
  get("next").addEventListener("click", () => { page += 1; render(); });
  update();
  get("comparison").hidden = false;
}

async function initialize() {
  const source = get("configuration").textContent.trim();
  if (source === "__CHECKPOINT_CONFIG__") {
    get("status").textContent = "This is the HTML template. Open an anchor’s HTML link from your Step 3 comparison-summary.md.";
    return;
  }
  get("report-link").hidden = false;
  get("status").textContent = "Loading captured rows…";
  const config = JSON.parse(source);
  get("title").textContent = config.title;
  document.title = config.title;
  const tables = await Promise.all(config.tables.map(loadTable));
  showTables(config, tables);
  get("report-fields").hidden = !config.hasReportFields;
  get("representation").hidden = !config.hasCoarseRules;
  get("legend").hidden = !(config.hasCoarseRules || config.status === "mismatch" || config.status === "incomplete");
  get("coarse-legend").hidden = !config.hasCoarseRules;
  if (config.status === "coarse_match") get("status").dataset.result = "coarse-match";
  if (config.status === "mismatch") get("status").dataset.result = "unmatched";
  const changes = config.orderDifferences.join(" and ");
  get("status").textContent = config.status === "match" && changes
    ? `Match after aligning ${changes}.`
    : ({
      match: "Match.",
      coarse_match: "Coarse match. Enable representation differences to review the exact values.",
      incomplete: "Incomplete evidence.",
      mismatch: changes ? `Mismatch · ordering differs for ${changes}.` : "Mismatch in captured data.",
      unassessed: "Captured rows available for inspection. Checkpoint parity was unavailable.",
    }[config.status] ?? config.status);
}

initialize().catch((error) => {
  get("comparison").hidden = true;
  get("status").textContent = "Could not open the captured tables. " + error.message;
});
