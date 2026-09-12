import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { installDesignTokens } from "./theme";
import App from "./App";
import "./styles/global.css";

// Design tokens are injected onto :root before the first paint so CSS Modules
// can reference var(--bh-*) immediately. src/theme.ts stays the single source.
installDesignTokens();

const container = document.getElementById("root");
if (!container) {
  throw new Error("Root container #root is missing from index.html");
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
