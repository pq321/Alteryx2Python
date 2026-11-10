/* Alteryx2Python visual workflow editor - vanilla JS + SVG, no dependencies. */
(function () {
  "use strict";

  var NODE_W = 148, NODE_H = 54, ANCHOR_R = 5.5;

  var state = {
    tools: [],
    nodes: [],            /* {id, type, x, y, config} */
    edges: [],            /* {from, fromAnchor, to, toAnchor} */
    selected: null,       /* node id */
    nextId: 1,
    dragging: null,
    linking: null,
    lastCompile: null
  };

  var svg = document.getElementById("canvas");
  var paletteEl = document.getElementById("palette");
  var configBody = document.getElementById("configBody");
  var configTitle = document.getElementById("configTitle");
  var statusEl = document.getElementById("status");

  function setStatus(text, isError) {
    statusEl.textContent = text;
    statusEl.style.color = isError ? "#ffb4a8" : "#bfe3ff";
  }

  function toolByType(type) {
    for (var i = 0; i < state.tools.length; i++) if (state.tools[i].type === type) return state.tools[i];
    return null;
  }

  /* ---------------- palette ---------------- */

  function buildPalette() {
    var groups = {};
    state.tools.forEach(function (tool) {
      (groups[tool.category] = groups[tool.category] || []).push(tool);
    });
    Object.keys(groups).forEach(function (category) {
      var h = document.createElement("h4");
      h.textContent = category;
      paletteEl.appendChild(h);
      groups[category].forEach(function (tool) {
        var item = document.createElement("div");
        item.className = "paletteItem";
        item.textContent = tool.label;
        item.draggable = true;
        item.addEventListener("dragstart", function (event) {
          event.dataTransfer.setData("text/plain", tool.type);
        });
        item.addEventListener("dblclick", function () { addNode(tool.type, 120, 140); });
        paletteEl.appendChild(item);
      });
    });
  }

  var canvasWrap = document.getElementById("canvasWrap");
  canvasWrap.addEventListener("dragover", function (event) { event.preventDefault(); });
  canvasWrap.addEventListener("drop", function (event) {
    event.preventDefault();
    var type = event.dataTransfer.getData("text/plain");
    if (!type) return;
    var point = toCanvasPoint(event);
    addNode(type, point.x, point.y);
  });

  function toCanvasPoint(event) {
    var pt = svg.createSVGPoint();
    pt.x = event.clientX; pt.y = event.clientY;
    return pt.matrixTransform(svg.getScreenCTM().inverse());
  }

  /* ---------------- nodes / edges ---------------- */

  function addNode(type, x, y) {
    var tool = toolByType(type);
    if (!tool) return;
    var node = {
      id: String(state.nextId++),
      type: type,
      x: Math.round(x - NODE_W / 2),
      y: Math.round(y - NODE_H / 2),
      config: JSON.parse(JSON.stringify(tool.defaults || {}))
    };
    state.nodes.push(node);
    render();
    selectNode(node.id);
  }

  function removeNode(id) {
    state.nodes = state.nodes.filter(function (n) { return n.id !== id; });
    state.edges = state.edges.filter(function (e) { return e.from !== id && e.to !== id; });
    if (state.selected === id) { state.selected = null; renderConfig(); }
    render();
  }

  function anchorPos(node, anchor, isInput) {
    var tool = toolByType(node.type);
    var list = isInput ? (tool ? tool.inputs : []) : (tool ? tool.outputs : []);
    var index = Math.max(0, list.indexOf(anchor));
    var count = Math.max(1, list.length);
    var step = (NODE_H - 16) / count;
    return {
      x: node.x + (isInput ? 0 : NODE_W),
      y: node.y + 8 + step * index + step / 2
    };
  }

  /* ---------------- rendering ---------------- */

  function render() {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var defs = document.createElementNS(svgNS(), "defs");
    svg.appendChild(defs);

    state.edges.forEach(function (edge, index) {
      var fromNode = findNode(edge.from), toNode = findNode(edge.to);
      if (!fromNode || !toNode) return;
      var a = anchorPos(fromNode, edge.fromAnchor, false);
      var b = anchorPos(toNode, edge.toAnchor, true);
      var path = document.createElementNS(svgNS(), "path");
      path.setAttribute("d", bezier(a, b));
      path.setAttribute("class", "edgePath");
      path.addEventListener("dblclick", function () {
        state.edges.splice(index, 1); render();
      });
      svg.appendChild(path);
      var label = document.createElementNS(svgNS(), "text");
      label.setAttribute("x", (a.x + b.x) / 2);
      label.setAttribute("y", (a.y + b.y) / 2 - 6);
      label.setAttribute("text-anchor", "middle");
      label.setAttribute("font-size", "9");
      label.setAttribute("fill", "#6f8797");
      label.textContent = edge.fromAnchor === "Output" ? "" : edge.fromAnchor;
      svg.appendChild(label);
    });

    state.nodes.forEach(function (node) {
      var group = document.createElementNS(svgNS(), "g");
      group.setAttribute("class", "node" + (state.selected === node.id ? " selected" : ""));
      group.setAttribute("transform", "translate(" + node.x + "," + node.y + ")");

      var rect = document.createElementNS(svgNS(), "rect");
      rect.setAttribute("class", "body");
      rect.setAttribute("width", NODE_W); rect.setAttribute("height", NODE_H);
      rect.setAttribute("rx", 8);
      group.appendChild(rect);

      var title = document.createElementNS(svgNS(), "text");
      title.setAttribute("class", "title");
      title.setAttribute("x", NODE_W / 2); title.setAttribute("y", 22);
      title.setAttribute("text-anchor", "middle");
      var tool = toolByType(node.type);
      title.textContent = tool ? tool.label : node.type;
      group.appendChild(title);

      var sub = document.createElementNS(svgNS(), "text");
      sub.setAttribute("class", "anchorLabel");
      sub.setAttribute("x", NODE_W / 2); sub.setAttribute("y", 38);
      sub.setAttribute("text-anchor", "middle");
      sub.textContent = nodeSummary(node);
      group.appendChild(sub);

      group.addEventListener("mousedown", function (event) {
        if (event.target.classList.contains("anchor")) return;
        selectNode(node.id);
        state.dragging = { id: node.id, dx: event.clientX, dy: event.clientY, ox: node.x, oy: node.y };
        event.preventDefault();
      });
      svg.appendChild(group);

      var inputs = tool ? tool.inputs : [];
      var outputs = tool ? tool.outputs : [];
      if (tool && tool.multiInput) inputs = ["Input"];
      inputs.forEach(function (anchor) {
        var pos = anchorPos(node, anchor, true);
        drawAnchor(group, node, pos, anchor, true);
      });
      outputs.forEach(function (anchor) {
        var pos = anchorPos(node, anchor, false);
        drawAnchor(group, node, pos, anchor, false);
      });
    });
  }

  function nodeSummary(node) {
    var config = node.config || {};
    if (node.type === "TextInput") return (config.fields || []).join(", ");
    if (node.type === "Filter" || node.type === "Formula") {
      var expr = node.type === "Filter" ? config.expression : (config.expressions || [{}])[0].expression;
      return truncate(expr, 22);
    }
    if (node.type === "DbFileOutput") return truncate(config.file || "output.csv", 24);
    if (node.type === "Summarize") return (config.actions || []).length + " actions";
    return "";
  }

  function truncate(value, n) {
    value = String(value || "");
    return value.length > n ? value.slice(0, n - 1) + "…" : value;
  }

  function drawAnchor(group, node, pos, anchor, isInput) {
    var circle = document.createElementNS(svgNS(), "circle");
    circle.setAttribute("class", "anchor");
    circle.setAttribute("cx", pos.x - node.x);
    circle.setAttribute("cy", pos.y - node.y);
    circle.setAttribute("r", ANCHOR_R);
    group.appendChild(circle);
    var label = document.createElementNS(svgNS(), "text");
    label.setAttribute("class", "anchorLabel");
    label.setAttribute("x", pos.x - node.x + (isInput ? 9 : -9));
    label.setAttribute("y", pos.y - node.y + 3);
    label.setAttribute("text-anchor", isInput ? "start" : "end");
    label.textContent = anchor;
    group.appendChild(label);

    circle.addEventListener("mousedown", function (event) {
      event.stopPropagation();
      if (!isInput) {
        state.linking = { from: node.id, fromAnchor: anchor };
        setStatus("drag to an input anchor…");
      }
    });
    circle.addEventListener("mouseup", function (event) {
      event.stopPropagation();
      if (isInput && state.linking && state.linking.from !== node.id) {
        state.edges.push({
          from: state.linking.from,
          fromAnchor: state.linking.fromAnchor,
          to: node.id,
          toAnchor: anchor
        });
        state.linking = null;
        setStatus("");
        render();
      }
    });
  }

  function bezier(a, b) {
    var dx = Math.max(36, Math.abs(b.x - a.x) / 2);
    return "M " + a.x + " " + a.y +
      " C " + (a.x + dx) + " " + a.y + ", " + (b.x - dx) + " " + b.y + ", " + b.x + " " + b.y;
  }

  function svgNS() { return "http://www.w3.org/2000/svg"; }
  function findNode(id) {
    for (var i = 0; i < state.nodes.length; i++) if (state.nodes[i].id === id) return state.nodes[i];
    return null;
  }

  /* ---------------- global mouse handlers ---------------- */

  document.addEventListener("mousemove", function (event) {
    if (state.dragging) {
      var node = findNode(state.dragging.id);
      if (!node) return;
      var scale = svg.getScreenCTM().a;
      node.x = state.dragging.ox + (event.clientX - state.dragging.dx) / scale;
      node.y = state.dragging.oy + (event.clientY - state.dragging.dy) / scale;
      render();
    }
  });
  document.addEventListener("mouseup", function () {
    state.dragging = null;
    state.linking = null;
  });
  document.addEventListener("keydown", function (event) {
    if ((event.key === "Delete" || event.key === "Backspace") && state.selected) {
      var active = document.activeElement && document.activeElement.tagName;
      if (active === "INPUT" || active === "SELECT" || active === "TEXTAREA") return;
      removeNode(state.selected);
    }
  });

  /* ---------------- config panel ---------------- */

  function selectNode(id) {
    state.selected = id;
    render();
    renderConfig();
  }

  function renderConfig() {
    configBody.innerHTML = "";
    var node = state.selected ? findNode(state.selected) : null;
    if (!node) {
      configTitle.textContent = "Configuration";
      configBody.innerHTML = '<p class="hint">Select a node to configure it. Drag tools from the palette; drag between anchors to connect; double-click an edge to delete it.</p>';
      return;
    }
    var tool = toolByType(node.type);
    configTitle.textContent = tool ? tool.label : node.type;
    var builders = {
      TextInput: buildTextInputConfig,
      DbFileOutput: buildSimpleConfig,
      Filter: buildSimpleConfig,
      Unique: buildSimpleConfig,
      Formula: buildFormulaConfig,
      Select: buildSelectConfig,
      Sort: buildFieldOrderConfig,
      Summarize: buildSummarizeConfig,
      Join: buildSimpleConfig,
      RegEx: buildSimpleConfig,
      DateTime: buildSimpleConfig,
      MultiRowFormula: buildSimpleConfig,
      Sample: buildSimpleConfig,
      CrossTab: buildSimpleConfig,
      Transpose: buildListFieldsConfig,
      RecordID: buildSimpleConfig,
      RunningTotal: buildSimpleConfig,
      Rank: buildSimpleConfig,
      TextToColumns: buildSimpleConfig
    };
    (builders[node.type] || buildSimpleConfig)(node, tool);
  }

  function field(labelText, value, onChange) {
    var row = document.createElement("div");
    row.className = "cfgRow";
    var label = document.createElement("label");
    label.textContent = labelText;
    var input = document.createElement("input");
    input.value = value == null ? "" : value;
    input.addEventListener("input", function () { onChange(input.value); updateNodeSummary(); });
    row.appendChild(label); row.appendChild(input);
    configBody.appendChild(row);
    return input;
  }

  function buildSimpleConfig(node) {
    var config = node.config;
    Object.keys(config).forEach(function (key) {
      if (typeof config[key] === "string" || typeof config[key] === "number") {
        field(key, config[key], function (value) { config[key] = value; });
      }
    });
  }

  function buildTextInputConfig(node) {
    var config = node.config;
    field("Columns (comma separated)", (config.fields || []).join(","), function (value) {
      config.fields = value.split(",").map(function (s) { return s.trim(); }).filter(Boolean);
    });
    var box = document.createElement("div");
    box.className = "cfgRow";
    var label = document.createElement("label");
    label.textContent = "Data (one row per line, cells comma separated)";
    var area = document.createElement("textarea");
    area.style.width = "100%"; area.style.height = "110px";
    area.value = (config.rows || []).map(function (row) { return row.join(","); }).join("\n");
    area.addEventListener("input", function () {
      config.rows = area.value.split("\n").filter(function (line) { return line.trim() !== ""; })
        .map(function (line) { return line.split(","); });
      updateNodeSummary();
    });
    box.appendChild(label); box.appendChild(area);
    configBody.appendChild(box);
  }

  function listEditor(container, items, renderEntry, newItem, key) {
    var wrap = document.createElement("div");
    wrap.className = "listEditor";
    function redraw() {
      wrap.innerHTML = "";
      items.forEach(function (item, index) {
        var entry = document.createElement("div");
        entry.className = "entry";
        renderEntry(entry, item, function () { items.splice(index, 1); redraw(); updateNodeSummary(); });
        wrap.appendChild(entry);
      });
      var add = document.createElement("button");
      add.className = "addRowBtn";
      add.textContent = "+ add";
      add.addEventListener("click", function () { items.push(newItem()); redraw(); updateNodeSummary(); });
      wrap.appendChild(add);
    }
    redraw();
    container.appendChild(wrap);
  }

  function buildFormulaConfig(node) {
    var config = node.config;
    config.expressions = config.expressions || [];
    listEditor(configBody, config.expressions,
      function (entry, item, remove) {
        entry.appendChild(smallInput(item, "field", "field"));
        var typeSel = smallSelect(item, "type", ["String", "Double", "Int64", "Bool", "Date", "DateTime"]);
        entry.appendChild(typeSel);
        entry.appendChild(smallInput(item, "expression", "expression"));
        entry.appendChild(removeBtn(remove));
      },
      function () { return { field: "NewField", type: "Double", size: "", expression: "[Col2]" }; });
  }

  function buildSelectConfig(node) {
    var config = node.config;
    config.fields = config.fields || [];
    listEditor(configBody, config.fields,
      function (entry, item, remove) {
        entry.appendChild(smallInput(item, "field", "field"));
        var sel = smallSelect(item, "selected", ["True", "False"]);
        entry.appendChild(sel);
        entry.appendChild(removeBtn(remove));
      },
      function () { return { field: "Col1", selected: "True" }; });
    var note = document.createElement("p");
    note.className = "hint";
    note.textContent = "includeUnknown keeps every unlisted column.";
    configBody.appendChild(note);
    var check = document.createElement("input");
    check.type = "checkbox";
    check.checked = !!config.includeUnknown;
    check.addEventListener("change", function () { config.includeUnknown = check.checked; });
    var lbl = document.createElement("label");
    lbl.appendChild(check);
    lbl.appendChild(document.createTextNode(" includeUnknown"));
    configBody.appendChild(lbl);
  }

  function buildFieldOrderConfig(node) {
    var config = node.config;
    config.order = config.order || [];
    listEditor(configBody, config.order,
      function (entry, item, remove) {
        entry.appendChild(smallInput(item, "field", "field"));
        entry.appendChild(smallSelect(item, "order", ["Ascending", "Descending"]));
        entry.appendChild(removeBtn(remove));
      },
      function () { return { field: "Col2", order: "Ascending" }; });
  }

  function buildSummarizeConfig(node) {
    var config = node.config;
    config.actions = config.actions || [];
    listEditor(configBody, config.actions,
      function (entry, item, remove) {
        entry.appendChild(smallInput(item, "field", "field"));
        entry.appendChild(smallSelect(item, "action", ["GroupBy", "Sum", "Avg", "Min", "Max", "Count"]));
        entry.appendChild(smallInput(item, "rename", "rename"));
        entry.appendChild(removeBtn(remove));
      },
      function () { return { field: "Col2", action: "Sum", rename: "" }; });
  }

  function buildListFieldsConfig(node) {
    var config = node.config;
    ["keyFields", "dataFields"].forEach(function (key) {
      var label = document.createElement("label");
      label.textContent = key;
      configBody.appendChild(label);
      field(key, (config[key] || []).join(","), function (value) {
        config[key] = value.split(",").map(function (s) { return s.trim(); }).filter(Boolean);
      });
    });
  }

  function smallInput(item, key, placeholder) {
    var input = document.createElement("input");
    input.placeholder = placeholder;
    input.value = item[key] == null ? "" : item[key];
    input.addEventListener("input", function () { item[key] = input.value; });
    return input;
  }

  function smallSelect(item, key, options) {
    var select = document.createElement("select");
    options.forEach(function (option) {
      var el = document.createElement("option");
      el.value = option; el.textContent = option;
      select.appendChild(el);
    });
    select.value = item[key] || options[0];
    select.addEventListener("change", function () { item[key] = select.value; });
    return select;
  }

  function removeBtn(onRemove) {
    var button = document.createElement("button");
    button.textContent = "×";
    button.addEventListener("click", onRemove);
    return button;
  }

  function updateNodeSummary() { render(); }

  /* ---------------- compile / run ---------------- */

  function graphPayload() {
    return {
      name: document.getElementById("wfName").value || "workflow",
      nodes: state.nodes,
      edges: state.edges
    };
  }

  function post(path, payload, onDone, onError) {
    fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }).then(function (response) {
      return response.json().then(function (data) { return { ok: response.ok, data: data }; });
    }).then(function (result) {
      if (result.ok) onDone(result.data); else onError(result.data.error || "request failed");
    }).catch(function (error) { onError(String(error)); });
  }

  function showCompile(result) {
    state.lastCompile = result;
    document.getElementById("tabPython").textContent = result.python;
    document.getElementById("tabYxmd").textContent = result.yxmd;
    if (result.unsupported && result.unsupported.length) {
      setStatus("compiled with warnings: " + result.unsupported.length + " node(s) not standalone-translatable", true);
    } else {
      setStatus("compiled ok - yxmd + python generated");
    }
    switchTab("python");
  }

  function showRun(result) {
    state.lastCompile = result;
    document.getElementById("tabPython").textContent = result.python;
    document.getElementById("tabYxmd").textContent = result.yxmd;
    var container = document.getElementById("tabResult");
    container.innerHTML = "";
    var table = document.createElement("table");
    table.className = "result";
    var headRow = document.createElement("tr");
    (result.columns || []).forEach(function (column) {
      var th = document.createElement("th");
      th.textContent = column;
      headRow.appendChild(th);
    });
    table.appendChild(headRow);
    (result.rows || []).forEach(function (row) {
      var tr = document.createElement("tr");
      row.forEach(function (cell) {
        var td = document.createElement("td");
        td.textContent = cell == null ? "" : String(cell);
        tr.appendChild(td);
      });
      table.appendChild(tr);
    });
    container.appendChild(table);
    var info = document.createElement("p");
    info.className = "hint";
    info.textContent = (result.rows || []).length + " rows -> " + result.output_file;
    container.appendChild(info);
    setStatus("run ok - " + (result.rows || []).length + " rows");
    switchTab("result");
  }

  function switchTab(name) {
    var pages = document.querySelectorAll(".tabPage");
    for (var i = 0; i < pages.length; i++) pages[i].classList.remove("active");
    var buttons = document.querySelectorAll("#tabs button[data-tab]");
    for (var j = 0; j < buttons.length; j++) buttons[j].classList.remove("active");
    var page = document.getElementById("tab" + name.charAt(0).toUpperCase() + name.slice(1));
    if (page) page.classList.add("active");
    var button = document.querySelector("#tabs button[data-tab=" + name + "]");
    if (button) button.classList.add("active");
  }

  document.querySelectorAll("#tabs button[data-tab]").forEach(function (button) {
    button.addEventListener("click", function () { switchTab(button.dataset.tab); });
  });

  function download(filename, text) {
    var element = document.createElement("a");
    element.setAttribute("href", "data:text/plain;charset=utf-8," + encodeURIComponent(text));
    element.setAttribute("download", filename);
    element.style.display = "none";
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  }

  document.getElementById("btnCompile").addEventListener("click", function () {
    setStatus("compiling…");
    post("/api/compile", graphPayload(), showCompile, function (error) { setStatus("compile failed: " + error, true); });
  });
  document.getElementById("btnRun").addEventListener("click", function () {
    setStatus("running…");
    post("/api/run", graphPayload(), showRun, function (error) { setStatus("run failed: " + error, true); });
  });
  document.getElementById("btnClear").addEventListener("click", function () {
    state.nodes = []; state.edges = []; state.selected = null; state.lastCompile = null;
    render(); renderConfig(); setStatus("");
  });
  document.getElementById("btnDownloadPy").addEventListener("click", function () {
    if (state.lastCompile) download(graphPayload().name + ".py", state.lastCompile.python || "");
  });
  document.getElementById("btnDownloadYxmd").addEventListener("click", function () {
    if (state.lastCompile) download(graphPayload().name + ".yxmd", state.lastCompile.yxmd || "");
  });

  /* ---------------- boot ---------------- */

  fetch("/api/tools").then(function (r) { return r.json(); }).then(function (data) {
    state.tools = data.tools || [];
    buildPalette();
    render();
    renderConfig();
    setStatus("ready - drag a tool onto the canvas");
  });
})();
