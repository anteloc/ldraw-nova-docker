import { useState } from "react";
import { Link } from "react-router-dom";
import { inventoryApi, trackParts, type FitReport } from "../inventory";
import { type ModelFile } from "../api";
import { useApp } from "../context";
export default function UseMyParts({ model }: { model: ModelFile }) {
  const { refreshChats, openViewer } = useApp();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [result, setResult] = useState<{
      model: ModelFile;
      report: FitReport;
    } | null>(
      model.inventory_report ? { model, report: model.inventory_report } : null,
    );
  async function fit() {
    setBusy(true);
    setError("");
    setResult(null);
    trackParts("inventory_model_fit_started");
    try {
      const value = await inventoryApi.fit(model.file);
      setResult(value);
      refreshChats();
      window.dispatchEvent(new Event("models-changed"));
      trackParts("inventory_model_fit_completed", {
        matched: value.report.matched_parts,
        missing: value.report.missing_parts,
      });
    } catch (e) {
      setError((e as Error).message);
      trackParts("inventory_model_fit_failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="inventory-fit">
      <button disabled={busy || !model.model_url} onClick={fit}>
        {busy ? "Matching parts and rendering…" : "Use my parts"}
      </button>
      {busy && (
        <p className="muted small" role="status">
          Matching owned quantities and colors, validating and rendering a new
          version. Your original stays saved.
        </p>
      )}
      {error && (
        <p className="danger-text small" role="alert">
          {error} <Link to="/parts">My Parts</Link>
        </p>
      )}
      {result && (
        <div>
          <p className="small" role="status">
            Fitted version: {result.report.matched_parts.toLocaleString()} of{" "}
            {result.report.total_parts.toLocaleString()} pieces owned ·{" "}
            {result.report.missing_parts.toLocaleString()} missing.{" "}
            {result.report.color_changes} color{" "}
            {result.report.color_changes === 1 ? "change" : "changes"} ·{" "}
            {result.report.splits} brick/plate{" "}
            {result.report.splits === 1 ? "split" : "splits"}.
          </p>
          {!!result.report.missing.length && (
            <details onToggle={() => trackParts("inventory_shortages_toggled")}>
              <summary>Missing parts</summary>
              <ul>
                {result.report.missing.map((r) => (
                  <li key={r.part + "-" + r.color}>
                    {r.quantity} × {r.part} · LDraw color {r.color}
                  </li>
                ))}
              </ul>
            </details>
          )}
          <button
            onClick={() => {
              if (result.model.model_url)
                openViewer({
                  modelUrl: result.model.model_url,
                  title: result.model.description || result.model.file,
                  parts: result.model.parts,
                  mode: "viewer",
                });
              trackParts("inventory_fitted_model_opened");
            }}
          >
            View fitted model
          </button>
        </div>
      )}
    </div>
  );
}
