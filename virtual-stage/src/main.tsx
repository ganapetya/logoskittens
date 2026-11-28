import { createRoot } from "react-dom/client";
import { App } from "./App";
import { SettingsPage } from "./settings";
import "./index.css";

// #/settings is its own page, opened in a new tab, so a talk in the first tab keeps going.
const page = window.location.hash.startsWith("#/settings") ? <SettingsPage /> : <App />;
createRoot(document.getElementById("root")!).render(page);
