import { useRef, useState } from "react";

function savedSignature() {
  try {
    const value = localStorage.getItem("studio-signature");
    return value?.startsWith("data:image/png;base64,") ? value : null;
  } catch {
    return null;
  }
}
export default function SignatureDialog({
  disabled,
  onImage,
  onText,
}: {
  disabled: boolean;
  onImage: (file: File) => Promise<boolean>;
  onText: (text: string) => Promise<boolean>;
}) {
  const canvas = useRef<HTMLCanvasElement>(null),
    input = useRef<HTMLInputElement>(null),
    drawing = useRef(false);
  const [ink, setInk] = useState(false),
    [name, setName] = useState(""),
    [remember, setRemember] = useState(false),
    [saved, setSaved] = useState(savedSignature),
    [error, setError] = useState("");
  function point(e: React.PointerEvent<HTMLCanvasElement>) {
    const c = canvas.current!,
      r = c.getBoundingClientRect();
    return [
      ((e.clientX - r.left) * c.width) / r.width,
      ((e.clientY - r.top) * c.height) / r.height,
    ];
  }
  async function useDrawing() {
    const c = canvas.current;
    if (!c || !ink) return;
    const blob = await new Promise<Blob | null>((resolve) =>
      c.toBlob(resolve, "image/png"),
    );
    if (!blob) {
      setError("Could not create the signature image. Please draw again.");
      return;
    }
    if (
      await onImage(new File([blob], "signature.png", { type: "image/png" }))
    ) {
      if (remember) {
        try {
          localStorage.setItem("studio-signature", c.toDataURL("image/png"));
        } catch {
          setError("Signature was added, but browser storage is unavailable.");
        }
      }
    }
  }
  return (
    <>
      <p>
        Draw, upload, or type your own visual signature. It will be placed
        visibly on the current page, ready to reposition and export. This is not
        a digital certificate signature.
      </p>
      <canvas
        ref={canvas}
        width={700}
        height={220}
        aria-label="Draw signature"
        onPointerDown={(e) => {
          if (disabled) return;
          const c = e.currentTarget,
            ctx = c.getContext("2d")!,
            [x, y] = point(e);
          c.setPointerCapture(e.pointerId);
          drawing.current = true;
          ctx.lineWidth = 3;
          ctx.lineCap = "round";
          ctx.strokeStyle = "#172033";
          ctx.fillStyle = "#172033";
          ctx.beginPath();
          ctx.arc(x, y, 1.5, 0, Math.PI * 2);
          ctx.fill();
          ctx.beginPath();
          ctx.moveTo(x, y);
          setInk(true);
        }}
        onPointerMove={(e) => {
          if (!drawing.current) return;
          const ctx = e.currentTarget.getContext("2d")!,
            [x, y] = point(e);
          ctx.lineTo(x, y);
          ctx.stroke();
        }}
        onPointerUp={() => {
          drawing.current = false;
        }}
        onPointerCancel={() => {
          drawing.current = false;
        }}
      />
      <div className="modal-actions">
        <button
          disabled={disabled}
          onClick={() => {
            canvas.current?.getContext("2d")?.clearRect(0, 0, 700, 220);
            setInk(false);
          }}
        >
          Clear
        </button>
        <button disabled={disabled} onClick={() => input.current?.click()}>
          Upload signature image
        </button>
        <button
          className="primary"
          disabled={disabled || !ink}
          onClick={() => void useDrawing()}
        >
          Use signature
        </button>
      </div>
      <input
        ref={input}
        aria-label="Signature image file"
        hidden
        type="file"
        accept="image/png,image/jpeg,image/webp"
        onChange={(e) => {
          if (e.target.files?.[0]) void onImage(e.target.files[0]);
          e.target.value = "";
        }}
      />
      <label className="check-label">
        <input
          type="checkbox"
          checked={remember}
          onChange={(e) => setRemember(e.target.checked)}
        />
        Save this drawing in this browser for reuse
      </label>
      {saved && (
        <div className="modal-actions">
          <button
            disabled={disabled}
            onClick={() =>
              void (async () => {
                try {
                  const response = await fetch(saved);
                  await onImage(
                    new File([await response.blob()], "signature.png", {
                      type: "image/png",
                    }),
                  );
                } catch {
                  setError(
                    "Saved signature could not be loaded. Draw or upload it again.",
                  );
                }
              })()
            }
          >
            Reuse saved signature
          </button>
          <button
            disabled={disabled}
            onClick={() => {
              try {
                localStorage.removeItem("studio-signature");
                setSaved(null);
              } catch {
                setError("Could not remove saved signature.");
              }
            }}
          >
            Delete saved signature
          </button>
        </div>
      )}
      <label>
        Your name or signature text
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          dir="auto"
          autoComplete="off"
        />
      </label>
      <button
        className="wide-button"
        disabled={disabled || !name.trim()}
        onClick={() => void onText(name.trim())}
      >
        Use typed signature
      </button>
      {error && (
        <p className="inline-error" role="alert">
          {error}
        </p>
      )}
      <p className="hint">
        After placing, use Select & edit to move or resize the signature.
        Changes to a signed PDF can invalidate existing digital signatures.
      </p>
    </>
  );
}
