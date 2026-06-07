/**
 * ExcelLikeFilter — AG Grid React custom filter (Excel-style), ported from the
 * buildingsmanager project so Solarica's grids filter the same way: a checkbox
 * list of the column's unique values with a search box, "select all", and
 * OK/Cancel. Localised (en/he/ar) and direction-aware.
 *
 * Uses the reactive custom-component API: CustomFilterProps + useGridFilter.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useGridFilter } from "ag-grid-react";
import type { CustomFilterProps, IAfterGuiAttachedParams, IDoesFilterPassParams } from "ag-grid-community";

export interface ExcelLikeFilterModel {
  values: string[]; // display values that remain checked (visible)
}

const ExcelLikeFilter = ({
  model,
  onModelChange,
  onUiChange,
  api,
  getValue,
}: CustomFilterProps<any, any, ExcelLikeFilterModel>) => {
  const { t, i18n } = useTranslation();
  const rtl = i18n.language === "he" || i18n.language === "ar";
  const BLANK_LABEL = `(${t("grid.blank", "Blanks")})`;

  const toDisplay = useCallback((raw: unknown): string => {
    if (raw === null || raw === undefined || raw === "") return BLANK_LABEL;
    return String(raw);
  }, [BLANK_LABEL]);

  const hidePopupRef = useRef<(() => void) | undefined>();

  const collectAllValues = useCallback((): string[] => {
    const seen = new Set<string>();
    api.forEachNode((node: any) => {
      if (!node.data) return;
      seen.add(toDisplay(getValue(node)));
    });
    return Array.from(seen).sort((a, b) => {
      if (a === BLANK_LABEL) return 1;
      if (b === BLANK_LABEL) return -1;
      return a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" });
    });
  }, [api, getValue, toDisplay, BLANK_LABEL]);

  const [allValues, setAllValues] = useState<string[]>(() => collectAllValues());
  const [pending, setPending] = useState<Set<string>>(() => (model ? new Set(model.values) : new Set(collectAllValues())));
  const [search, setSearch] = useState("");

  const modelRef = useRef<ExcelLikeFilterModel | null>(model);
  useEffect(() => { modelRef.current = model; }, [model]);

  useGridFilter({
    doesFilterPass(params: IDoesFilterPassParams): boolean {
      if (!modelRef.current) return true;
      return modelRef.current.values.includes(toDisplay(getValue(params.node)));
    },
    afterGuiAttached(params?: IAfterGuiAttachedParams) {
      hidePopupRef.current = params?.hidePopup;
      const fresh = collectAllValues();
      setAllValues(fresh);
      if (!modelRef.current) setPending(new Set(fresh));
    },
  });

  useEffect(() => {
    if (model) setPending(new Set(model.values));
    else setPending(new Set(collectAllValues()));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [model]);

  const visible = search
    ? allValues.filter((v) => v.toLowerCase().includes(search.toLowerCase()))
    : allValues;
  const allVisibleSelected = visible.length > 0 && visible.every((v) => pending.has(v));
  const someVisibleSelected = visible.some((v) => pending.has(v));

  const toggleValue = (value: string) => {
    setPending((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value); else next.add(value);
      return next;
    });
    onUiChange();
  };

  const toggleSelectAll = () => {
    setPending((prev) => {
      const next = new Set(prev);
      if (allVisibleSelected) visible.forEach((v) => next.delete(v));
      else visible.forEach((v) => next.add(v));
      return next;
    });
    onUiChange();
  };

  const handleOk = () => {
    const isAll = allValues.every((v) => pending.has(v));
    onModelChange(isAll ? null : { values: Array.from(pending) });
    hidePopupRef.current?.();
  };

  const handleCancel = () => {
    if (model) setPending(new Set(model.values)); else setPending(new Set(allValues));
    setSearch("");
    hidePopupRef.current?.();
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const next = e.target.value;
    if (next && !search) { setPending(new Set()); onUiChange(); }
    setSearch(next);
  };

  const dir = rtl ? "rtl" : "ltr";
  const align = rtl ? "right" : "left";
  return (
    <div style={{ ...styles.container, direction: dir }} dir={dir}>
      <div style={styles.searchRow}>
        <input
          type="text"
          placeholder={t("app.search", "Search…")}
          value={search}
          onChange={handleSearchChange}
          style={{ ...styles.searchInput, textAlign: align, direction: dir }}
          autoFocus
        />
      </div>
      <div style={styles.listContainer}>
        <label style={{ ...styles.itemLabel, direction: dir }}>
          <input
            type="checkbox"
            checked={allVisibleSelected}
            ref={(el) => { if (el) el.indeterminate = !allVisibleSelected && someVisibleSelected; }}
            onChange={toggleSelectAll}
            style={styles.checkbox}
          />
          <span style={styles.selectAllText}>({t("grid.selectAll", "Select all")})</span>
        </label>
        {visible.length === 0 ? (
          <div style={styles.noResults}>{t("grid.noResults", "No results")}</div>
        ) : (
          visible.map((value) => (
            <label key={value} style={{ ...styles.itemLabel, direction: dir }}>
              <input type="checkbox" checked={pending.has(value)} onChange={() => toggleValue(value)} style={styles.checkbox} />
              <span style={value === BLANK_LABEL ? styles.blankText : undefined}>{value}</span>
            </label>
          ))
        )}
      </div>
      <div style={styles.buttonRow}>
        <button onClick={handleOk} style={styles.okBtn} type="button">{t("app.apply", "OK")}</button>
        <button onClick={handleCancel} style={styles.cancelBtn} type="button">{t("app.cancel", "Cancel")}</button>
      </div>
    </div>
  );
};

export default ExcelLikeFilter;

const styles: Record<string, React.CSSProperties> = {
  container: { width: 230, padding: 6, boxSizing: "border-box", fontFamily: "inherit", fontSize: 13, backgroundColor: "#fff", border: "1px solid #cbd5e1", boxShadow: "2px 2px 6px rgba(0,0,0,0.15)" },
  searchRow: { marginBottom: 4 },
  searchInput: { width: "100%", boxSizing: "border-box", padding: "4px 8px", border: "1px solid #cbd5e1", borderRadius: 4, fontSize: 12, outline: "none" },
  listContainer: { maxHeight: 200, overflowY: "auto", border: "1px solid #e2e8f0", marginBottom: 6, backgroundColor: "#fff" },
  itemLabel: { display: "flex", alignItems: "center", gap: 6, padding: "3px 6px", cursor: "pointer", userSelect: "none", fontSize: 12, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" },
  selectAllText: { fontWeight: 600 },
  noResults: { padding: 6, color: "#94a3b8", textAlign: "center", fontSize: 12 },
  blankText: { color: "#94a3b8", fontStyle: "italic" },
  checkbox: { cursor: "pointer", flexShrink: 0, margin: 0, accentColor: "#2563eb" },
  buttonRow: { display: "flex", gap: 6, justifyContent: "flex-end" },
  okBtn: { padding: "4px 14px", backgroundColor: "#0f172a", color: "#fff", border: "1px solid #0f172a", borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 600 },
  cancelBtn: { padding: "4px 14px", backgroundColor: "#fff", color: "#334155", border: "1px solid #cbd5e1", borderRadius: 6, cursor: "pointer", fontSize: 12 },
};
