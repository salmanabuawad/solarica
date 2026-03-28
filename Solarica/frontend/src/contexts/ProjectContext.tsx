import { createContext, useContext, useEffect, useState } from "react";
import type { SiteSummary } from "../api/client";
import { api } from "../api/client";

interface ProjectContextValue {
  sites: SiteSummary[];
  sitesLoading: boolean;
  selectedSite: SiteSummary | null;
  selectSite: (site: SiteSummary | null) => void;
  reloadSites: () => void;
}

const ProjectContext = createContext<ProjectContextValue>({
  sites: [],
  sitesLoading: true,
  selectedSite: null,
  selectSite: () => {},
  reloadSites: () => {},
});

function loadSavedSite(sites: SiteSummary[]): SiteSummary | null {
  try {
    const id = localStorage.getItem("solarica.selectedSiteId");
    if (!id) return null;
    return sites.find((s) => s.id === Number(id)) ?? null;
  } catch {
    return null;
  }
}

export function ProjectProvider({ children }: { children: React.ReactNode }) {
  const [sites, setSites] = useState<SiteSummary[]>([]);
  const [sitesLoading, setSitesLoading] = useState(true);
  const [selectedSite, setSelectedSite] = useState<SiteSummary | null>(null);

  const loadSites = () => {
    setSitesLoading(true);
    api.listSites()
      .then((items) => {
        setSites(items);
        setSelectedSite((prev) => {
          if (prev) return items.find((s) => s.id === prev.id) ?? null;
          return loadSavedSite(items);
        });
        setSitesLoading(false);
      })
      .catch(() => setSitesLoading(false));
  };

  useEffect(() => { loadSites(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const selectSite = (site: SiteSummary | null) => {
    setSelectedSite(site);
    try {
      if (site) localStorage.setItem("solarica.selectedSiteId", String(site.id));
      else localStorage.removeItem("solarica.selectedSiteId");
    } catch {}
  };

  return (
    <ProjectContext.Provider value={{ sites, sitesLoading, selectedSite, selectSite, reloadSites: loadSites }}>
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject() {
  return useContext(ProjectContext);
}
