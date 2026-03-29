/**
 * DownloadPage
 *
 * Presents both connector options (Python and .NET) with install steps,
 * requirements, and driver note. Shown when the user clicks "Get Connector".
 */

interface DownloadPageProps {
  onClose: () => void;
}

export function DownloadPage({ onClose }: DownloadPageProps) {
  return (
    <section className="download-page">
      <div className="section-heading">
        <div>
          <h2>הורד מחבר מקומי</h2>
          <p className="hint">
            המחבר פועל במחשב המחובר ל-PVPM 1540X שלך. הוא שומר מדידות מקומית ולאחר מכן מסנכרן אותן לאפליקציה זו. שני המחברים חושפים אותו REST API — בחר את המתאים לסביבתך.
          </p>
        </div>
        <button type="button" onClick={onClose}>
          סגור
        </button>
      </div>

      {/* Vendor driver note */}
      <div className="card" style={{ borderLeft: "4px solid #f59e0b", marginBottom: "1.5rem" }}>
        <strong>נדרש דרייבר USB של הספק (התקנה נפרדת)</strong>
        <p className="hint" style={{ marginTop: "0.25rem" }}>
          יש להתקין את דרייבר ה-USB של הספק ותוכנת ה-Transfer לפני השימוש במחבר. הורד אותם מהפורטל של EKO / IMT / Solmetric. מחבר Solarica אינו תחליף לדרייבר הספק — הוא קורא את הקבצים שתוכנת הספק מייצרת.
        </p>
      </div>

      <div className="content-grid" style={{ gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>

        {/* Python connector */}
        <div className="card">
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
            <span style={{ fontSize: "1.5rem" }}>🐍</span>
            <h3 style={{ margin: 0 }}>מחבר Python</h3>
            <span className="badge">ייחוסי</span>
          </div>
          <p className="hint">
            המימוש הייחוסי. תכונות מלאות, הורדה כתיקייה אחת — ללא צורך בהתקנת Python (קובץ הרצה עצמאי PyInstaller).
          </p>

          <table className="info-table">
            <tbody>
              <tr><td>סביבת ריצה</td><td>Python 3.11+ (מצורף)</td></tr>
              <tr><td>מסגרת</td><td>FastAPI + Uvicorn</td></tr>
              <tr><td>בסיס נתונים</td><td>SQLite (מטמון מקומי)</td></tr>
              <tr><td>טורי</td><td>PySerial</td></tr>
              <tr><td>אריזה</td><td>PyInstaller one-dir</td></tr>
              <tr><td>פלטפורמה</td><td>Windows, Linux, macOS</td></tr>
            </tbody>
          </table>

          <h4>דרייברים</h4>
          <ul className="hint">
            <li><strong>mock</strong> — נתונים סינתטיים לבדיקות</li>
            <li><strong>vendor_export</strong> — קורא קבצי ייצוא PVPM מתיקייה</li>
            <li><strong>serial</strong> — פורט COM ישיר (פרוטוקול בפיתוח)</li>
          </ul>

          <h4>התחלה מהירה</h4>
          <pre className="code-block">{`# 1. חלץ את הזיפ
# 2. ערוך .env (הגדר PVPM_DRIVER=vendor_export)
# 3. הפעל:
solarica_connector.exe          # Windows
./solarica_connector            # Linux / macOS`}</pre>

          <div className="action-bar" style={{ marginTop: "1rem" }}>
            <a
              className="button-link primary"
              href="/downloads/solarica_connector_python.zip"
            >
              הורד מחבר Python
            </a>
            <a
              className="button-link"
              href="/docs/python-connector.md"
              target="_blank"
              rel="noreferrer"
            >
              תיעוד
            </a>
          </div>
        </div>

        {/* .NET connector */}
        <div className="card">
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
            <span style={{ fontSize: "1.5rem" }}>⚙️</span>
            <h3 style={{ margin: 0 }}>.NET Connector</h3>
            <span className="badge badge-secondary">בסיסי</span>
          </div>
          <p className="hint">
            מתאים ל-Windows Service. פועל כשירות מנוהל, שורד אתחולים אוטומטית ומשתלב עם יומן האירועים של Windows.
          </p>

          <table className="info-table">
            <tbody>
              <tr><td>סביבת ריצה</td><td>.NET 8 (עצמאי או מותקן)</td></tr>
              <tr><td>מסגרת</td><td>ASP.NET Core Minimal API</td></tr>
              <tr><td>בסיס נתונים</td><td>SQLite via EF Core</td></tr>
              <tr><td>טורי</td><td>System.IO.Ports</td></tr>
              <tr><td>אריזה</td><td>פרסום עצמאי / Windows Service</td></tr>
              <tr><td>פלטפורמה</td><td>Windows (עיקרי), Linux / macOS</td></tr>
            </tbody>
          </table>

          <h4>התחלה מהירה</h4>
          <pre className="code-block">{`# הפעלה ישירה:
solarica_connector.exe

# התקנה כ-Windows Service:
sc create SolaricaConnector ^
  binPath="C:\\Solarica\\solarica_connector.exe"
sc start SolaricaConnector`}</pre>

          <div className="action-bar" style={{ marginTop: "1rem" }}>
            <a
              className="button-link primary"
              href="/downloads/solarica_connector_dotnet.zip"
            >
              הורד מחבר .NET
            </a>
            <a
              className="button-link"
              href="/docs/dotnet-connector.md"
              target="_blank"
              rel="noreferrer"
            >
              תיעוד
            </a>
          </div>
        </div>
      </div>

      {/* Chrome Extension */}
      <div className="card" style={{ marginTop: "1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
          <span style={{ fontSize: "1.5rem" }}>🧩</span>
          <h3 style={{ margin: 0 }}>תוסף Chrome</h3>
          <span className="badge">מומלץ</span>
        </div>
        <p className="hint">
          מגשר בין אפליקציית Solarica בדפדפן לבין המחבר המקומי שרץ במחשב שלך. מציג את מצב החיבור, מאפשר ייבוא מדידות וסנכרון ישירות מסרגל הכלים של Chrome — ללא צורך לפתוח ממשק נפרד.
        </p>

        <h4>התקנה</h4>
        <ol className="hint" style={{ paddingInlineStart: "1.25rem", lineHeight: "1.8" }}>
          <li>הורד את הקובץ <code>solarica_connector_extension.zip</code> ופתח אותו לתיקייה</li>
          <li>פתח Chrome ועבור אל <code>chrome://extensions</code></li>
          <li>הפעל <strong>Developer mode</strong> (פינה עליונה ימנית)</li>
          <li>לחץ <strong>Load unpacked</strong> ובחר את התיקייה שחולצה</li>
          <li>ודא שהמחבר המקומי פועל ב-<code>127.0.0.1:8765</code></li>
        </ol>

        <div className="action-bar" style={{ marginTop: "1rem" }}>
          <a
            className="button-link primary"
            href="/downloads/solarica_connector_extension.zip"
          >
            הורד תוסף Chrome
          </a>
        </div>
      </div>

      {/* Same API callout */}
      <div className="card" style={{ borderLeft: "4px solid #22c55e", marginTop: "1.5rem" }}>
        <strong>שני המחברים חושפים אותו REST API</strong>
        <p className="hint" style={{ marginTop: "0.25rem" }}>
          האפליקציה מזהה אוטומטית את המחבר הפועל ב-{" "}
          <code>http://127.0.0.1:8765</code>. ניתן לעבור בין Python ל-.NET בכל עת — אין צורך בשינויים באפליקציה. החוזה המשותף מוגדר ב-{" "}
          <code>connector/api-contract/openapi.yaml</code>.
        </p>
      </div>
    </section>
  );
}
