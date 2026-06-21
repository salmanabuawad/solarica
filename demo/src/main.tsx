import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ThemeProvider, CssBaseline } from "@mui/material";
import { theme } from "./theme";
import { DrawerProvider } from "./components/AssetDrawer";
import App from "./App.tsx";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, "")}>
        <DrawerProvider>
          <App />
        </DrawerProvider>
      </BrowserRouter>
    </ThemeProvider>
  </StrictMode>,
);
