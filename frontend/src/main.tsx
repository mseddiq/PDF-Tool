import React, { useState, useEffect, useRef, useCallback } from "react";
import { createRoot } from "react-dom/client";
import {
  FileText,
  Upload,
  Plus,
  Download,
  Undo2,
  Redo2,
  Search,
  Settings,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  PanelLeft,
  Type,
  Image as ImageIcon,
  PenTool,
  Highlighter,
  Layers,
  Scissors,
  RotateCw,
  Trash2,
  Copy,
  ArrowUpDown,
  FileOutput,
  Shield,
  ScanText,
  MousePointer2,
  Square,
  MessageSquare,
  Sun,
  Moon,
  X,
  Check,
  FolderOpen,
  Command,
  ArrowUpRight,
  Minimize2,
  Printer,
  Stamp,
  Move,
  Menu,
} from "lucide-react";
import {
  api,
  json,
  openFile,
  download,
  renderUrl,
  DocumentState,
  Objects,
  Rect,
  Span,
  Operation,
  Page,
} from "./api";
import Thumbnails from "./Thumbnails";
import SelectionFrame from "./SelectionFrame";
import SignatureDialog from "./SignatureDialog";
import "./styles.css";

type Tool =
  | "select"
  | "text"
  | "image"
  | "highlight"
  | "underline"
  | "strikeout"
  | "rect"
  | "circle"
  | "line"
  | "arrow"
  | "note"
  | "ink"
  | "signature"
  | "extract_signature"
  | "crop"
  | "stamp";
type Job = {
  id: string;
  kind: string;
  status: string;
  progress: number;
  error?: string;
  warnings?: string[];
  review?: { page: number; confidence: number; text: string }[];
};
const categories = [
  "Edit PDF",
  "Organize",
  "Convert",
  "Annotate",
  "Sign",
  "OCR",
  "Protect",
];
function App() {
  const [doc, setDoc] = useState<DocumentState | null>(null),
    [active, setActive] = useState(""),
    [selected, setSelected] = useState<string[]>([]);
  const [objects, setObjects] = useState<Objects | null>(null),
    [span, setSpan] = useState<Span | null>(null),
    [imageXref, setImageXref] = useState<number | null>(null);
  const [tool, setTool] = useState<Tool>("select"),
    [category, setCategory] = useState("Edit PDF"),
    [zoom, setZoom] = useState(0.9),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState(""),
    [error, setError] = useState("");
  const [dark, setDark] = useState(
      () => localStorage.getItem("studio-theme") === "dark",
    ),
    [modal, setModal] = useState(""),
    [text, setText] = useState(""),
    [fontSize, setFontSize] = useState(16),
    [fontFamily, setFontFamily] = useState<"helv" | "tiro" | "cour">("helv"),
    [color, setColor] = useState("#273447"),
    [bold, setBold] = useState(false),
    [italic, setItalic] = useState(false),
    [underline, setUnderline] = useState(false),
    [align, setAlign] = useState<"left" | "center" | "right">("left"),
    [opacity, setOpacity] = useState(1);
  const [rect, setRect] = useState<Rect>([72, 72, 320, 130]),
    [asset, setAsset] = useState(""),
    [assetPending, setAssetPending] = useState(false),
    [textPending, setTextPending] = useState(false),
    [search, setSearch] = useState(""),
    [hits, setHits] = useState<{ page_id: string; rect: Rect }[]>([]),
    [job, setJob] = useState<Job | null>(null),
    [language, setLanguage] = useState("eng"),
    [mode, setMode] = useState("editable"),
    [password, setPassword] = useState("");
  const [health, setHealth] = useState<{
      libreoffice: boolean;
      ocr_languages: string[];
      max_mb: number;
      ocr?: {
        available: boolean;
        data_directory: string | null;
        error: string | null;
      };
    } | null>(null),
    [pendingFile, setPendingFile] = useState<File | null>(null),
    [importDoc, setImportDoc] = useState<DocumentState | null>(null),
    [importIds, setImportIds] = useState<string[]>([]),
    [sideOpen, setSideOpen] = useState(true),
    [inspectorOpen, setInspectorOpen] = useState(false),
    [imageAngle, setImageAngle] = useState(0),
    [behind, setBehind] = useState(false),
    [pngDpi, setPngDpi] = useState(300),
    [removeWhite, setRemoveWhite] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null),
    assetInput = useRef<HTMLInputElement>(null),
    importInput = useRef<HTMLInputElement>(null),
    surface = useRef<HTMLDivElement>(null),
    drag = useRef<{ start: [number, number]; points: number[][] } | null>(null);
  const page = doc?.pages.find((p) => p.id === active) || doc?.pages[0];
  const adopt = useCallback((next: DocumentState) => {
    setDoc(next);
    try {
      localStorage.setItem("studio-last-document", next.id);
    } catch {}
    setActive((old) =>
      next.pages.some((p) => p.id === old) ? old : next.pages[0]?.id || "",
    );
    setSelected((old) =>
      old.filter((id) => next.pages.some((p) => p.id === id)),
    );
    setSpan(null);
    setImageXref(null);
  }, []);
  const requestCount = useRef(0),
    mutationFlight = useRef(false);
  const run = useCallback(
    async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
      requestCount.current++;
      setBusy(true);
      setError("");
      try {
        return await fn();
      } catch (e) {
        setError((e as Error).message);
      } finally {
        requestCount.current--;
        setBusy(requestCount.current > 0);
      }
    },
    [],
  );
  useEffect(() => {
    let active = true;
    let previous: string | null = null;
    try {
      previous = localStorage.getItem("studio-last-document");
    } catch {}
    if (previous)
      api<DocumentState>(`/documents/${previous}`)
        .then((state) => {
          if (active) adopt(state);
        })
        .catch(() => {
          try {
            localStorage.removeItem("studio-last-document");
          } catch {}
        });
    return () => {
      active = false;
    };
  }, [adopt]);
  useEffect(() => {
    api<typeof health>("/health")
      .then(setHealth)
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    localStorage.setItem("studio-theme", dark ? "dark" : "light");
  }, [dark]);
  useEffect(() => {
    if (!doc || !page) {
      setObjects(null);
      return;
    }
    let cancelled = false;
    api<Objects>(`/documents/${doc.id}/pages/${page.id}/objects`)
      .then((o) => {
        if (!cancelled) setObjects(o);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [doc?.id, doc?.revision, page?.id]);
  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    const timer = setInterval(
      () =>
        api<Job>(`/jobs/${job.id}`)
          .then(setJob)
          .catch((e) => setError(e.message)),
      700,
    );
    return () => clearInterval(timer);
  }, [job?.id, job?.status]);
  useEffect(() => {
    if (!modal) return;
    const previous = document.activeElement as HTMLElement;
    const timer = requestAnimationFrame(() => {
      const dialog = document.querySelector("[role=dialog]");
      (
        dialog?.querySelector("input,textarea,select,button") as HTMLElement
      )?.focus();
    });
    const trap = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;
      const elements = Array.from(
        document.querySelectorAll<HTMLElement>(
          "[role=dialog] button:not(:disabled),[role=dialog] input:not(:disabled),[role=dialog] select,[role=dialog] textarea",
        ),
      );
      const first = elements[0],
        last = elements[elements.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last?.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", trap);
    return () => {
      cancelAnimationFrame(timer);
      document.removeEventListener("keydown", trap);
      previous?.focus();
    };
  }, [modal]);
  useEffect(() => {
    if (message) {
      const t = setTimeout(() => setMessage(""), 5000);
      return () => clearTimeout(t);
    }
  }, [message]);
  const mutate = useCallback(
    async (op: Operation) => {
      if (!doc || mutationFlight.current) return;
      mutationFlight.current = true;
      try {
        return await run(async () => {
          const next = await api<DocumentState>(
            `/documents/${doc.id}/operations`,
            json({ revision: doc.revision, operation: op }),
          );
          adopt(next);
          setMessage("Changes saved to working copy");
          if (op.kind === "replace_image") {
            setAssetPending(false);
            setTool("select");
          }
          if (op.kind === "text") {
            setTextPending(false);
            setTool("select");
          }
          return next;
        });
      } finally {
        mutationFlight.current = false;
      }
    },
    [doc, run, adopt],
  );
  const history = useCallback(
    (direction: "undo" | "redo") => {
      if (!doc) return;
      void run(async () =>
        adopt(
          await api(
            `/documents/${doc.id}/history`,
            json({ revision: doc.revision, direction }),
          ),
        ),
      );
    },
    [doc, run, adopt],
  );
  const save = useCallback(
    (subset = false) => {
      if (!doc || busy) return;
      if (
        assetPending ||
        textPending ||
        (span &&
          (text !== span.text ||
            rect.some((v, i) => Math.abs(v - span.rect[i]) > 0.1) ||
            Math.abs(fontSize - span.size) > 0.1 ||
            color !== span.color ||
            bold !== !!(span.flags & 16) ||
            italic !== !!(span.flags & 2) ||
            underline ||
            fontFamily !== "helv"))
      ) {
        setError(
          "Apply the text edit or place the pending image before exporting. Escape cancels the selection.",
        );
        return;
      }
      void run(async () => {
        await download(
          `/documents/${doc.id}/export`,
          doc.name.replace(/\.pdf$/i, "") + "-edited.pdf",
          json({
            page_ids: subset
              ? doc.pages
                  .filter((p) => selected.includes(p.id))
                  .map((p) => p.id)
              : null,
            password,
          }),
        );
        setMessage("Export downloaded. Your original file is unchanged.");
        setModal("");
      });
    },
    [
      doc,
      selected,
      password,
      run,
      busy,
      assetPending,
      textPending,
      span,
      text,
      rect,
      fontSize,
      color,
      bold,
      italic,
      underline,
      fontFamily,
    ],
  );
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setModal("");
        setSpan(null);
        setTool("select");
        setAssetPending(false);
        setTextPending(false);
        setImageXref(null);
        return;
      }
      if (
        (e.target as HTMLElement).matches(
          "input,textarea,select,[contenteditable]",
        )
      )
        return;
      if (
        (e.ctrlKey || e.metaKey) &&
        ["s", "z", "y", "o"].includes(e.key.toLowerCase())
      ) {
        e.preventDefault();
        if (e.key === "s") save();
        if (e.key === "o") fileInput.current?.click();
        if (e.key === "z") history(e.shiftKey ? "redo" : "undo");
        if (e.key === "y") history("redo");
      }
      if (e.key === "Escape") {
        setModal("");
        setSpan(null);
        setTool("select");
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [save, history]);
  async function upload(file: File, pw = "") {
    await run(async () => {
      try {
        const next = await openFile(file, pw);
        adopt(next);
        setPendingFile(null);
        setPassword("");
        setModal(next.kind === "docx" ? "convert" : "");
        setMessage("Document opened securely on this device");
      } catch (e) {
        if ((e as Error).message.includes("password")) {
          setPendingFile(file);
          setModal("unlock");
        } else throw e;
      }
    });
  }
  useEffect(() => {
    setAsset("");
    setAssetPending(false);
    setTextPending(false);
    setHits([]);
    setTool("select");
    setSpan(null);
    setImageXref(null);
    setBehind(false);
    setOpacity(1);
    setText("");
    setJob(null);
  }, [doc?.id]);
  useEffect(() => {
    setSpan(null);
    setImageXref(null);
    setTextPending(false);
  }, [page?.id]);
  useEffect(() => {
    if (modal === "ocr")
      api<NonNullable<typeof health>>("/health")
        .then(setHealth)
        .catch((e) => setError(e.message));
  }, [modal]);
  const chosen = selected.length ? selected : page ? [page.id] : [];
  const style = {
    text,
    font_size: fontSize,
    font: fontFamily,
    color,
    bold,
    italic,
    underline,
    align,
    opacity,
  };
  function pickSpan(s: Span) {
    setSpan(s);
    setRect(s.rect);
    setText(s.text);
    setFontSize(Math.round(s.size * 10) / 10);
    setColor(s.color);
    setBold(!!(s.flags & 16));
    setItalic(!!(s.flags & 2));
    setImageXref(null);
    setUnderline(false);
  }
  function toDoc(x: number, y: number): [number, number] {
    if (!page || !surface.current) return [0, 0];
    const r = surface.current.getBoundingClientRect();
    const px = ((x - r.left) / r.width) * page.width,
      py = ((y - r.top) / r.height) * page.height;
    const m = page.inverse;
    return [
      Math.max(
        page.bounds[0],
        Math.min(page.bounds[2], px * m[0] + py * m[2] + m[4]),
      ),
      Math.max(
        page.bounds[1],
        Math.min(page.bounds[3], px * m[1] + py * m[3] + m[5]),
      ),
    ];
  }
  function displayRect(r: Rect) {
    if (!page) return {};
    const m = page.matrix;
    const pts = [
      [r[0], r[1]],
      [r[2], r[3]],
    ].map(([x, y]) => [x * m[0] + y * m[2] + m[4], x * m[1] + y * m[3] + m[5]]);
    return {
      left: Math.min(pts[0][0], pts[1][0]) * zoom,
      top: Math.min(pts[0][1], pts[1][1]) * zoom,
      width: Math.abs(pts[1][0] - pts[0][0]) * zoom,
      height: Math.abs(pts[1][1] - pts[0][1]) * zoom,
    };
  }
  function down(e: React.PointerEvent) {
    if (tool === "select" || busy) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    const start = toDoc(e.clientX, e.clientY);
    drag.current = { start, points: [start] };
    setRect([start[0], start[1], start[0] + 1, start[1] + 1]);
  }
  function move(e: React.PointerEvent) {
    if (!drag.current) return;
    const p = toDoc(e.clientX, e.clientY),
      s = drag.current.start;
    drag.current.points.push(p);
    setRect([
      Math.min(s[0], p[0]),
      Math.min(s[1], p[1]),
      Math.max(s[0], p[0]),
      Math.max(s[1], p[1]),
    ]);
  }
  function up(e: React.PointerEvent) {
    if (!drag.current || !page || tool === "select") return;
    const d = drag.current;
    drag.current = null;
    const p = toDoc(e.clientX, e.clientY);
    let r: Rect = [
      Math.min(d.start[0], p[0]),
      Math.min(d.start[1], p[1]),
      Math.max(d.start[0], p[0]),
      Math.max(d.start[1], p[1]),
    ];
    d.points.push(p);
    if (["line", "arrow", "ink"].includes(tool)) {
      if (
        Math.hypot(p[0] - d.start[0], p[1] - d.start[1]) < 2 &&
        d.points.length < 3
      )
        return;
      r = [
        Math.max(page.bounds[0], r[0] - 0.5),
        Math.max(page.bounds[1], r[1] - 0.5),
        Math.min(page.bounds[2], r[2] + 0.5),
        Math.min(page.bounds[3], r[3] + 0.5),
      ];
    }
    if (r[2] - r[0] < 1 || r[3] - r[1] < 1) {
      setMessage("Drag a rectangle on the page to place this object.");
      return;
    }
    setRect(r);
    setSpan(null);
    if (tool === "text") {
      setTextPending(true);
      return;
    }
    if (tool === "image" || tool === "signature") {
      if (!asset) {
        setModal("image");
        return;
      }
      void mutate({
        kind: "image",
        page_id: page.id,
        rect: r,
        asset_id: asset,
        angle: imageAngle,
        opacity,
        behind,
      }).then((next) => {
        if (next) {
          setAssetPending(false);
          setTool("select");
        }
      });
      return;
    }
    if (tool === "extract_signature") {
      setModal("extract_signature");
      return;
    }
    if (tool === "crop") {
      void mutate({ kind: "crop", page_id: page.id, rect: r });
      return;
    }
    void mutate({
      kind: "annotation",
      page_id: page.id,
      rect: r,
      annotation: tool === "note" ? "text" : tool,
      points: d.points,
      ...style,
    });
  }
  async function uploadAsset(file: File) {
    if (!doc) return;
    await run(async () => {
      const form = new FormData();
      form.append("file", file);
      const a = await api<{ id: string }>(`/documents/${doc.id}/assets`, {
        method: "POST",
        body: form,
      });
      setAsset(a.id);
      setAssetPending(true);
      setModal("");
      setMessage(
        imageXref
          ? "Replacement ready. Click Replace resource to apply it."
          : "Image ready. Drag a rectangle on the page to place it.",
      );
      setTool(imageXref ? "select" : "image");
    });
  }
  function startJob(kind: string) {
    if (!doc) return;
    if (
      kind === "ocr" &&
      (!health?.ocr?.available ||
        language
          .split("+")
          .some((code) => !health.ocr_languages.includes(code)))
    ) {
      setError(
        "OCR is not ready. Check installed languages or run Install-OCR-Languages.cmd, then refresh status.",
      );
      return;
    }
    void run(async () => {
      setJob(
        await api(`/documents/${doc.id}/jobs`, json({ kind, language, mode })),
      );
      setModal("jobs");
    });
  }
  async function importPages(file: File) {
    await run(async () => {
      const next = await openFile(file);
      if (next.kind !== "pdf") throw new Error("Choose a PDF to merge.");
      setImportDoc(next);
      setImportIds(next.pages.map((p) => p.id));
      setModal("merge");
    });
  }
  function signatureBox(ratio: number): Rect {
    if (!page) return [72, 72, 252, 132];
    const width = Math.min(200, page.width - 48),
      height = Math.min(100, width / Math.max(0.1, ratio), page.height - 48);
    const display: Rect = [
      page.width - 24 - width,
      page.height - 36 - height,
      page.width - 24,
      page.height - 36,
    ];
    const m = page.inverse;
    const pts = [
      [display[0], display[1]],
      [display[2], display[3]],
    ].map(([x, y]) => [x * m[0] + y * m[2] + m[4], x * m[1] + y * m[3] + m[5]]);
    return [
      Math.min(pts[0][0], pts[1][0]),
      Math.min(pts[0][1], pts[1][1]),
      Math.max(pts[0][0], pts[1][0]),
      Math.max(pts[0][1], pts[1][1]),
    ];
  }
  async function addSignatureImage(file: File): Promise<boolean> {
    if (!doc || !page) return false;
    return Boolean(
      await run(async () => {
        const form = new FormData();
        form.append("file", file);
        form.append("signature", "true");
        const asset = await api<{ id: string; width: number; height: number }>(
          `/documents/${doc.id}/assets`,
          { method: "POST", body: form },
        );
        const next = await mutate({
          kind: "image",
          page_id: page.id,
          rect: signatureBox(asset.width / asset.height),
          asset_id: asset.id,
          angle: page.rotation,
          opacity: 1,
          behind: false,
          signature: true,
        });
        if (!next) return false;
        setAssetPending(false);
        setTool("select");
        setModal("");
        setMessage("Signature placed on the page and ready to export.");
        return true;
      }),
    );
  }
  async function addSignatureText(value: string): Promise<boolean> {
    if (!page) return false;
    const next = await mutate({
      kind: "text",
      page_id: page.id,
      rect: signatureBox(3),
      angle: page.rotation,
      text: value,
      font: "tiro",
      italic: true,
      font_size: Math.max(8, Math.min(26, 320 / Math.max(1, value.length))),
      color: "#172033",
    });
    if (!next) return false;
    setModal("");
    setTool("select");
    setMessage("Typed signature placed and ready to export.");
    return true;
  }
  const tools: { id: Tool; label: string; icon: React.ReactNode }[] = [
    { id: "select", label: "Select & edit", icon: <MousePointer2 /> },
    { id: "text", label: "Add text", icon: <Type /> },
    { id: "image", label: "Add image", icon: <ImageIcon /> },
    { id: "highlight", label: "Highlight", icon: <Highlighter /> },
    { id: "signature", label: "Signature", icon: <PenTool /> },
    {
      id: "extract_signature",
      label: "Extract signature PNG",
      icon: <Scissors />,
    },
    { id: "rect", label: "Shape", icon: <Square /> },
    { id: "note", label: "Comment", icon: <MessageSquare /> },
  ];
  return (
    <div
      className="app"
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        if (e.dataTransfer.files[0]) void upload(e.dataTransfer.files[0]);
      }}
    >
      <input
        ref={fileInput}
        type="file"
        accept=".pdf,.docx"
        hidden
        onChange={(e) => {
          if (e.target.files?.[0]) void upload(e.target.files[0]);
          e.target.value = "";
        }}
      />
      <input
        ref={assetInput}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        hidden
        onChange={(e) => {
          if (e.target.files?.[0]) void uploadAsset(e.target.files[0]);
          e.target.value = "";
        }}
      />
      <input
        ref={importInput}
        type="file"
        accept=".pdf"
        hidden
        onChange={(e) => {
          if (e.target.files?.[0]) void importPages(e.target.files[0]);
          e.target.value = "";
        }}
      />
      <header className="topbar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setModal("about");
          }}
        >
          <span className="brand-mark">
            <FileText size={22} />
          </span>
          <span>
            PDF Studio <b>PRO</b>
          </span>
        </a>
        <div className="top-divider" />
        <div className="document-title">
          {doc ? (
            <>
              <FileText size={16} />
              <span>{doc.name}</span>
              <span className="local-dot" title="Working copy stored locally" />
            </>
          ) : (
            <span>Your documents. Your workspace.</span>
          )}
        </div>
        <div className="top-actions">
          <span className="privacy">
            <Shield size={13} /> Local & private
          </span>
          <button
            className="icon-button"
            title="Toggle theme"
            onClick={() => setDark(!dark)}
          >
            {dark ? <Sun /> : <Moon />}
          </button>
          <button
            className="icon-button"
            title="Settings"
            onClick={() => setModal("settings")}
          >
            <Settings />
          </button>
          <span className="avatar">S</span>
        </div>
      </header>
      <nav className="menubar">
        <div className="categories">
          {categories.map((c) => (
            <button
              className={category === c ? "category current" : "category"}
              key={c}
              onClick={() => {
                setCategory(c);
                if (c === "Convert") setModal("convert");
                if (c === "Sign") setModal("signature");
                if (c === "Annotate") setTool("highlight");
                if (c === "Edit PDF") setTool("select");
                if (c === "Organize") setSideOpen(true);
                if (c === "OCR") setModal("ocr");
                if (c === "Protect") setModal("protect");
              }}
            >
              {c}
            </button>
          ))}
        </div>
        <button
          className="export-button"
          disabled={!doc || busy || doc.kind !== "pdf"}
          onClick={() => setModal("export")}
        >
          <Download size={15} /> Export PDF <ChevronDown size={13} />
        </button>
      </nav>
      {doc?.kind === "pdf" ? (
        <>
          <div className="toolbar">
            <div className="toolbar-group">
              <button
                title="New blank document"
                onClick={() =>
                  void run(async () =>
                    adopt(await api<DocumentState>("/new", { method: "POST" })),
                  )
                }
              >
                <Plus />
              </button>
              <button
                onClick={() => fileInput.current?.click()}
                title="Open document"
              >
                <FolderOpen />
                <span>Open</span>
              </button>
              <button
                disabled={!doc.can_undo || busy}
                onClick={() => history("undo")}
                title="Undo (Ctrl+Z)"
              >
                <Undo2 />
              </button>
              <button
                disabled={!doc.can_redo || busy}
                onClick={() => history("redo")}
                title="Redo (Ctrl+Y)"
              >
                <Redo2 />
              </button>
            </div>
            <div className="toolbar-group main-tools">
              {tools.map((t) => (
                <button
                  key={t.id}
                  title={t.label}
                  className={tool === t.id ? "tool active-tool" : "tool"}
                  onClick={() => {
                    setTool(t.id);
                    setSpan(null);
                    setImageXref(null);
                    if (t.id === "image") assetInput.current?.click();
                    if (t.id === "signature") setModal("signature");
                  }}
                >
                  {t.icon}
                  <span>{t.label}</span>
                </button>
              ))}
            </div>
            <div className="toolbar-group search-tool">
              <button onClick={() => setModal("search")} title="Search">
                <Search />
              </button>
              <button
                onClick={() => setZoom(Math.max(0.25, zoom - 0.1))}
                title="Zoom out"
              >
                <ZoomOut />
              </button>
              <button className="zoom-value" onClick={() => setZoom(0.9)}>
                {Math.round(zoom * 100)}%
              </button>
              <button
                onClick={() => setZoom(Math.min(2, zoom + 0.1))}
                title="Zoom in"
              >
                <ZoomIn />
              </button>
            </div>
          </div>
          <div className={`workspace ${!sideOpen ? "collapsed" : ""}`}>
            <aside className="pages-panel">
              <div className="panel-heading">
                <span>
                  <Layers size={15} /> Pages <b>{doc.pages.length}</b>
                </span>
                <button
                  className="icon-button"
                  title="Hide thumbnails"
                  onClick={() => setSideOpen(false)}
                >
                  <PanelLeft />
                </button>
              </div>
              <div className="page-actions">
                <button
                  title="Insert blank page"
                  disabled={busy}
                  onClick={() =>
                    void mutate({ kind: "blank", page_id: page?.id })
                  }
                >
                  <Plus />
                </button>
                <button
                  title="Rotate selected pages"
                  disabled={busy}
                  onClick={() =>
                    void mutate({ kind: "rotate", page_ids: chosen, angle: 90 })
                  }
                >
                  <RotateCw />
                </button>
                <button
                  title="Duplicate selected pages"
                  disabled={busy}
                  onClick={() =>
                    void mutate({ kind: "duplicate", page_ids: chosen })
                  }
                >
                  <Copy />
                </button>
                <button
                  title="Delete selected pages"
                  disabled={busy}
                  onClick={() =>
                    void mutate({ kind: "delete_pages", page_ids: chosen })
                  }
                >
                  <Trash2 />
                </button>
              </div>
              <div className="thumb-scroll">
                <Thumbnails
                  doc={doc}
                  active={page?.id || ""}
                  selected={selected}
                  onSelect={(p, multi) => {
                    setActive(p.id);
                    if (multi)
                      setSelected((old) =>
                        old.includes(p.id)
                          ? old.filter((id) => id !== p.id)
                          : [...old, p.id],
                      );
                    else setSelected([p.id]);
                  }}
                  onReorder={(ids) => {
                    if (!busy) void mutate({ kind: "reorder", page_ids: ids });
                  }}
                />
              </div>
              <button
                className="add-pages"
                onClick={() => importInput.current?.click()}
              >
                <Plus size={14} /> Add pages from PDF
              </button>
            </aside>
            <main className="canvas-area">
              {!sideOpen && (
                <button
                  className="show-pages icon-button"
                  title="Show pages"
                  onClick={() => setSideOpen(true)}
                >
                  <PanelLeft />
                </button>
              )}
              <div className="canvas-heading">
                <span>
                  <span className="small-dot" />{" "}
                  {category === "Organize"
                    ? "Organize your document"
                    : tool === "select"
                      ? "Click existing text to edit"
                      : `Drag on the page to ${tool === "text" ? "place a text block" : tool === "crop" ? "crop the page" : tool === "extract_signature" ? "select the signature to save as PNG" : `add ${tool}`}`}
                </span>
                <span>
                  Page {page?.number} of {doc.pages.length}
                </span>
              </div>
              {doc.warnings.map((w) => (
                <div className="document-warning" key={w}>
                  {w}
                </div>
              ))}
              {objects?.scanned && (
                <div className="document-warning">
                  This page has no native text.{" "}
                  <button onClick={() => setModal("ocr")}>Run local OCR</button>
                </div>
              )}
              <div className="page-scroll">
                {page && (
                  <div
                    ref={surface}
                    className={`paper tool-${tool}`}
                    style={{
                      width: page.width * zoom,
                      height: page.height * zoom,
                    }}
                    onPointerDown={down}
                    onPointerMove={move}
                    onPointerUp={up}
                    onPointerCancel={() => {
                      drag.current = null;
                    }}
                  >
                    <img
                      className="page-render"
                      draggable={false}
                      src={renderUrl(
                        doc,
                        page,
                        Math.min(2, Math.max(1, zoom * 1.5)),
                      )}
                      alt={`Document page ${page.number}`}
                    />
                    {tool === "select" &&
                      objects?.spans.map((s, i) => (
                        <button
                          key={i}
                          className={`text-hit ${span === s ? "selected-object" : ""}`}
                          style={displayRect(s.rect)}
                          title={`Edit: ${s.text}`}
                          aria-label={`Edit text ${s.text}`}
                          onClick={() => pickSpan(s)}
                        />
                      ))}
                    {tool === "select" &&
                      objects?.images.map((im, i) => (
                        <button
                          key={`image-${i}`}
                          className="image-hit"
                          style={displayRect(im.rect)}
                          title="Select embedded image"
                          aria-label={`Select image ${i + 1}`}
                          onClick={() => {
                            setImageXref(im.xref);
                            setRect(im.rect);
                            setImageAngle(0);
                            setOpacity(1);
                            setBehind(false);
                            setSpan(null);
                          }}
                        />
                      ))}
                    {hits
                      .filter((h) => h.page_id === page.id)
                      .map((h, i) => (
                        <span
                          key={`hit-${i}`}
                          className="search-hit"
                          style={displayRect(h.rect)}
                        />
                      ))}
                    {tool === "select" && (span || imageXref) && (
                      <SelectionFrame
                        rect={rect}
                        page={page}
                        style={displayRect(rect)}
                        onChange={setRect}
                        toDoc={toDoc}
                      />
                    )}
                    {tool !== "select" && (
                      <div className="placement" style={displayRect(rect)} />
                    )}
                  </div>
                )}
              </div>
              <div className="floating-nav">
                <button
                  title="Previous page"
                  disabled={!page || page.number <= 1}
                  onClick={() => setActive(doc.pages[page!.number - 2].id)}
                >
                  <ChevronLeft />
                </button>
                <span>
                  {page?.number} <i>/</i> {doc.pages.length}
                </span>
                <button
                  title="Next page"
                  disabled={!page || page.number >= doc.pages.length}
                  onClick={() => setActive(doc.pages[page!.number].id)}
                >
                  <ChevronRight />
                </button>
                <div />
                <button
                  title="Fit page width"
                  onClick={() =>
                    setZoom(
                      Math.min(
                        1.5,
                        ((surface.current?.parentElement?.clientWidth || 800) -
                          100) /
                          (page?.width || 612),
                      ),
                    )
                  }
                >
                  <Minimize2 />
                </button>
              </div>
            </main>
            <button
              className="mobile-inspector icon-button"
              title="Toggle properties"
              onClick={() => setInspectorOpen(!inspectorOpen)}
            >
              <Settings />
            </button>
            <aside
              className={`properties ${inspectorOpen ? "inspector-open" : ""}`}
            >
              <div className="panel-heading">
                <span>Properties</span>
                <Settings size={15} />
              </div>
              <div className="property-section">
                <div className="section-label">
                  {span
                    ? "EDIT EXISTING TEXT"
                    : imageXref
                      ? "EMBEDDED IMAGE"
                      : "TEXT & APPEARANCE"}
                </div>
                {span && (
                  <p className="hint">
                    Original: {span.font}. Replacement uses a fallback font.
                    Original text is removed from the export.
                  </p>
                )}
                {imageXref ? (
                  <>
                    <button
                      className="wide-button"
                      disabled={busy}
                      onClick={() =>
                        void run(() =>
                          download(
                            `/documents/${doc.id}/pages/${page!.id}/images/${imageXref}`,
                            "signature-image.png",
                          ),
                        )
                      }
                    >
                      Export selected image as PNG
                    </button>
                    <p className="hint">
                      Resource #{imageXref}. Replacing or deleting affects all
                      uses of a shared resource. Single-use images can be moved
                      or resized; shared-resource movement is rejected.
                    </p>
                    <button
                      className="wide-button"
                      onClick={() => {
                        assetInput.current?.click();
                        setTool("image");
                      }}
                    >
                      Upload replacement
                    </button>
                    <button
                      className="wide-button"
                      disabled={!asset}
                      onClick={() =>
                        void mutate({
                          kind: "replace_image",
                          page_id: page!.id,
                          xref: imageXref,
                          asset_id: asset,
                        })
                      }
                    >
                      Replace resource
                    </button>
                    <label>
                      Rotation
                      <select
                        value={imageAngle}
                        onChange={(e) => setImageAngle(+e.target.value)}
                      >
                        {[0, 90, 180, 270].map((a) => (
                          <option key={a} value={a}>
                            {a}°
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Image opacity
                      <input
                        type="range"
                        min="0.1"
                        max="1"
                        step="0.05"
                        value={opacity}
                        onChange={(e) => setOpacity(+e.target.value)}
                      />
                    </label>
                    <button
                      className="wide-button"
                      onClick={() =>
                        void mutate({
                          kind: "transform_image",
                          page_id: page!.id,
                          xref: imageXref,
                          rect,
                          angle: imageAngle,
                          opacity,
                          behind,
                        })
                      }
                    >
                      Apply position, size & rotation
                    </button>
                    <button
                      className="wide-button danger"
                      onClick={() =>
                        void mutate({
                          kind: "delete_image",
                          page_id: page!.id,
                          xref: imageXref,
                        })
                      }
                    >
                      Remove image resource
                    </button>
                  </>
                ) : (
                  <>
                    <label>
                      Text content
                      <textarea
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                        placeholder="Select text or draw a new text box…"
                        dir="auto"
                      />
                    </label>
                    <label>
                      Font family
                      <select
                        aria-label="Font family"
                        value={fontFamily}
                        onChange={(e) =>
                          setFontFamily(e.target.value as typeof fontFamily)
                        }
                      >
                        <option value="helv">Helvetica · Latin fallback</option>
                        <option value="tiro">Times · Latin fallback</option>
                        <option value="cour">Courier · Latin fallback</option>
                      </select>
                    </label>
                    <div className="field-row">
                      <label>
                        Size
                        <input
                          type="number"
                          min="4"
                          max="300"
                          value={fontSize}
                          onChange={(e) => setFontSize(+e.target.value)}
                        />
                      </label>
                      <label>
                        Color
                        <div className="color-control">
                          <input
                            aria-label="Text color"
                            type="color"
                            value={color}
                            onChange={(e) => setColor(e.target.value)}
                          />
                          <span>{color.toUpperCase()}</span>
                        </div>
                      </label>
                    </div>
                    <div className="format-controls">
                      <button
                        className={bold ? "pressed" : ""}
                        onClick={() => setBold(!bold)}
                        title="Bold"
                      >
                        <b>B</b>
                      </button>
                      <button
                        className={italic ? "pressed" : ""}
                        onClick={() => setItalic(!italic)}
                        title="Italic"
                      >
                        <i>I</i>
                      </button>
                      <button
                        className={underline ? "pressed" : ""}
                        onClick={() => setUnderline(!underline)}
                        title="Underline"
                      >
                        <u>U</u>
                      </button>
                      <select
                        aria-label="Alignment"
                        value={align}
                        onChange={(e) =>
                          setAlign(e.target.value as typeof align)
                        }
                      >
                        <option value="left">Left</option>
                        <option value="center">Center</option>
                        <option value="right">Right</option>
                      </select>
                    </div>
                    <label className="check-label">
                      <input
                        type="checkbox"
                        checked={behind}
                        onChange={(e) => setBehind(e.target.checked)}
                      />{" "}
                      Insert images behind page content
                    </label>
                    <label>
                      Annotation opacity
                      <input
                        type="range"
                        min="0.1"
                        max="1"
                        step="0.05"
                        value={opacity}
                        onChange={(e) => setOpacity(+e.target.value)}
                      />
                    </label>
                    <button
                      className="primary wide-button"
                      disabled={busy || !text || (!span && tool !== "text")}
                      onClick={() =>
                        void mutate(
                          span
                            ? {
                                kind: "replace_text",
                                page_id: page!.id,
                                rect,
                                source_rect: span.rect,
                                original: span.text,
                                ...style,
                              }
                            : {
                                kind: "text",
                                page_id: page!.id,
                                rect,
                                ...style,
                              },
                        )
                      }
                    >
                      <Check size={14} />{" "}
                      {span ? "Apply text replacement" : "Insert text block"}
                    </button>
                    {span && (
                      <button
                        className="wide-button danger"
                        disabled={busy}
                        onClick={() =>
                          void mutate({
                            kind: "replace_text",
                            page_id: page!.id,
                            rect: span.rect,
                            original: span.text,
                            text: "",
                            font_size: span.size,
                          })
                        }
                      >
                        Delete selected text
                      </button>
                    )}
                  </>
                )}
              </div>
              <div className="property-section">
                <div className="section-label">POSITION & SIZE · PT</div>
                <div className="field-row">
                  {["X", "Y", "Right", "Bottom"].map((label, i) => (
                    <label key={label}>
                      {label}
                      <input
                        type="number"
                        value={Math.round(rect[i] * 10) / 10}
                        onChange={(e) =>
                          setRect(
                            (old) =>
                              old.map((v, n) =>
                                n === i ? +e.target.value : v,
                              ) as Rect,
                          )
                        }
                      />
                    </label>
                  ))}
                </div>
              </div>
              <div className="property-section">
                <div className="section-label">ANNOTATION TOOLS</div>
                <label>
                  Drawing tool
                  <select
                    aria-label="Annotation tool"
                    value={tool}
                    onChange={(e) => setTool(e.target.value as Tool)}
                  >
                    <option value="select">Select existing content</option>
                    <option value="highlight">Highlight</option>
                    <option value="underline">Underline</option>
                    <option value="strikeout">Strikethrough</option>
                    <option value="rect">Rectangle</option>
                    <option value="circle">Circle</option>
                    <option value="line">Line</option>
                    <option value="arrow">Arrow</option>
                    <option value="ink">Freehand drawing</option>
                    <option value="note">Sticky note</option>
                    <option value="stamp">Approved stamp</option>
                  </select>
                </label>
              </div>
              <div className="property-section">
                <div className="section-label">DOCUMENT TOOLS</div>
                <div className="utility-grid">
                  <button onClick={() => importInput.current?.click()}>
                    <Layers />
                    Merge
                  </button>
                  <button onClick={() => setModal("split")}>
                    <Scissors />
                    Split / extract
                  </button>
                  <button
                    onClick={() =>
                      void mutate({
                        kind: "reorder",
                        page_ids: doc.pages.map((p) => p.id).reverse(),
                      })
                    }
                  >
                    <ArrowUpDown />
                    Reverse
                  </button>
                  <button onClick={() => setTool("crop")}>
                    <Minimize2 />
                    Crop
                  </button>
                  <button onClick={() => setModal("watermark")}>
                    <Stamp />
                    Watermark
                  </button>
                  <button
                    onClick={() =>
                      void mutate({
                        kind: "numbers",
                        font_size: 10,
                        color: "#657085",
                      })
                    }
                  >
                    <FileText />
                    Page numbers
                  </button>
                  <button
                    onClick={() => {
                      const before = doc.size;
                      void mutate({ kind: "compress" }).then((next) => {
                        if (next)
                          setMessage(
                            `Lossless compression: ${(before / 1024).toFixed(1)} KB before → ${(next.size / 1024).toFixed(1)} KB after${next.size >= before ? " (already optimized; no size reduction)" : ""}.`,
                          );
                      });
                    }}
                  >
                    <Download />
                    Compress
                  </button>
                  <button
                    onClick={() =>
                      void run(() =>
                        download(`/documents/${doc.id}/images`, "images.zip"),
                      )
                    }
                  >
                    <ImageIcon />
                    Extract images
                  </button>
                  <button onClick={() => setModal("metadata")}>
                    <Settings />
                    Properties
                  </button>
                  <button
                    onClick={() => {
                      const popup = window.open("about:blank", "_blank");
                      if (!popup) {
                        setError("Allow popups to open the printable PDF.");
                        return;
                      }
                      void run(async () => {
                        try {
                          const response = await fetch(
                            `/api/documents/${doc.id}/export`,
                            json({}),
                          );
                          if (!response.ok)
                            throw new Error("Print preparation failed.");
                          const url = URL.createObjectURL(
                            await response.blob(),
                          );
                          popup.location.href = url;
                          setTimeout(() => URL.revokeObjectURL(url), 60000);
                        } catch (error) {
                          popup.close();
                          throw error;
                        }
                      });
                    }}
                  >
                    <Printer />
                    Print PDF
                  </button>
                </div>
              </div>
              <div className="property-tip">
                <Shield size={17} />
                <p>
                  <strong>Made for your privacy</strong>Your files stay on this
                  device. No uploads to external services.
                </p>
              </div>
            </aside>
          </div>
          <footer className="statusbar">
            <span>
              <span className="small-dot" />{" "}
              {busy ? "Processing…" : "All changes in local working copy"}
            </span>
            <span>
              {page &&
                `${Math.round(page.width)} × ${Math.round(page.height)} pt`}
              <i>·</i>
              {(doc.size / 1024).toFixed(1)} KB<i>·</i>Revision {doc.revision}
            </span>
            <span>PDF Studio Pro · 0.2.0</span>
          </footer>
        </>
      ) : (
        <main className="home">
          <div className="home-eyebrow">
            <span className="small-dot" /> YOUR LOCAL DOCUMENT WORKSPACE
          </div>
          <h1>
            Great documents.
            <br />
            <span>Without the busywork.</span>
          </h1>
          <p className="home-description">
            Edit, organize, and make every PDF your own.
            <br />A complete workspace. Everything stays on your device.
          </p>
          <button
            className="upload-zone"
            onClick={() => fileInput.current?.click()}
          >
            <span className="upload-icon">
              <Upload size={27} />
            </span>
            <strong>Drop your document here</strong>
            <span>
              or <b>browse files</b> to get started
            </span>
            <small>
              PDF & Word documents · Up to {health?.max_mb || 200} MB
            </small>
          </button>
          <div className="home-cards">
            {[
              {
                icon: <Type />,
                title: "Edit PDF",
                copy: "Make the changes that matter.",
                action: () => fileInput.current?.click(),
              },
              {
                icon: <Layers />,
                title: "Merge & organize",
                copy: "Every page in the right place.",
                action: () => fileInput.current?.click(),
              },
              {
                icon: <FileOutput />,
                title: "Convert documents",
                copy: "Move between PDF and Word.",
                action: () => {
                  setModal("convert");
                },
              },
              {
                icon: <PenTool />,
                title: "Sign & annotate",
                copy: "Add your personal touch.",
                action: () => fileInput.current?.click(),
              },
            ].map((c) => (
              <button key={c.title} onClick={c.action}>
                <span className="card-icon">{c.icon}</span>
                <ArrowUpRight className="card-arrow" size={16} />
                <strong>{c.title}</strong>
                <p>{c.copy}</p>
              </button>
            ))}
          </div>
          <button
            className="new-document"
            onClick={() =>
              void run(async () =>
                adopt(await api<DocumentState>("/new", { method: "POST" })),
              )
            }
          >
            <Plus size={14} /> Create a blank document
          </button>
          <div className="home-footer">
            <Shield size={15} /> Private by design <span>·</span> No account
            needed <span>·</span> Works offline after installation
          </div>
          {doc?.kind === "docx" && (
            <button
              className="primary wide-button"
              onClick={() => startJob("word_pdf")}
            >
              Convert {doc.name} to PDF
            </button>
          )}
        </main>
      )}
      {error && (
        <div className="toast error" role="alert">
          <span>{error}</span>
          <button aria-label="Dismiss error" onClick={() => setError("")}>
            <X size={16} />
          </button>
        </div>
      )}
      {message && (
        <div className="toast" role="status">
          <Check size={16} />
          {message}
        </div>
      )}
      {modal && (
        <div className="modal-backdrop" onClick={() => setModal("")}>
          <section
            className={`modal ${modal === "signature" ? "signature-modal" : ""}`}
            role="dialog"
            aria-modal="true"
            aria-labelledby="modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <h2 id="modal-title">
                {
                  {
                    convert: "Convert documents",
                    ocr: "Make your PDF searchable",
                    signature: "Your signature",
                    extract_signature: "Export signature as PNG",
                    export: "Export your document",
                    protect: "Password protection",
                    search: "Search document",
                    merge: "Merge preview",
                    split: "Split & extract pages",
                    settings: "Workspace settings",
                    jobs: "Document processing",
                    unlock: "Unlock PDF",
                    watermark: "Add watermark",
                    metadata: "Document properties",
                    about: "PDF Studio Pro",
                    image: "Insert an image",
                  }[modal]
                }
              </h2>
              <button
                aria-label="Close dialog"
                className="icon-button"
                onClick={() => setModal("")}
              >
                <X />
              </button>
            </div>
            {modal === "unlock" ? (
              <>
                <p>
                  Enter the document password. It is used locally and is not
                  retained.
                </p>
                <input
                  autoFocus
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  aria-label="Document password"
                />
                <button
                  className="primary wide-button"
                  onClick={() =>
                    pendingFile && void upload(pendingFile, password)
                  }
                >
                  Open PDF
                </button>
              </>
            ) : null}
            {modal === "convert" && (
              <>
                <p>
                  Local conversion with editable content. Layout reconstruction
                  is approximate; review the result before sharing.
                </p>
                {!doc ? (
                  <button
                    className="primary wide-button"
                    onClick={() => fileInput.current?.click()}
                  >
                    Choose PDF or DOCX
                  </button>
                ) : doc.kind === "docx" ? (
                  <>
                    <p className="hint">
                      Requires LibreOffice:{" "}
                      {health?.libreoffice
                        ? "available"
                        : "not detected on PATH"}
                    </p>
                    <button
                      className="primary wide-button"
                      onClick={() => startJob("word_pdf")}
                    >
                      Convert Word to PDF
                    </button>
                  </>
                ) : (
                  <>
                    <label>
                      Reconstruction mode
                      <select
                        value={mode}
                        onChange={(e) => setMode(e.target.value)}
                      >
                        <option value="editable">
                          Editable Word · text flow
                        </option>
                        <option value="layout">
                          Layout approximation · line positions
                        </option>
                      </select>
                    </label>
                    <p className="hint">
                      Scanned pages need OCR first. Tables, columns and headers
                      may need manual correction.
                    </p>
                    <button
                      className="primary wide-button"
                      onClick={() => startJob("docx")}
                    >
                      Convert to editable DOCX
                    </button>
                  </>
                )}
              </>
            )}
            {modal === "ocr" && (
              <>
                <p>
                  Add an invisible searchable text layer to scanned pages.
                  Native-text pages are preserved. Recognition is approximate.
                </p>
                <label>
                  Recognition language
                  <select
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                  >
                    <option
                      value="eng"
                      disabled={!health?.ocr_languages.includes("eng")}
                    >
                      English
                    </option>
                    <option
                      value="ara"
                      disabled={!health?.ocr_languages.includes("ara")}
                    >
                      Arabic
                    </option>
                    <option
                      value="eng+ara"
                      disabled={
                        !["eng", "ara"].every((code) =>
                          health?.ocr_languages.includes(code),
                        )
                      }
                    >
                      English + Arabic
                    </option>
                  </select>
                </label>
                <p className="hint">
                  Installed packs:{" "}
                  {health?.ocr_languages.join(", ") || "Tesseract not detected"}
                </p>
                <button
                  disabled={
                    busy ||
                    !doc ||
                    doc.kind !== "pdf" ||
                    !health?.ocr?.available ||
                    language
                      .split("+")
                      .some((code) => !health?.ocr_languages.includes(code))
                  }
                  className="primary wide-button"
                  onClick={() => startJob("ocr")}
                >
                  Run local OCR
                </button>
                {health?.ocr?.error && (
                  <p className="inline-error">{health.ocr.error}</p>
                )}
                {language
                  .split("+")
                  .some((code) => !health?.ocr_languages.includes(code)) && (
                  <p className="inline-error">
                    Missing:{" "}
                    {language
                      .split("+")
                      .filter((code) => !health?.ocr_languages.includes(code))
                      .join(", ")}
                    . Double-click Install-OCR-Languages.cmd in the app folder,
                    then refresh status here.
                  </p>
                )}
                <button
                  className="wide-button"
                  onClick={() =>
                    void run(async () => {
                      const result =
                        await api<NonNullable<typeof health>>("/health");
                      setHealth(result);
                      setMessage("Local tool status refreshed");
                    })
                  }
                >
                  Refresh OCR status
                </button>
              </>
            )}
            {modal === "jobs" && job && (
              <>
                <p>
                  {job.kind === "ocr"
                    ? "OCR recognition"
                    : "Document conversion"}{" "}
                  · {job.status}
                </p>
                <progress value={job.progress} max="1" />
                <p>{Math.round(job.progress * 100)}% complete</p>
                {job.error && <p className="inline-error">{job.error}</p>}
                {job.warnings?.map((w) => (
                  <p className="hint" key={w}>
                    {w}
                  </p>
                ))}
                {job.review?.map((r) => (
                  <details key={r.page}>
                    <summary>
                      Page {r.page} · OCR confidence {r.confidence}%
                    </summary>
                    <p dir="auto">{r.text}</p>
                  </details>
                ))}
                {["queued", "running"].includes(job.status) ? (
                  <button
                    className="wide-button"
                    onClick={() =>
                      void run(() =>
                        api(`/jobs/${job.id}`, { method: "DELETE" }),
                      )
                    }
                  >
                    Cancel job
                  </button>
                ) : (
                  job.status === "done" && (
                    <>
                      <button
                        className="primary wide-button"
                        onClick={() =>
                          void run(() =>
                            download(
                              `/jobs/${job.id}/download`,
                              `converted.${job.kind === "docx" ? "docx" : "pdf"}`,
                            ),
                          )
                        }
                      >
                        Download result
                      </button>
                      {job.kind !== "docx" && (
                        <button
                          className="wide-button"
                          onClick={() =>
                            void run(async () => {
                              const r = await fetch(
                                `/api/jobs/${job.id}/download`,
                              );
                              if (!r.ok)
                                throw new Error(
                                  "Could not open conversion result. Try downloading again.",
                                );
                              await upload(
                                new File([await r.blob()], "converted.pdf", {
                                  type: "application/pdf",
                                }),
                              );
                            })
                          }
                        >
                          Open result in editor
                        </button>
                      )}
                    </>
                  )
                )}
              </>
            )}
            {modal === "extract_signature" && (
              <>
                <p>
                  Save the selected area of your existing document as a PNG.
                  This works for scanned, drawn, annotated, and embedded
                  signatures. The PDF is not changed.
                </p>
                <label>
                  PNG resolution
                  <select
                    value={pngDpi}
                    onChange={(e) => setPngDpi(+e.target.value)}
                  >
                    <option value={144}>144 DPI</option>
                    <option value={300}>300 DPI</option>
                    <option value={600}>600 DPI</option>
                  </select>
                </label>
                <label className="check-label">
                  <input
                    type="checkbox"
                    checked={removeWhite}
                    onChange={(e) => setRemoveWhite(e.target.checked)}
                  />
                  Make near-white paper transparent
                </label>
                <p className="hint">
                  Transparency can remove very light marks. Leave it off to
                  preserve the selected appearance.
                </p>
                <button
                  className="primary wide-button"
                  disabled={busy || !doc || !page}
                  onClick={() =>
                    void run(async () => {
                      await download(
                        `/documents/${doc!.id}/pages/${page!.id}/region-png`,
                        "signature.png",
                        json({
                          revision: doc!.revision,
                          rect,
                          dpi: pngDpi,
                          remove_white: removeWhite,
                        }),
                      );
                      setMessage(
                        "Signature region downloaded as PNG. The PDF is unchanged.",
                      );
                      setModal("");
                      setTool("select");
                    })
                  }
                >
                  Download signature PNG
                </button>
                <button
                  className="wide-button"
                  onClick={() => {
                    setTool("extract_signature");
                    setModal("");
                    setMessage(
                      "Drag a rectangle closely around your existing signature.",
                    );
                  }}
                >
                  Select a different region
                </button>
              </>
            )}
            {modal === "signature" && (
              <SignatureDialog
                disabled={busy || !doc || doc.kind !== "pdf"}
                onImage={addSignatureImage}
                onText={addSignatureText}
              />
            )}
            {modal === "signature" && (
              <button
                className="wide-button"
                disabled={!page}
                onClick={() => {
                  setTool("extract_signature");
                  setModal("");
                  setMessage(
                    "Drag a rectangle around the signature already in your document.",
                  );
                }}
              >
                Extract existing signature as PNG
              </button>
            )}
            {modal === "image" && (
              <>
                <p>
                  Upload a PNG, JPEG or WebP, then drag its rectangle on the
                  page. Images retain their source resolution.
                </p>
                <button
                  className="primary wide-button"
                  onClick={() => assetInput.current?.click()}
                >
                  Choose image
                </button>
              </>
            )}
            {(modal === "export" || modal === "protect") && (
              <>
                <p>
                  Download a new PDF. Your original source is never overwritten.
                  Edits may invalidate existing digital signatures.
                </p>
                <label>
                  Optional export password
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="new-password"
                  />
                </label>
                <p className="hint">
                  A password encrypts the output with AES-256. Removing source
                  encryption requires its valid password when opening.
                </p>
                <button
                  className="primary wide-button"
                  disabled={!doc || doc.kind !== "pdf" || busy}
                  onClick={() => save()}
                >
                  Download PDF
                </button>
              </>
            )}
            {modal === "search" && (
              <>
                <label>
                  Find text
                  <input
                    autoFocus
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && doc)
                        void run(async () =>
                          setHits(
                            await api(
                              `/documents/${doc.id}/search?q=${encodeURIComponent(search)}`,
                            ),
                          ),
                        );
                    }}
                  />
                </label>
                <button
                  className="primary wide-button"
                  disabled={!doc || !search}
                  onClick={() =>
                    void run(async () =>
                      setHits(
                        await api(
                          `/documents/${doc!.id}/search?q=${encodeURIComponent(search)}`,
                        ),
                      ),
                    )
                  }
                >
                  Search
                </button>
                <div className="search-results">
                  {hits.map((h, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        setActive(h.page_id);
                        setModal("");
                      }}
                    >
                      Match {i + 1} · Page{" "}
                      {doc?.pages.find((p) => p.id === h.page_id)?.number}
                    </button>
                  ))}
                </div>
              </>
            )}
            {modal === "merge" && importDoc && (
              <>
                <p>
                  Append the selected pages from{" "}
                  <strong>{importDoc.name}</strong> after the current page.
                  Review and order before merging.
                </p>
                <div className="merge-preview">
                  {importDoc.pages.map((p) => (
                    <label key={p.id}>
                      <input
                        type="checkbox"
                        checked={importIds.includes(p.id)}
                        onChange={() =>
                          setImportIds((old) =>
                            old.includes(p.id)
                              ? old.filter((id) => id !== p.id)
                              : [...old, p.id],
                          )
                        }
                      />
                      <img
                        src={renderUrl(importDoc, p, 0.16)}
                        alt={`Source page ${p.number}`}
                      />
                      Page {p.number}
                    </label>
                  ))}
                </div>
                <p className="hint">
                  Output order:{" "}
                  {importIds
                    .map(
                      (id) => importDoc.pages.find((p) => p.id === id)?.number,
                    )
                    .join(", ")}
                  . Uncheck and recheck to move a page to the end.
                </p>
                <button
                  className="primary wide-button"
                  disabled={!importIds.length || busy}
                  onClick={() => {
                    void mutate({
                      kind: "insert",
                      source_id: importDoc.id,
                      page_id: page?.id,
                      page_ids: importIds,
                    }).then((next) => {
                      if (next) setModal("");
                    });
                  }}
                >
                  Merge selected pages
                </button>
              </>
            )}
            {modal === "split" && (
              <>
                <p>
                  Select pages using the thumbnail checkboxes, then export the
                  selection. Repeat for each split range; the source stays
                  intact.
                </p>
                <p>
                  {selected.length} pages selected:{" "}
                  {doc?.pages
                    .filter((p) => selected.includes(p.id))
                    .map((p) => p.number)
                    .join(", ")}
                </p>
                <button
                  className="primary wide-button"
                  disabled={!selected.length}
                  onClick={() => save(true)}
                >
                  Extract selected pages
                </button>
              </>
            )}
            {modal === "watermark" && (
              <>
                <label>
                  Watermark text
                  <input
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                  />
                </label>
                <p className="hint">
                  Adds footer text on all pages using the chosen size, color and
                  opacity.
                </p>
                <button
                  className="primary wide-button"
                  disabled={!text || busy}
                  onClick={() => {
                    void mutate({ kind: "watermark", ...style }).then(
                      (next) => {
                        if (next) setModal("");
                      },
                    );
                  }}
                >
                  Apply to all pages
                </button>
              </>
            )}
            {modal === "metadata" && (
              <>
                <p>
                  {doc?.pages.length} pages ·{" "}
                  {((doc?.size || 0) / 1024).toFixed(1)} KB
                </p>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const data = new FormData(e.currentTarget);
                    void mutate({
                      kind: "metadata",
                      metadata: Object.fromEntries(data) as Record<
                        string,
                        string
                      >,
                    }).then((next) => {
                      if (next) setModal("");
                    });
                  }}
                >
                  {["title", "author", "subject", "keywords"].map((k) => (
                    <label key={k}>
                      {k}
                      <input name={k} defaultValue={doc?.metadata?.[k] || ""} />
                    </label>
                  ))}
                  <button className="primary wide-button">
                    Save properties
                  </button>
                </form>
              </>
            )}
            {modal === "settings" && (
              <>
                <p>
                  All processing happens locally. Temporary working files are
                  removed after 24 hours on service startup. Close a document to
                  remove its workspace immediately.
                </p>
                <button className="wide-button" onClick={() => setDark(!dark)}>
                  {dark ? "Use light theme" : "Use dark theme"}
                </button>
                <p className="hint">
                  File limit: {health?.max_mb} MB. Configure limits with
                  STUDIO_* environment variables; see README.
                </p>
                {doc && (
                  <button
                    className="wide-button danger"
                    onClick={() =>
                      void run(async () => {
                        await api(`/documents/${doc.id}`, { method: "DELETE" });
                        setDoc(null);
                        try {
                          localStorage.removeItem("studio-last-document");
                        } catch {}
                        setModal("");
                      })
                    }
                  >
                    Close & delete local working copy
                  </button>
                )}
              </>
            )}
            {modal === "about" && (
              <>
                <p>
                  A local PDF editing workspace with persistent document
                  operations.
                </p>
                <p className="hint">
                  Native editing uses redaction and fallback fonts. Complex
                  layouts and conversions need review. PyMuPDF is
                  AGPL/commercial licensed; see repository licensing notes
                  before redistribution.
                </p>
                <button
                  className="primary wide-button"
                  onClick={() => setModal("")}
                >
                  Back to workspace
                </button>
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
