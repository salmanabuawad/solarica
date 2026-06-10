import { AgGridReact } from "ag-grid-react";
import { themeQuartz } from "ag-grid-community";
import { useEffect, useMemo, useRef, useState } from "react";
import { useResponsive } from "../hooks/useResponsive";
import ExcelLikeFilter from "./grid/ExcelLikeFilter";

function setQuickFilter(api, value) {
  if (!api) return;
  if (typeof api.setQuickFilter === "function") {
    api.setQuickFilter(value);
    return;
  }
  if (typeof api.setGridOption === "function") {
    api.setGridOption("quickFilterText", value);
  }
}

export default function SimpleGrid({
  rows,
  columns,
  height = 240,
  onRowClick,
  onRowDoubleClick,
  autoSizeColumns = false,
  enableQuickFilter = false,
  quickFilterPlaceholder = "Search...",
  pagination = false,
  pageSize = 200,
  getRowId,
  getRowStyle,
  rowSelection = "single",
  paginationPageSizeSelector = [20, 50, 100, 200],
  selectedIds,
  onSelectionChange,
  onCellValueChanged,
  stopEditingWhenCellsLoseFocus = true,
  onFilterChanged,
  gridApiRef: externalGridApiRef,
}: any) {
  const { isMobile, isTablet } = useResponsive();
  const compact = isMobile || isTablet;
  const isRtl = typeof document !== "undefined" && document.documentElement.dir === "rtl";
  const gridApiRef = useRef<any>(null);
  const [q, setQ] = useState("");
  const applyingExternalSelection = useRef(false);

  const defaultColDef = useMemo(() => ({
    // Columns are FIXED to the layout defined in the field_configurations
    // table (order/visibility/pin/width applied by applyFieldConfigs in the
    // caller). Users can't resize or drag-reorder them — only the admin's
    // field-configuration screen changes the layout. Sorting + filtering still
    // act on the data.
    resizable: false,
    suppressMovable: true,
    sortable: true,
    // Excel-style filter (checkbox value list + search + OK/Cancel), matching
    // the buildingsmanager project. Opens from the column header menu. Floating
    // filters stay off so the header isn't noisy; active filters still show as
    // chips above the grid (rendered by the caller).
    filter: ExcelLikeFilter,
    floatingFilter: false,
    // NB: deliberately NOT using wrapHeaderText/autoHeaderHeight — they make
    // ag-grid recompute the header height as columns scroll in/out, which made
    // the sort/filter icons jump around during horizontal scroll. Long headers
    // simply truncate (with the tooltip below revealing the full text).
    headerTooltip: undefined as string | undefined,
    minWidth: compact ? 64 : 80,
    // On phones the per-column filter menu button (funnel) crowds the header
    // and overlapped the text; hide it there. Filtering on mobile is via the
    // quick-search box (and active filters still show as chips). Desktop keeps
    // the menu button so per-column filtering stays one click away.
    suppressHeaderMenuButton: compact,
  }), [isMobile, compact]);

  useEffect(() => {
    setQuickFilter(gridApiRef.current, q);
  }, [q]);

  // Push an external selection set into the grid whenever it changes.
  useEffect(() => {
    const api = gridApiRef.current;
    if (!api || !selectedIds) return;
    applyingExternalSelection.current = true;
    try {
      api.forEachNode((node: any) => {
        const id = node.id;
        if (id == null) return;
        const shouldBeSelected = selectedIds.has(id);
        if (node.isSelected() !== shouldBeSelected) {
          node.setSelected(shouldBeSelected, false, "api");
        }
      });
    } finally {
      // The flag is cleared in the onSelectionChanged handler — one tick later.
      setTimeout(() => { applyingExternalSelection.current = false; }, 0);
    }
  }, [selectedIds, rows]);

  return (
    <div style={{ width: "100%" }}>
      {enableQuickFilter && (
        <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: compact ? 6 : 8 }}>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={quickFilterPlaceholder}
            style={{
              width: "100%",
              padding: compact ? "7px 12px" : "10px 12px",
              fontSize: compact ? 14 : undefined,
              borderRadius: 10,
              border: "1px solid #e2e8f0",
              outline: "none"
            }}
          />
        </div>
      )}
      <div style={{ height, width: "100%", borderRadius: 16, overflow: "hidden" }}>
        <AgGridReact<any>
          theme={themeQuartz}
          rowData={rows}
          columnDefs={columns}
          defaultColDef={defaultColDef}
          suppressMovableColumns
          suppressDragLeaveHidesColumns
          animateRows
          enableRtl={isRtl}
          rowSelection={{
            mode: rowSelection === "multiple" ? "multiRow" : "singleRow",
            // checkboxes/headerCheckbox are disabled here on purpose —
            // the consumer (App.tsx) decides where the checkbox lives
            // by adding a custom checkbox column to the
            // column defs. That lets us pin the checkbox to either
            // side of the grid (left vs right edge).
            checkboxes: rowSelection === "multiple",
            headerCheckbox: rowSelection === "multiple",
            selectAll: "filtered",
            checkboxLocation: "selectionColumn",
            enableClickSelection: false,
          }}
          selectionColumnDef={{
            pinned: isRtl ? "right" : "left",
            width: 40,
            minWidth: 40,
            maxWidth: 40,
            sortable: false,
            resizable: false,
            suppressHeaderMenuButton: true,
            suppressMovable: true,
            suppressSizeToFit: true,
            suppressNavigable: true,
            lockPosition: isRtl ? "right" : "left",
            lockPinned: true,
          }}
          pagination={pagination}
          paginationPageSize={pageSize}
          paginationPageSizeSelector={paginationPageSizeSelector}
          getRowId={getRowId}
          getRowStyle={getRowStyle}
          onFilterChanged={(e) => onFilterChanged?.(e.api.getFilterModel?.() ?? {}, e.api)}
          onGridReady={(e) => {
            gridApiRef.current = e.api;
            if (externalGridApiRef) externalGridApiRef.current = e.api;
            setQuickFilter(e.api, q);
            // NOTE: previously this called sizeColumnsToFit() on grid
            // ready + every ResizeObserver tick.  That stretched all
            // columns to fill the viewport, OVERRIDING the per-column
            // widths set in `field_configurations`.  We now respect
            // the configured pixel widths exactly: if the total is
            // wider than the grid the user gets a horizontal scroll;
            // if narrower, there's some empty space on the right.
            // Apply any pre-existing external selection.
            if (selectedIds) {
              applyingExternalSelection.current = true;
              e.api.forEachNode((node: any) => {
                if (node.id != null && selectedIds.has(node.id)) {
                  node.setSelected(true, false, "api");
                }
              });
              setTimeout(() => { applyingExternalSelection.current = false; }, 0);
            }
          }}
          onRowClicked={(e) => onRowClick?.(e.data)}
          onCellDoubleClicked={(e) => onRowDoubleClick?.(e.data, e.column?.getColId?.())}
          onFirstDataRendered={(e) => { if (autoSizeColumns) { try { e.api.autoSizeAllColumns(); } catch { /* ignore */ } } }}
          onCellValueChanged={onCellValueChanged}
          stopEditingWhenCellsLoseFocus={stopEditingWhenCellsLoseFocus}
          onSelectionChanged={(e) => {
            if (!onSelectionChange || applyingExternalSelection.current) return;
            const ids = new Set<string>();
            for (const row of e.api.getSelectedRows()) {
              const id = getRowId ? getRowId({ data: row }) : row.pier_code;
              if (id != null) ids.add(id);
            }
            onSelectionChange(ids);
          }}
        />
      </div>
    </div>
  );
}
