"""Preserve table geometry; attach header semantics only with explicit evidence."""

from __future__ import annotations

import re

from .html_source import Node, whitespace
from .table_semantics import compound_labels


MAX_GRID_SLOTS = 200_000


def parse_table(source: Node, builder, table_kind="data") -> dict:
    table = builder.base(source, "table", text="")
    rows = []
    groups = []
    colgroups = []
    issues = []

    def warn(code, message, node=source):
        issue = {"code": code, "message": message, "source_ref": node.ref}
        issues.append(issue)
        builder.issues.append(issue)

    def add_row(node, group):
        row = builder.base(node, "table_row", text="")
        row.update({"row": len(rows), "row_group": group["id"], "section": group["section"], "cells": []})
        for source_index, child in enumerate(node.children):
            if isinstance(child, Node) and child.tag in {"td", "th"}:
                cell = builder.base(child, "table_cell")
                cell["children"] = builder.serialize_children(child)
                cell.update({"row": row["row"], "cell_type": "header" if child.tag == "th" else "data",
                             "row_group": group["id"], "section": group["section"],
                             "role": "unknown", "confidence": 0.0, "header_refs": {"row": [], "column": [], "other": []}})
                # Keep the full source label and explicit line boundaries for ambiguous headers.
                cell["candidate_labels"] = [
                    {"text": whitespace(line), "role": "unknown", "order": i}
                    for i, line in enumerate(builder.text(child, blocks=True).splitlines()) if whitespace(line)
                ]
                row["cells"].append(cell)
                row["children"].append({"type": "cell_ref", "cell_id": cell["id"], "order": cell["order"]})
            elif isinstance(child, str) and not whitespace(child):
                continue
            else:
                row["children"].extend(builder.serialize_child(child, node, source_index))
                warn("unexpected_row_content", "Content outside table cells retained in its source position", node)
        rows.append(row)
        group["rows"].append(row["row"])
        return {"type": "row_ref", "row": row["row"], "row_id": row["id"], "order": row["order"]}

    implicit = None
    column_cursor = 0
    for index, child in enumerate(source.children):
        if isinstance(child, str) and not whitespace(child):
            continue
        if isinstance(child, Node) and child.tag in {"thead", "tbody", "tfoot"}:
            implicit = None
            group = {"id": f"group_{child.dom_order}", "section": child.tag, "rows": [],
                     "order": child.dom_order, "source_ref": child.ref, "attributes": child.attrs}
            groups.append(group)
            group_block = builder.base(child, "row_group", text="")
            for n, item in enumerate(child.children):
                if isinstance(item, Node) and item.tag == "tr":
                    group_block["children"].append(add_row(item, group))
                elif not isinstance(item, str) or whitespace(item):
                    group_block["children"].extend(builder.serialize_child(item, child, n))
                    warn("unexpected_row_group_content", "Non-row content inside row group retained", child)
            table["children"].append(group_block)
        elif isinstance(child, Node) and child.tag == "tr":
            if implicit is None:
                implicit = {"id": f"group_implicit_{child.dom_order}", "section": "implicit", "rows": [],
                            "order": child.dom_order, "source_ref": source.ref, "attributes": {}}
                groups.append(implicit)
            table["children"].append(add_row(child, implicit))
        else:
            implicit = None
            table["children"].extend(builder.serialize_child(child, source, index))
            if isinstance(child, Node) and child.tag == "colgroup":
                span = 0
                columns = [n for n in child.children if isinstance(n, Node) and n.tag == "col"]
                for n in columns or [child]:
                    raw_span = n.attrs.get("span", "1")
                    if not re.fullmatch(r"\d+", raw_span or "") or (len(raw_span) < 7 and int(raw_span) < 1):
                        warn("invalid_column_group_span", "Invalid colgroup/col span; geometry uses 1", n)
                        span += 1
                    else:
                        span += min(int(raw_span), 1000) if len(raw_span) < 7 else 1000
                        if len(raw_span) >= 7 or int(raw_span) > 1000:
                            warn("clamped_column_group_span", "Column-group span exceeds HTML limit; source value retained", n)
                colgroups.append({"id": f"colgroup_{child.dom_order}", "column": column_cursor,
                                  "colspan": span, "source_ref": child.ref})
                column_cursor += span
            elif isinstance(child, Node) and child.tag not in {"caption", "col"}:
                warn("unexpected_table_content", "Unrecognized table content retained without assigning geometry", child)

    cells = [cell for row in rows for cell in row["cells"]]
    group_by_id = {g["id"]: g for g in groups}
    occupancy = {}
    dense = True
    width = 0
    height = len(rows)

    def span(cell, name, limit):
        value = cell["attributes"].get(name, "1")
        if not re.fullmatch(r"\d+", value or "") or (name == "colspan" and int(value) == 0):
            warn("invalid_cell_span", f"Invalid {name}={value!r}; logical geometry uses 1", source_for(cell))
            return 1
        result = int(value) if len(value) < 7 else limit + 1
        if result > limit:
            warn("clamped_cell_span", f"{name} exceeds HTML limit; original value retained", source_for(cell))
        return min(result, limit)

    def source_for(cell):
        return Node(cell["source_ref"]["tag"], dom_order=cell["source_ref"]["dom_order"],
                    line=cell["source_ref"]["line"], column=cell["source_ref"]["column"])

    rectangles = []
    for row in rows:
        col = 0
        for cell in row["cells"]:
            # Anchor placement follows the first free slot, without shifting a
            # colspan to hide overlaps later in the same row.
            while any(r <= row["row"] < r + rs and c <= col < c + cs
                      for r, c, rs, cs, _ in rectangles):
                col += 1
            rs = span(cell, "rowspan", 65534)
            cs = span(cell, "colspan", 1000)
            group = group_by_id[cell["row_group"]]
            if rs == 0:
                rs = group["rows"][-1] - row["row"] + 1
            if row["row"] + rs - 1 > group["rows"][-1]:
                warn("span_crosses_row_group", "Cell spans beyond its source row group; semantic associations disabled", source_for(cell))
            cell.update({"column": col, "rowspan": rs, "colspan": cs})
            rect = (row["row"], col, rs, cs, cell["id"])
            for r, c, prev_rs, prev_cs, prev_id in rectangles:
                if (rect[0] < r + prev_rs and r < rect[0] + rs and col < c + prev_cs and c < col + cs):
                    warn("overlapping_cells", f"Cells {prev_id} and {cell['id']} overlap; both retained", source_for(cell))
            rectangles.append(rect)
            height = max(height, row["row"] + rs)
            width = max(width, col + cs)
            col += cs

    if height * width > MAX_GRID_SLOTS:
        dense = False
        warn("grid_resource_limit", "Dense grid exceeds limit; exact cell rectangles retained for reconstruction")
    if dense:
        for r, c, rs, cs, cell_id in rectangles:
            for y in range(r, r + rs):
                for x in range(c, c + cs):
                    occupancy.setdefault((y, x), []).append(cell_id)
        grid = [[occupancy.get((r, c), []) for c in range(width)] for r in range(height)]
        if any(not slot for line in grid for slot in line):
            warn("ragged_table", "Logical grid contains uncovered slots; no values were invented")
    else:
        grid = None
    if not rows:
        warn("table_without_rows", "No direct table rows; source children retained")

    # Structural inference starts only after geometry and actual semantic cell
    # content exist. Adapters may provide a context-free first classification.
    if hasattr(builder, "prepare_cells"):
        builder.prepare_cells(source, cells)
    infer_td_headers(source, rows, cells)
    if table_kind is None:
        table_kind, evidence = builder.classify_table(source, rows, cells)
        table["classification_evidence"] = evidence
    table["table_kind"] = table_kind
    if table_kind in {"layout", "form", "annex_form", "key_value"}:
        table.update(rows=rows, row_groups=groups, column_groups=colgroups,
                     grid_shape={"rows": height, "columns": width},
                     semantics={"status": "not_applicable", "reason": table_kind}, issues=issues)
        return table

    bad_geometry = any(i["code"] in {"overlapping_cells", "span_crosses_row_group", "invalid_cell_span",
                                     "clamped_cell_span", "grid_resource_limit", "unexpected_table_content",
                                     "unexpected_row_content", "unexpected_row_group_content"} for i in issues)
    source_ids = {}
    for cell in cells:
        html_id = cell["attributes"].get("id")
        if html_id:
            source_ids.setdefault(html_id, []).append(cell)

    for row in rows:
        all_headers = bool(row["cells"]) and all(c["cell_type"] == "header" for c in row["cells"])
        carried_data = any(c["cell_type"] == "data" and c["row"] <= row["row"] < c["row"] + c["rowspan"] for c in cells)
        leading_band = all(c["cell_type"] == "header" for prev in rows[:row["row"]] for c in prev["cells"])
        for cell in row["cells"]:
            attrs = cell["attributes"]
            scope = attrs.get("scope")
            explicit_axis = attrs.get("data-axis")
            if scope and cell["cell_type"] != "header":
                cell.update(role="ambiguous", confidence=0.0)
                warn("scope_on_data_cell", "scope on td is not evidence for a header association", source_for(cell))
            elif scope in {"row", "col", "rowgroup", "colgroup"}:
                cell.update(role={"row": "row_header", "col": "column_header", "rowgroup": "row_group_header",
                                  "colgroup": "column_group_header"}[scope], confidence=1.0, evidence="scope")
            elif scope:
                cell.update(role="unknown", confidence=0.0)
                warn("invalid_header_scope", f"Unknown header scope: {scope}", source_for(cell))
            elif cell["cell_type"] == "header" and all_headers and not carried_data and (row["section"] == "thead" or leading_band):
                cell.update(role="column_header", confidence=0.9, evidence=cell.get("evidence", "all_header_row"))
            elif cell["cell_type"] == "header" and not any(
                    c["cell_type"] == "data" and c["column"] < cell["column"] + cell["colspan"]
                    and cell["column"] < c["column"] + c["colspan"] for c in cells):
                cell.update(role="row_header", confidence=0.9, evidence="all_header_column")
            elif cell["cell_type"] == "header":
                cell.update(role="unknown", confidence=0.0)
            else:
                cell.update(role="data", confidence=1.0, evidence="td")

            labels = [{"text": text, "role": "unknown", "order": i} for i, text in enumerate(
                compound_labels(cell.get("text_segments", [c["text"] for c in cell["candidate_labels"]]),
                                cell.get("effective_text", cell["text"])))]
            cell["candidate_labels"] = labels
            if cell.get("evidence") in {"emphasized_ordinal_header_row", "explicit_column_label_vocabulary"} and len(labels) == 2 and re.match(
                    r"^(?:\(.+\)$|theo\s)", labels[1]["text"], re.I):
                labels = [{"text": cell.get("effective_text", cell["text"]), "role": "unknown", "order": 0}]
                cell["candidate_labels"] = labels
            corner = cell["row"] == 0 and cell["column"] == 0
            diagonal = bool(re.search(r"linear-gradient|diagonal|border.*(?:rotate|skew)", str(attrs), re.I))
            axis_nodes = [n for n in find_cell_node(source, cell).find() if n.attrs.get("data-axis") in {"row", "column"}]
            if axis_nodes and {n.attrs["data-axis"] for n in axis_nodes} == {"row", "column"}:
                cell.update(role="dual_axis_header", header_kind="dual_axis_header", confidence=1.0,
                            candidate_labels=[{"text": n.text(), "role": n.attrs["data-axis"] + "_header",
                                               "order": n.dom_order, "source_ref": n.ref} for n in axis_nodes],
                            evidence="explicit_data_axis")
            elif len(labels) > 1 and (diagonal or cell["cell_type"] == "header" or explicit_axis or corner and table_kind == "matrix" or
                                      (corner and any(c["cell_type"] == "header" for c in cells)) or
                                      (corner and len(rows) > 1 and all(len(label["text"]) <= 120 for label in labels)
                                       and any(re.fullmatch(r"[\d.,%+−-]+", c.get("effective_text", c["text"])) for c in cells))):
                cell.update(role="ambiguous", header_kind="compound_header", confidence=0.0,
                            candidate_roles=["compound_header", "dual_axis_header"])
                warn("ambiguous_compound_header", "Multiple labels in a possible header cell; axis roles not guessed", source_for(cell))
            if cell["cell_type"] == "header" and cell["role"] == "unknown":
                warn("unresolved_header_role", "Header cell has no reliable row/column role", source_for(cell))

    column_headers = [c for c in cells if c["role"] in {"column_header", "column_group_header"}]
    row_headers = [c for c in cells if c["role"] in {"row_header", "row_group_header"}]
    header_hierarchy = []
    for header in column_headers:
        parents = [h for h in column_headers if h["row"] < header["row"]
                   and h["column"] <= header["column"]
                   and h["column"] + h["colspan"] >= header["column"] + header["colspan"]]
        # All source levels are recorded; no lexical matching of labels.
        header_hierarchy.append({"cell_id": header["id"], "parent_candidates": [h["id"] for h in parents],
                                 "role": "multi_level_header" if parents else "column_header"})

    for cell in cells:
        if cell["role"] != "data":
            continue
        explicit = cell["attributes"].get("headers")
        candidates = []
        unresolved_explicit = False
        if explicit:
            for html_id in explicit.split():
                matches = source_ids.get(html_id, [])
                if len(matches) != 1 or matches[0]["cell_type"] != "header":
                    unresolved_explicit = True
                    warn("unresolved_header_reference", f"Header reference {html_id!r} is missing, duplicated or not th", source_for(cell))
                    candidates.extend(c["id"] for c in matches)
                else:
                    header = matches[0]
                    axis = "row" if header["role"] in {"row_header", "row_group_header"} else (
                        "column" if header["role"] in {"column_header", "column_group_header"} else "other")
                    cell["header_refs"][axis].append(header["id"])
            cell["header_evidence"] = "headers_attribute"
        elif not bad_geometry:
            for h in column_headers:
                group = next((g for g in colgroups if g["column"] <= h["column"] < g["column"] + g["colspan"]), None)
                start, end = ((group["column"], group["column"] + group["colspan"])
                              if h["role"] == "column_group_header" and group else (h["column"], h["column"] + h["colspan"]))
                if h["role"] == "column_group_header" and group is None:
                    continue
                if h["row"] + h["rowspan"] <= cell["row"] and start <= cell["column"] and end >= cell["column"] + cell["colspan"]:
                    cell["header_refs"]["column"].append(h["id"])
                elif h["row"] + h["rowspan"] <= cell["row"] and start < cell["column"] + cell["colspan"] and cell["column"] < end:
                    candidates.append(h["id"])
                    warn("partial_axis_coverage", "Spanning value crosses a column-header boundary; association not asserted", source_for(cell))
            for h in row_headers:
                group = group_by_id[h["row_group"]]
                in_rows = (h["row"] <= cell["row"] and cell["row"] + cell["rowspan"] <= h["row"] + h["rowspan"] if h["role"] == "row_header"
                           else h["row"] <= cell["row"] and cell["row"] + cell["rowspan"] - 1 <= group["rows"][-1]
                           and cell["row_group"] == h["row_group"])
                if in_rows and h["column"] + h["colspan"] <= cell["column"]:
                    cell["header_refs"]["row"].append(h["id"])
                elif h["column"] + h["colspan"] <= cell["column"] and h["row"] < cell["row"] + cell["rowspan"] and cell["row"] < h["row"] + h["rowspan"]:
                    candidates.append(h["id"])
                    warn("partial_axis_coverage", "Spanning value crosses a row-header boundary; association not asserted", source_for(cell))
            aligned = [h for h in column_headers if h["id"] in cell["header_refs"]["column"]]
            for i, earlier in enumerate(aligned):
                for later in aligned[i + 1:]:
                    if any(c["cell_type"] == "data" and earlier["row"] < c["row"] < later["row"]
                           and c["column"] < cell["column"] + cell["colspan"]
                           and cell["column"] < c["column"] + c["colspan"] for c in cells):
                        candidates.extend([earlier["id"], later["id"]])
                        warn("ambiguous_header_bands", "Repeated header bands separated by values; no axis relationship guessed", source_for(cell))
            cell["header_evidence"] = "supported_geometry_and_header_markup"
        if bad_geometry or unresolved_explicit or candidates:
            candidates += [h for values in cell["header_refs"].values() for h in values]
            cell["header_refs"] = {"row": [], "column": [], "other": []}
        cell["header_candidates"] = list(dict.fromkeys(candidates))
        cell["association_status"] = "unknown" if bad_geometry or unresolved_explicit or candidates else (
            "supported" if any(cell["header_refs"].values()) else "unknown")

    if cells and not column_headers and not row_headers and table_kind != "layout":
        warn("unresolved_table_semantics", "No reliable axis headers; geometry and all cell content retained")
    table.update({"rows": rows, "row_groups": groups, "column_groups": colgroups,
                  "grid": grid, "grid_shape": {"rows": height, "columns": width},
                  "grid_status": "ambiguous" if bad_geometry else "preserved",
                  "semantics": {"status": "unknown" if bad_geometry or not (column_headers or row_headers) else "partial",
                                "row_headers": [h["id"] for h in row_headers],
                                "column_headers": [h["id"] for h in column_headers],
                                "header_hierarchy": header_hierarchy}, "issues": issues})
    return table


def infer_td_headers(source, rows, cells):
    """Use explicit typography or reusable column labels, preserving td refs.

    Never promote a numeric row, a diagonal corner or an unmarked prose row.
    A shaded band must precede unshaded body rows, rather than shading alone.
    """
    if len(rows) < 2 or any(c["cell_type"] == "header" for c in cells):
        return
    by_order = {n.dom_order: n for n in source.find()}
    def emphasized(node, inherited=False):
        bold = inherited or node.tag in {"b", "strong"} or bool(re.search(r"font-weight\s*:\s*(?:bold|[7-9]00)", node.attrs.get("style", ""), re.I))
        return all(bold or not whitespace(child) if isinstance(child, str) else emphasized(child, bold) for child in node.children)
    first = rows[0]["cells"]
    nonempty = [c for c in first if c.get("effective_text")]
    ordinal = first and re.fullmatch(r"STT|TT|Số TT", first[0].get("effective_text", ""), re.I)
    labels = {"đơn vị", "đơn vị tính", "giá trị", "ghi chú", "số lượng", "nội dung", "thành tiền", "tên hàng", "đơn giá", "định mức"}
    named = sum(re.sub(r'\s*\([^)]*\)\s*$', '', c.get("effective_text", "")).casefold() in labels for c in nonempty)
    evidence = "emphasized_ordinal_header_row" if ordinal and len(nonempty) >= 2 and all(emphasized(by_order[c["order"]]) for c in nonempty) else (
        "explicit_column_label_vocabulary" if named >= 2 and len(nonempty) == named else None)
    if evidence:
        for c in first:
            c.update(cell_type="header", evidence=evidence)
        return
    band = []
    for row in rows:
        if not row["cells"] or not all(re.search(r"background(?:-color)?\s*:\s*(?!transparent|none)[^;]+", c["attributes"].get("style", ""), re.I)
                                       and c.get("effective_text") and not re.fullmatch(r"[\d.,%]+|X", c["effective_text"]) for c in row["cells"]):
            break
        band.extend(row["cells"])
    if band and len(band) < len(cells) and any(re.fullmatch(r"[\d.,%]+|X", c.get("effective_text", "")) for c in cells[len(band):]):
        for c in band:
            c.update(cell_type="header", evidence="leading_shaded_header_band")


def find_cell_node(table: Node, cell: dict) -> Node:
    return next(node for node in table.find() if node.dom_order == cell["source_ref"]["dom_order"])
