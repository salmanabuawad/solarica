import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { SiteDataPanel } from "../components/SiteDataPanel";

export function ProjectsPage() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  return (
    <div>
      <nav className="page-tab-bar">
        <Link to="/projects">
          <button type="button" className={`page-tab-btn${pathname === "/projects" ? " active" : ""}`}>
            {t("nav.sitesDesign")}
          </button>
        </Link>
        <Link to="/progress">
          <button type="button" className={`page-tab-btn${pathname === "/progress" ? " active" : ""}`}>
            {t("nav.progress")}
          </button>
        </Link>
      </nav>
      <SiteDataPanel />
    </div>
  );
}
