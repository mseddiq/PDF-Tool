import { useRef } from "react";
import { Page, Rect } from "./api";
const EDGES: Record<number, Record<string, number>> = {
  0: { n: 1, s: 3, w: 0, e: 2 },
  90: { n: 0, s: 2, w: 3, e: 1 },
  180: { n: 3, s: 1, w: 2, e: 0 },
  270: { n: 2, s: 0, w: 1, e: 3 },
};
export function changeSelection(
  before: Rect,
  page: Page,
  handle: string | undefined,
  dx: number,
  dy: number,
): Rect {
  const b = page.bounds,
    next: Rect = [...before];
  if (handle) {
    for (const edge of handle) {
      const i = (EDGES[page.rotation] || EDGES[0])[edge];
      const axis = i % 2;
      let value = before[i] + (axis === 0 ? dx : dy);
      if (i < 2) value = Math.max(b[i], Math.min(before[i + 2] - 4, value));
      else value = Math.min(b[i], Math.max(before[i - 2] + 4, value));
      next[i] = value;
    }
    return next;
  }
  dx = Math.max(b[0] - before[0], Math.min(b[2] - before[2], dx));
  dy = Math.max(b[1] - before[1], Math.min(b[3] - before[3], dy));
  return [before[0] + dx, before[1] + dy, before[2] + dx, before[3] + dy];
}
const names: Record<string, string> = {
  nw: "top left",
  n: "top",
  ne: "top right",
  e: "right",
  se: "bottom right",
  s: "bottom",
  sw: "bottom left",
  w: "left",
};
export default function SelectionFrame({
  rect,
  page,
  style,
  onChange,
  toDoc,
  disabled = false,
}: {
  rect: Rect;
  page: Page;
  style: React.CSSProperties;
  onChange: (r: Rect, action?: "move" | "resize") => void;
  toDoc: (x: number, y: number) => [number, number];
  disabled?: boolean;
}) {
  const drag = useRef<{
    start: [number, number];
    before: Rect;
    handle?: string;
  } | null>(null);
  function key(e: React.KeyboardEvent, handle?: string) {
    if (
      disabled ||
      !["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)
    )
      return;
    e.preventDefault();
    e.stopPropagation();
    const step = e.shiftKey ? 10 : 1,
      x = e.key === "ArrowLeft" ? -step : e.key === "ArrowRight" ? step : 0,
      y = e.key === "ArrowUp" ? -step : e.key === "ArrowDown" ? step : 0,
      m = page.inverse;
    onChange(
      changeSelection(
        rect,
        page,
        handle,
        x * m[0] + y * m[2],
        x * m[1] + y * m[3],
      ),
      handle ? "resize" : "move",
    );
  }
  return (
    <div
      className="selection-frame"
      style={style}
      aria-label="Selected object; drag to reposition"
      role="group"
      tabIndex={disabled ? -1 : 0}
      onKeyDown={(e) => {
        if (e.target === e.currentTarget) key(e);
      }}
      onPointerDown={(e) => {
        if (disabled) return;
        e.preventDefault();
        e.stopPropagation();
        e.currentTarget.setPointerCapture(e.pointerId);
        drag.current = {
          start: toDoc(e.clientX, e.clientY),
          before: [...rect],
          handle: (e.target as HTMLElement).closest<HTMLElement>(
            "[data-handle]",
          )?.dataset.handle,
        };
      }}
      onPointerMove={(e) => {
        if (!drag.current) return;
        e.stopPropagation();
        const p = toDoc(e.clientX, e.clientY),
          d = drag.current;
        onChange(
          changeSelection(
            d.before,
            page,
            d.handle,
            p[0] - d.start[0],
            p[1] - d.start[1],
          ),
          d.handle ? "resize" : "move",
        );
      }}
      onPointerUp={(e) => {
        e.stopPropagation();
        drag.current = null;
      }}
      onLostPointerCapture={() => {
        drag.current = null;
      }}
      onPointerCancel={() => {
        if (drag.current) onChange(drag.current.before);
        drag.current = null;
      }}
    >
      {Object.keys(names).map((handle) => (
        <button
          key={handle}
          type="button"
          className={`resize-handle handle-${handle}`}
          data-handle={handle}
          aria-label={`Resize ${names[handle]}`}
          title={`Resize ${names[handle]} (arrow keys; Shift for larger steps)`}
          disabled={disabled}
          onKeyDown={(e) => key(e, handle)}
        />
      ))}
      <span className="selection-caption">
        Drag to move · Resize with handles · Apply below
      </span>
    </div>
  );
}
