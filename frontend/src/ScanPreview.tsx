import { useEffect, useState } from "react";
import { Rect, json } from "./api";
export default function ScanPreview({
  docId,
  pageId,
  revision,
  rect,
}: {
  docId: string;
  pageId: string;
  revision: number;
  rect: Rect;
}) {
  const [url, setUrl] = useState(""),
    [error, setError] = useState("");
  const key = rect.join(",");
  useEffect(() => {
    let active = true,
      objectUrl = "";
    const controller = new AbortController();
    setUrl("");
    setError("");
    fetch(`/api/documents/${docId}/pages/${pageId}/region-png`, {
      ...json({ revision, rect, dpi: 144, remove_white: false }),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok)
          throw new Error("Reselect the source area to preview it.");
        return response.blob();
      })
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        if (active) setUrl(objectUrl);
        else URL.revokeObjectURL(objectUrl);
      })
      .catch((error) => {
        if (active && error.name !== "AbortError") setError(error.message);
      });
    return () => {
      active = false;
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [docId, pageId, revision, key]);
  return (
    <div className="scan-preview">
      <strong>Original scan area</strong>
      {url ? (
        <img src={url} alt="Original scanned field for comparison" />
      ) : (
        <p>{error || "Loading original field…"}</p>
      )}
      <p>
        OCR can misread digits and Arabic. Compare this image and correct the
        text before applying.
      </p>
    </div>
  );
}
