"use strict";

const PAGE_SIZE = 50;
const get = (id) => document.getElementById(id);
const config = JSON.parse(get("configuration").textContent);
const sideNames = ["Alteryx", "Python Phase 1"];

function element(tag, text) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  return node;
}

async function loadTable(key) {
  if (key === null) return { available: false, rows: [], fields: [] };
  const compressed = Uint8Array.from(atob(window.checkpointTables[key]), (char) => char.charCodeAt(0));
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

function valueKey(cell) {
  if (!cell) return null;
  return cell.length === 3 && cell[2].startsWith("numeric:") ? cell[2] : cell;
}

function rowKey(row, indexes) {
  return JSON.stringify(indexes.map((index) => valueKey(row[index])));
}

function buckets(rows, indexes, include) {
  const groups = new Map();
  rows.forEach((row, index) => {
    if (!include(index)) return;
    const signature = rowKey(row, indexes);
    if (!groups.has(signature)) groups.set(signature, { indexes: [], next: 0 });
    groups.get(signature).indexes.push(index);
  });
  return groups;
}

function alignedRows(left, right, common, keys) {
  const indexes = [0, 1].map((side) => common.map((column) => column[side].index));
  const rightByValue = buckets(right, indexes[1], () => true);
  const used = new Set();
  const pairs = left.map((row, index) => {
    if (!common.length) return [index, null];
    const group = rightByValue.get(rowKey(row, indexes[0]));
    const paired = group && group.next < group.indexes.length ? group.indexes[group.next++] : null;
    if (paired !== null) used.add(paired);
    return [index, paired];
  });
  if (keys.length) {
    const selected = [0, 1].map((side) => keys.map((column) => column[side].index));
    const leftByKey = buckets(left, selected[0], (index) => pairs[index][1] === null);
    const rightByKey = buckets(right, selected[1], (index) => !used.has(index));
    for (const [key, group] of leftByKey) {
      const other = rightByKey.get(key);
      // A repeated key does not identify which of several changed rows corresponds.
      if (group.indexes.length === 1 && other?.indexes.length === 1) {
        const paired = other.indexes[0];
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

function sameCell(left, right) {
  return JSON.stringify(valueKey(left)) === JSON.stringify(valueKey(right));
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

function tableSection(tables, side, columns, pairs) {
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
    th.append(element("small", field ? [field.type, "Column " + (field.index + 1)].filter(Boolean).join(" · ") : "Missing field"));
    header.append(th);
  });
  const body = table.createTBody();
  pairs.forEach((pair) => {
    const index = pair[side];
    const row = body.insertRow();
    const th = element("th", index === null ? "—" : String(index + 1));
    th.scope = "row";
    if (pair.includes(null)) th.append(element("small", "Unpaired row"));
    row.append(th);
    columns.forEach((column) => {
      const cell = cellAt(tables[side], index, column[side]);
      const other = cellAt(tables[1 - side], pair[1 - side], column[1 - side]);
      const td = row.insertCell();
      if (!cell) {
        td.className = "missing";
      } else if (!sameCell(cell, other)) {
        td.className = "changed";
        td.setAttribute("aria-label", "Different value");
      }
      writeCell(td, cell);
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

function showTables(tables) {
  const columns = boundColumns(...tables);
  const common = columns.filter((column) => column[0] && column[1]);
  let view = config.status === "match" && config.orderDifferences.length ? "aligned" : "original";
  let pairs = [];
  let page = 0;
  const keys = new Set();

  function render() {
    const totalPages = Math.max(1, Math.ceil(pairs.length / PAGE_SIZE));
    const slice = pairs.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
    const sections = tables.map((_, side) => {
      const visible = view === "aligned" ? columns : columns.filter((column) => column[side])
        .sort((left, right) => left[side].index - right[side].index);
      return tableSection(tables, side, visible, slice);
    });
    get("tables").replaceChildren(...sections);
    get("page").textContent = `Page ${page + 1} of ${totalPages} · ${pairs.length} row pairs`;
    get("previous").disabled = page === 0;
    get("next").disabled = page + 1 >= totalPages;
  }

  function update() {
    const [left, right] = tables.map((table) => table.rows);
    pairs = view === "aligned" ? alignedRows(left, right, common, [...keys])
      : Array.from({ length: Math.max(left.length, right.length) }, (_, index) =>
        [index < left.length ? index : null, index < right.length ? index : null]);
    if (get("only-differences").checked) {
      pairs = pairs.filter((pair) => pair.includes(null) || columns.some((column) =>
        !sameCell(cellAt(tables[0], pair[0], column[0]), cellAt(tables[1], pair[1], column[1]))));
    }
    get("keys").hidden = view !== "aligned" || !common.length;
    page = 0;
    render();
  }

  common.forEach((column) => {
    const label = element("label");
    const field = element("input");
    field.type = "checkbox";
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
  get("previous").addEventListener("click", () => { page -= 1; render(); });
  get("next").addEventListener("click", () => { page += 1; render(); });
  get("comparison").hidden = false;
  update();
}

get("title").textContent = config.title;
document.title = config.title;
get("report-fields").hidden = !config.hasReportFields;
Promise.all(config.tables.map(loadTable)).then((tables) => {
  const changes = config.orderDifferences.join(" and ");
  get("status").textContent = config.status === "match" && changes
    ? `Match after aligning ${changes}.`
    : ({
      match: "Match.",
      incomplete: "Incomplete evidence.",
      mismatch: changes ? `Mismatch · ordering differs for ${changes}.` : "Mismatch in captured data.",
      unassessed: "Captured rows available for inspection. Checkpoint parity was unavailable.",
    }[config.status] ?? config.status);
  showTables(tables);
}).catch((error) => {
  get("status").textContent = "Could not open the captured tables. " + error.message;
});
