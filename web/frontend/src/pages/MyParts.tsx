import { useEffect, useRef, useState } from "react";
import PartInput from "../components/PartInput";
import {
  inventoryApi,
  trackParts,
  type Lot,
  type Stock,
  type SetItem,
  type Catalog,
  type Color,
} from "../inventory";

function LotRow({
  lot,
  palette,
  onSaved,
}: {
  lot: Lot;
  palette: Color[];
  onSaved: (value: Stock) => void;
}) {
  const [editing, setEditing] = useState(false),
    [part, setPart] = useState(lot.part || lot.raw_part),
    [color, setColor] = useState<number | null>(lot.color),
    [quantity, setQuantity] = useState(lot.quantity),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function save() {
    if (color === null) {
      trackParts("inventory_lot_color_required");
      setError("Choose the LDraw color you own before saving this lot.");
      return;
    }
    setBusy(true);
    setError("");
    trackParts("inventory_lot_save_started");
    try {
      onSaved(await inventoryApi.edit(lot.id, part, color, quantity));
      setEditing(false);
      trackParts("inventory_lot_saved");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="inventory-lot">
      <div>
        <strong>{lot.part || lot.raw_part}</strong>
        <div className="muted small">{lot.label}</div>
        {(lot.part === null || lot.color === null) && (
          <span className="warn-text small">
            Needs LDraw mapping · {lot.system} color {lot.raw_color}
          </span>
        )}
      </div>
      {editing ? (
        <>
          <label className="small">
            LDraw part
            <PartInput
              label="Map to LDraw part"
              value={part}
              onChange={setPart}
            />
          </label>
          <label className="small">
            LDraw color
            <select
              aria-label="Map to LDraw color"
              value={color ?? ""}
              onChange={(e) => {
                setColor(Number(e.target.value));
                trackParts("inventory_color_changed");
              }}
            >
              <option value="" disabled>
                Choose color
              </option>
              {palette.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label className="small">
            Quantity
            <input
              aria-label="Owned quantity"
              type="number"
              min={1}
              max={1000000}
              value={quantity}
              onChange={(e) => {
                setQuantity(Number(e.target.value));
                trackParts("inventory_lot_quantity_changed");
              }}
            />
          </label>
          <div className="button-group">
            <button disabled={busy} onClick={save}>
              Save lot
            </button>
            <button
              disabled={busy}
              onClick={() => {
                setEditing(false);
                trackParts("inventory_lot_edit_cancelled");
              }}
            >
              Cancel
            </button>
          </div>
        </>
      ) : (
        <>
          <span>
            {palette.find((c) => c.code === lot.color)?.name ||
              "Unmapped color"}
          </span>
          <span>{lot.quantity.toLocaleString()} pieces</span>
          <button
            onClick={() => {
              setEditing(true);
              trackParts("inventory_lot_edit_opened");
            }}
          >
            {lot.part === null || lot.color === null ? "Map lot" : "Edit lot"}
          </button>
        </>
      )}
      {error && (
        <p role="alert" className="danger-text">
          {error}
        </p>
      )}
    </div>
  );
}

export default function MyParts() {
  const [stock, setStock] = useState<Stock | null>(null),
    [catalog, setCatalog] = useState<Catalog | null>(null),
    [error, setError] = useState(""),
    [status, setStatus] = useState(""),
    [busy, setBusy] = useState(false);
  const [query, setQuery] = useState(""),
    [sets, setSets] = useState<SetItem[]>([]),
    [searched, setSearched] = useState(false),
    [url, setUrl] = useState(""),
    [system, setSystem] = useState("ldraw"),
    [copies, setCopies] = useState(1);
  const [part, setPart] = useState(""),
    [color, setColor] = useState(4),
    [qty, setQty] = useState(1),
    [filter, setFilter] = useState(""),
    [visible, setVisible] = useState(50);
  const file = useRef<HTMLInputElement>(null);
  useEffect(() => {
    let active = true;
    inventoryApi.read().then(
      (value) => {
        if (active) {
          setStock(value);
          setCatalog(value.catalog || null);
        }
      },
      (e) => {
        if (active) setError(e.message);
      },
    );
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    if (!catalog?.building) return;
    let active = true;
    const timer = setInterval(
      () =>
        inventoryApi.read().then(
          (value) => {
            if (active) {
              setStock(value);
              setCatalog(value.catalog || null);
            }
          },
          () => {},
        ),
      2000,
    );
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [catalog?.building]);
  async function change(
    action: () => Promise<Stock>,
    message: string,
    event: string,
  ) {
    setBusy(true);
    setError("");
    setStatus("");
    trackParts(event);
    try {
      const value = await action();
      setStock(value);
      setStatus(message);
      trackParts(event + "_completed", {
        pieces: value.total,
        unmapped_lots: value.unmapped,
      });
    } catch (e) {
      setError((e as Error).message);
      trackParts(event + "_failed");
    } finally {
      setBusy(false);
    }
  }
  async function search(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    trackParts("inventory_set_search");
    try {
      const value = await inventoryApi.search(query);
      setSets(value.sets);
      setCatalog(value.catalog);
      setSearched(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function index() {
    setError("");
    trackParts("inventory_catalog_requested");
    try {
      setCatalog(await inventoryApi.catalog());
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const palette = stock?.palette || [],
    q = filter.toLowerCase();
  const lots = (stock?.lots || []).filter((l) =>
    (l.raw_part + " " + l.part + " " + l.label).toLowerCase().includes(q),
  );
  return (
    <div className="page inventory-page">
      <header className="page-head">
        <div>
          <h1>My Parts</h1>
          <p className="muted">
            Add sets and loose pieces you own. Nova can adapt models to these
            quantities and colors.
          </p>
        </div>
      </header>
      {error && (
        <div className="banner error" role="alert">
          {error}
        </div>
      )}
      {status && (
        <p className="banner" role="status">
          {status}
        </p>
      )}
      <div className="inventory-summary">
        <div>
          <strong>{(stock?.total || 0).toLocaleString()}</strong>
          <span>Owned pieces</span>
        </div>
        <div>
          <strong>{(stock?.usable || 0).toLocaleString()}</strong>
          <span>Ready for Nova</span>
        </div>
        <div>
          <strong>{stock?.unmapped || 0}</strong>
          <span>Lots needing mapping</span>
        </div>
      </div>
      <section className="inventory-section">
        <div className="inventory-section-head">
          <div>
            <h2>Find sets you own</h2>
            <p className="muted small">
              Search a local index of official sets. LEGO and BrickLink links
              open the source catalogs.
            </p>
          </div>
          <button disabled={catalog?.building} onClick={index}>
            {catalog?.ready ? "Refresh catalog" : "Download set catalog"}
          </button>
        </div>
        <p className="muted small" role="status">
          {catalog?.building
            ? catalog.stage + "…"
            : catalog?.ready
              ? `${catalog.sets.toLocaleString()} indexed sets · updated ${catalog.updated}`
              : "Download the public catalog once to search offline. No API key needed."}
        </p>
        {catalog?.warning && (
          <p className="warn-text small">{catalog.warning}</p>
        )}
        {catalog?.error && (
          <p role="alert" className="danger-text">
            {catalog.error}
          </p>
        )}
        <form className="inventory-controls" onSubmit={search}>
          <input
            type="search"
            aria-label="Search LEGO sets"
            placeholder="Set number or name, e.g. 10696 or Galaxy Explorer"
            value={query}
            maxLength={160}
            onChange={(e) => {
              setQuery(e.target.value);
              trackParts("inventory_set_query_changed");
            }}
          />
          <label className="small">
            Copies
            <input
              aria-label="Set copies"
              type="number"
              min={1}
              max={100}
              value={copies}
              onChange={(e) => {
                setCopies(Number(e.target.value));
                trackParts("inventory_set_copies_changed");
              }}
            />
          </label>
          <button disabled={busy || !catalog?.ready || !query.trim()}>
            Search sets
          </button>
        </form>
        {searched && !sets.length && (
          <p className="muted">No matching sets in this catalog.</p>
        )}
        <div className="inventory-set-grid">
          {sets.map((set) => (
            <article key={set.num}>
              <strong>{set.name}</strong>
              <p className="muted small">
                {set.num} · {set.year} · {set.num_parts.toLocaleString()} pieces
              </p>
              <div className="inventory-controls">
                <a
                  href={set.lego_url}
                  target="_blank"
                  rel="noreferrer"
                  onClick={() =>
                    trackParts("inventory_set_reference_opened", {
                      source: "lego",
                    })
                  }
                >
                  LEGO
                </a>
                <a
                  href={set.bricklink_url}
                  target="_blank"
                  rel="noreferrer"
                  onClick={() =>
                    trackParts("inventory_set_reference_opened", {
                      source: "bricklink",
                    })
                  }
                >
                  BrickLink
                </a>
                <button
                  disabled={busy}
                  onClick={() =>
                    change(
                      () =>
                        inventoryApi.importUrl(set.num, "rebrickable", copies),
                      "Added " +
                        copies +
                        (copies === 1 ? " copy of " : " copies of ") +
                        set.name +
                        ". Spares are excluded.",
                      "inventory_set_added",
                    )
                  }
                >
                  Add set
                </button>
              </div>
            </article>
          ))}
        </div>
        <p className="muted small">
          Catalog data:{" "}
          <a
            href="https://rebrickable.com/downloads/"
            target="_blank"
            rel="noreferrer"
            onClick={() => trackParts("inventory_catalog_source_opened")}
          >
            Rebrickable public downloads
          </a>
          . Color IDs are mapped by name to the installed LDraw palette; unknown
          mappings stay visible.
        </p>
      </section>
      <section className="inventory-section">
        <h2>Upload or import a parts list</h2>
        <p className="muted small">
          CSV (including Nova BOM exports) or BrickLink XML, up to 2 MB. A set
          number or LEGO/BrickLink set URL uses the indexed inventory.
          Login-only exports can be downloaded in your browser and uploaded
          here.
        </p>
        <div className="inventory-controls">
          <label>
            ID system
            <select
              aria-label="Parts list ID system"
              value={system}
              onChange={(e) => {
                setSystem(e.target.value);
                trackParts("inventory_import_format_changed", {
                  system: e.target.value,
                });
              }}
            >
              <option value="ldraw">LDraw / Nova BOM</option>
              <option value="bricklink">BrickLink</option>
              <option value="rebrickable">Rebrickable</option>
            </select>
          </label>
          <button
            disabled={busy}
            onClick={() => {
              file.current?.click();
              trackParts("inventory_upload_opened");
            }}
          >
            Upload CSV / XML
          </button>
          <input
            ref={file}
            type="file"
            hidden
            aria-label="Parts list file"
            accept=".csv,.xml,.txt"
            onChange={(e) => {
              const selected = e.target.files?.[0];
              e.target.value = "";
              if (selected) {
                if (selected.size > 2 * 1024 * 1024) {
                  setError("Parts list exceeds 2 MB");
                  return;
                }
                void change(
                  () => inventoryApi.upload(selected, system),
                  "Parts list added. Review any unmapped lots below.",
                  "inventory_file_import",
                );
              }
            }}
          />
        </div>
        <form
          className="inventory-controls"
          onSubmit={(e) => {
            e.preventDefault();
            void change(
              () => inventoryApi.importUrl(url, system, copies),
              "Parts added from your set or export link.",
              "inventory_url_import",
            );
          }}
        >
          <input
            aria-label="Set or parts list URL"
            placeholder="Set number, LEGO / BrickLink URL, or public CSV / XML URL"
            maxLength={2048}
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              trackParts("inventory_url_changed");
            }}
          />
          <button disabled={busy || !url.trim()}>Import link</button>
        </form>
      </section>
      <section className="inventory-section">
        <h2>Add loose parts</h2>
        <form
          className="inventory-controls"
          onSubmit={(e) => {
            e.preventDefault();
            void change(
              () => inventoryApi.add(part, color, qty),
              "Loose parts added.",
              "inventory_loose_parts_added",
            );
          }}
        >
          <label>
            Part number
            <PartInput
              label="Loose part number"
              value={part}
              onChange={setPart}
            />
          </label>
          <label>
            Color
            <select
              aria-label="Loose part color"
              value={color}
              onChange={(e) => {
                setColor(Number(e.target.value));
                trackParts("inventory_color_changed");
              }}
            >
              {palette.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Quantity
            <input
              aria-label="Loose part quantity"
              type="number"
              min={1}
              max={1000000}
              value={qty}
              onChange={(e) => {
                setQty(Number(e.target.value));
                trackParts("inventory_loose_quantity_changed");
              }}
            />
          </label>
          <button disabled={busy || !part.trim()}>Add pieces</button>
        </form>
        <p className="muted small">
          Search the installed library by number or description and select a
          LDraw part ID. Unknown imports can be mapped below. Quantities are a
          planning budget; fitting a model does not subtract them.
        </p>
      </section>
      <section className="inventory-section">
        <div className="inventory-section-head">
          <h2>Your inventory</h2>
          <input
            type="search"
            aria-label="Filter owned parts"
            placeholder="Filter part or source"
            value={filter}
            onChange={(e) => {
              setFilter(e.target.value);
              setVisible(50);
              trackParts("inventory_filter_changed");
            }}
          />
        </div>
        {!stock && !error && <p className="muted">Loading inventory…</p>}
        {stock && !stock.lots.length && (
          <p className="muted">
            No owned parts yet. Add a set, upload a list or enter loose pieces
            above.
          </p>
        )}
        {lots.slice(0, visible).map((lot) => (
          <LotRow
            key={lot.id}
            lot={lot}
            palette={palette}
            onSaved={(value) => {
              setStock(value);
              setStatus("Updated the owned lot.");
            }}
          />
        ))}
        {lots.length > visible && (
          <button
            onClick={() => {
              setVisible(visible + 50);
              trackParts("inventory_more_lots_requested");
            }}
          >
            Show more lots
          </button>
        )}
      </section>
    </div>
  );
}
