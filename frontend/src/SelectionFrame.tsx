import { useRef } from "react";
import { Page, Rect } from "./api";
export default function SelectionFrame({
  rect,
  page,
  style,
  onChange,
  toDoc,
}: {
  rect: Rect;
  page: Page;
  style: React.CSSProperties;
  onChange: (r: Rect) => void;
  toDoc: (x: number, y: number) => [number, number];
}) {
  const drag = useRef<{
    start: [number, number];
    before: Rect;
    resize: boolean;
  } | null>(null);
  return (
    <div
      className="selection-frame"
      style={style}
      aria-label="Selected object; drag to reposition"
      onPointerDown={(e) => {
        e.stopPropagation();
        e.currentTarget.setPointerCapture(e.pointerId);
        drag.current = {
          start: toDoc(e.clientX, e.clientY),
          before: [...rect],
          resize: (e.target as HTMLElement).dataset.resize === "true",
        };
      }}
      onPointerMove={(e) => {
        if (!drag.current) return;
        e.stopPropagation();
        const p = toDoc(e.clientX, e.clientY),
          { before, start, resize } = drag.current;
        let next: Rect = [...before];
        const b = page.bounds;
        if (resize) {
          const xIndex = page.rotation === 90 || page.rotation === 180 ? 0 : 2;
          const yIndex = page.rotation === 180 || page.rotation === 270 ? 1 : 3;
          next[xIndex] = Math.max(b[0], Math.min(b[2], p[0]));
          next[yIndex] = Math.max(b[1], Math.min(b[3], p[1]));
          if (next[2] - next[0] < 4 || next[3] - next[1] < 4) return;
        } else {
          const dx = Math.max(
              b[0] - before[0],
              Math.min(b[2] - before[2], p[0] - start[0]),
            ),
            dy = Math.max(
              b[1] - before[1],
              Math.min(b[3] - before[3], p[1] - start[1]),
            );
          next = [
            before[0] + dx,
            before[1] + dy,
            before[2] + dx,
            before[3] + dy,
          ];
        }
        onChange(next);
      }}
      onPointerUp={(e) => {
        e.stopPropagation();
        drag.current = null;
      }}
      onPointerCancel={() => {
        drag.current = null;
      }}
    >
      <span
        data-resize="true"
        className="resize-handle"
        title="Drag to resize"
      />
      <span className="selection-caption">
        Drag to move · Apply in Properties
      </span>
    </div>
  );
}
