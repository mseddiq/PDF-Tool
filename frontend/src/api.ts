export type Rect = [number, number, number, number];
export type Page = {
  id: string;
  number: number;
  width: number;
  height: number;
  rotation: number;
  bounds: Rect;
  inverse: number[];
  matrix: number[];
};
export type DocumentState = {
  id: string;
  name: string;
  kind: "pdf" | "docx";
  revision: number;
  pages: Page[];
  warnings: string[];
  size: number;
  metadata: Record<string, string>;
  can_undo: boolean;
  can_redo: boolean;
};
export type Span = {
  text: string;
  rect: Rect;
  font: string;
  can_reuse_font?: boolean;
  size: number;
  color: string;
  flags: number;
  source?: "native" | "ocr" | "hidden";
  angle?: number;
};
export type Objects = {
  spans: Span[];
  images: {
    xref: number;
    rect: Rect;
    width: number;
    height: number;
    background?: boolean;
  }[];
  scanned: boolean;
  has_ocr?: boolean;
  warning: string;
};
type Style = {
  font?: "helv" | "tiro" | "cour" | "original";
  text?: string;
  font_size?: number;
  fit_text?: boolean;
  background_color?: string;
  color?: string;
  bold?: boolean;
  italic?: boolean;
  underline?: boolean;
  align?: "left" | "center" | "right";
  opacity?: number;
};
type Target = { page_id: string; rect: Rect };
export type Operation = Style &
  (
    | ({
        kind: "replace_text";
        original: string;
        source_rect?: Rect;
        angle?: number;
      } & Target)
    | ({ kind: "replace_scan"; source_rect: Rect; angle?: number } & Target)
    | ({ kind: "text"; angle?: number } & Target)
    | ({
        kind: "image";
        asset_id: string;
        angle?: number;
        behind?: boolean;
        signature?: boolean;
      } & Target)
    | {
        kind: "replace_image" | "delete_image";
        page_id: string;
        xref: number;
        asset_id?: string;
      }
    | {
        kind: "transform_image";
        page_id: string;
        xref: number;
        rect: Rect;
        angle: number;
        opacity: number;
        behind?: boolean;
      }
    | ({
        kind: "annotation";
        annotation:
          | "highlight"
          | "underline"
          | "strikeout"
          | "text"
          | "rect"
          | "circle"
          | "line"
          | "arrow"
          | "ink"
          | "stamp";
        points?: number[][];
      } & Target)
    | { kind: "reorder" | "delete_pages"; page_ids: string[] }
    | { kind: "rotate" | "duplicate"; page_ids: string[]; angle?: number }
    | { kind: "blank"; page_id?: string }
    | {
        kind: "insert";
        source_id: string;
        page_id?: string;
        page_ids?: string[];
      }
    | ({ kind: "crop" } & Target)
    | { kind: "watermark" | "numbers" | "compress" }
    | { kind: "metadata"; metadata: Record<string, string> }
  );
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch("/api" + path, options);
  if (!response.ok) {
    let message = "Request failed";
    try {
      const body = await response.json();
      message =
        typeof body.detail === "string"
          ? body.detail
          : "Invalid operation. Check the selected properties.";
    } catch {}
    throw new Error(message);
  }
  return response.json();
}
export const json = (value: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(value),
});
export async function openFile(
  file: File,
  password = "",
): Promise<DocumentState> {
  const form = new FormData();
  form.append("file", file);
  form.append("password", password);
  return api("/documents", { method: "POST", body: form });
}
export async function download(
  path: string,
  filename: string,
  options: RequestInit = {},
) {
  const response = await fetch("/api" + path, options);
  if (!response.ok) {
    const e = await response.json();
    throw new Error(e.detail || "Download failed");
  }
  const url = URL.createObjectURL(await response.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}
export function renderUrl(doc: DocumentState, page: Page, scale = 1) {
  return `/api/documents/${doc.id}/pages/${page.id}/render?scale=${scale}&revision=${doc.revision}`;
}
