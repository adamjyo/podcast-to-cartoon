import { createRoot } from "react-dom/client";
import { Studio } from "@/routes/index";
import "@/styles.css";

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <div
      id="app-scroll"
      style={{ position: "fixed", inset: 0, overflowY: "scroll", overflowX: "hidden", background: "#f3ecdf" }}
    >
      <Studio />
    </div>,
  );
}
