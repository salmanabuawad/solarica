import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { StatCard } from "../components/StatCard";
import type { SiteSummary, SiteString } from "../api/client";
import { api } from "../api/client";
import { useProject } from "../contexts/ProjectContext";

export function InventoryPage() {
  const { t } = useTranslation();
  const { selectedSite: projectSite } = useProject();
  const [sites, setSites] = useState<SiteSummary[]>([]);
  const [strings, setStrings] = useState<SiteString[]>([]);
  const [selectedSiteId, setSelectedSiteId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [stringsLoading, setStringsLoading] = useState(false);

  useEffect(() => {
    api.listSites().then((items) => {
      setSites(items);
      setLoading(false);
      if (projectSite) {
        setSelectedSiteId(projectSite.id);
        setStringsLoading(true);
        api.listSiteStrings(projectSite.id).then((s) => { setStrings(s); setStringsLoading(false); });
      }
    });
  }, [projectSite?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const selectSite = (id: number) => {
    if (selectedSiteId === id) { setSelectedSiteId(null); setStrings([]); return; }
    setSelectedSiteId(id);
    setStringsLoading(true);
    api.listSiteStrings(id).then((items) => { setStrings(items); setStringsLoading(false); });
  };

  const totalModules = sites.reduce((s, x) => s + (x.module_count ?? 0), 0);
  const totalCapacity = sites.reduce((s, x) => s + (x.plant_capacity_mw ?? 0), 0);
  const totalStrings = sites.reduce((s, x) => s + x.string_count, 0);

  const thStyle: React.CSSProperties = {
    padding: "7px 12px", textAlign: "left", fontWeight: 600,
    fontSize: "var(--theme-font-size-xs)", color: "rgb(var(--theme-text-muted))",
    background: "var(--theme-ag-header-bg)", borderBottom: "1px solid var(--theme-ag-border)",
  };
  const tdStyle: React.CSSProperties = {
    padding: "6px 12px", fontSize: "var(--theme-font-size-xs)",
    borderBottom: "1px solid var(--theme-ag-border)", color: "rgb(var(--theme-text-primary))",
  };

  const filteredStrings = strings.filter((s) =>
    !search || s.string_code.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      <h2 style={{ margin: "0 0 16px", fontSize: "1.1rem", fontWeight: 700, color: "rgb(var(--theme-text-primary))" }}>
        {t("inventory.title")}
      </h2>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 12, marginBottom: 20 }}>
        <StatCard title={t("inventory.sites")} value={sites.length} />
        <StatCard title={t("inventory.totalModules")} value={totalModules.toLocaleString()} />
        <StatCard title={t("inventory.totalCapacity")} value={totalCapacity.toFixed(3) + " MW"} />
        <StatCard title={t("inventory.totalStrings")} value={totalStrings.toLocaleString()} />
      </div>

      <div className="solarica-card" style={{ marginBottom: 16 }}>
        <div style={{ fontWeight: 600, fontSize: "var(--theme-font-size-sm)", marginBottom: 10 }}>
          {t("inventory.sitesClickToView")}
        </div>
        {loading ? <p style={{ color: "rgb(var(--theme-text-muted))" }}>{t("inventory.loading")}</p> : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th style={thStyle}>{t("inventory.code")}</th>
                  <th style={thStyle}>{t("inventory.name")}</th>
                  <th style={thStyle}>{t("inventory.moduleType")}</th>
                  <th style={thStyle}>{t("inventory.modules")}</th>
                  <th style={thStyle}>{t("inventory.capacityMw")}</th>
                  <th style={thStyle}>{t("inventory.strings")}</th>
                  <th style={thStyle}>{t("inventory.countryRegion")}</th>
                </tr>
              </thead>
              <tbody>
                {sites.length === 0 && (
                  <tr><td colSpan={7} style={{ ...tdStyle, textAlign: "center", color: "rgb(var(--theme-text-muted))", padding: 20 }}>{t("inventory.noSitesFound")}</td></tr>
                )}
                {sites.map((s) => (
                  <tr
                    key={s.id}
                    onClick={() => selectSite(s.id)}
                    style={{ cursor: "pointer", background: selectedSiteId === s.id ? "rgb(var(--theme-highlight))" : undefined }}
                  >
                    <td style={{ ...tdStyle, fontWeight: 600, color: "rgb(var(--theme-action-accent))" }}>{s.site_code}</td>
                    <td style={tdStyle}>{s.site_name}</td>
                    <td style={tdStyle}>{s.module_type ?? "—"}</td>
                    <td style={tdStyle}>{s.module_count ?? "—"}</td>
                    <td style={tdStyle}>{s.plant_capacity_mw != null ? s.plant_capacity_mw.toFixed(3) : "—"}</td>
                    <td style={tdStyle}>{s.string_count}</td>
                    <td style={tdStyle}>{[s.country, s.region].filter(Boolean).join(" / ") || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selectedSiteId != null && (
        <div className="solarica-card">
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
            <span style={{ fontWeight: 600, fontSize: "var(--theme-font-size-sm)" }}>
              {t("inventory.stringsFor")} {sites.find((s) => s.id === selectedSiteId)?.site_name}
            </span>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("inventory.searchStringCode")}
              style={{ padding: "4px 10px", border: "1px solid rgb(var(--theme-card-border))", borderRadius: 6, fontSize: "var(--theme-font-size-xs)", marginLeft: "auto", width: 200 }}
            />
          </div>
          {stringsLoading ? <p style={{ color: "rgb(var(--theme-text-muted))" }}>{t("inventory.loadingStrings")}</p> : (
            <div style={{ overflowX: "auto", maxHeight: 320, overflowY: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead style={{ position: "sticky", top: 0, zIndex: 1 }}>
                  <tr>
                    <th style={thStyle}>{t("inventory.stringCode")}</th>
                    <th style={thStyle}>{t("inventory.section")}</th>
                    <th style={thStyle}>{t("inventory.block")}</th>
                    <th style={thStyle}>{t("inventory.stringNo")}</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredStrings.length === 0 && (
                    <tr><td colSpan={4} style={{ ...tdStyle, textAlign: "center", color: "rgb(var(--theme-text-muted))", padding: 16 }}>{t("inventory.noStringsFound")}</td></tr>
                  )}
                  {filteredStrings.map((s) => (
                    <tr key={s.id}>
                      <td style={{ ...tdStyle, fontFamily: "monospace" }}>{s.string_code}</td>
                      <td style={tdStyle}>{s.section_no}</td>
                      <td style={tdStyle}>{s.block_no}</td>
                      <td style={tdStyle}>{s.string_no}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
