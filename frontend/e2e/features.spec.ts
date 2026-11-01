import { test, expect, Page, Download } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";
const pageErrors = new WeakMap<Page, string[]>();
test.beforeEach(async ({ page }) => {
  const errors: string[] = [];
  pageErrors.set(page, errors);
  page.on("pageerror", (error) => errors.push(error.message));
});
test.afterEach(async ({ page }) => {
  expect(pageErrors.get(page) || []).toEqual([]);
});
const root = path.resolve("..");
const python =
  process.env.STUDIO_TEST_PYTHON ||
  path.join(
    root,
    ".venv",
    process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
  );
function generate(code: string) {
  return execFileSync(python, ["-c", code], {
    cwd: root,
    env: { ...process.env, PYTHONIOENCODING: "utf-8" },
    maxBuffer: 64 * 1024 * 1024,
  });
}
const native = () =>
  generate(
    "import pymupdf as f,sys;d=f.open();p=d.new_page();p.draw_rect(p.rect,fill=(1,1,1),color=None);p.insert_text((72,90),'Review original text',fontsize=16);p.draw_polyline([(100,300),(140,340),(180,300),(220,330)],color=(0,0,0),width=3);d.new_page();sys.stdout.buffer.write(d.tobytes())",
  );
const signature = () =>
  generate(
    "from PIL import Image,ImageDraw;import io,sys;i=Image.new('RGBA',(160,80));ImageDraw.Draw(i).line([(20,40),(40,20),(70,60),(130,30)],fill=(10,20,30,255),width=5);b=io.BytesIO();i.save(b,format='PNG');sys.stdout.buffer.write(b.getvalue())",
  );
async function open(page: Page, buffer = native(), name = "review.pdf") {
  await page.goto("/");
  const response = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/documents") && r.request().method() === "POST",
  );
  await page
    .locator("input[type=file]")
    .first()
    .setInputFiles({
      name,
      mimeType: name.endsWith(".docx")
        ? "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        : "application/pdf",
      buffer,
    });
  const d = await (await response).json();
  if (d.kind === "pdf") await expect(page.locator(".paper")).toBeVisible();
  return d;
}
async function drag(page: Page, from: [number, number], to: [number, number]) {
  const b = await page.locator(".paper").boundingBox();
  if (!b) throw new Error("Missing page surface");
  await page.mouse.move(b.x + from[0] * 0.9, b.y + from[1] * 0.9);
  await page.mouse.down();
  await page.mouse.move(b.x + to[0] * 0.9, b.y + to[1] * 0.9, { steps: 12 });
  await page.mouse.up();
}
async function downloaded(page: Page, button: string) {
  const event = page.waitForEvent("download");
  await page.getByRole("button", { name: button, exact: true }).click();
  return (await (await event).path()) as string;
}
function inspect(file: string) {
  return JSON.parse(
    generate(
      `import pymupdf as f,json;d=f.open(${JSON.stringify(file)});print(json.dumps({'pages':len(d),'text':[p.get_text() for p in d],'images':[len(p.get_images()) for p in d],'annotations':[len(list(p.annots())) for p in d],'title':d.metadata['title']}))`,
    ).toString(),
  );
}
async function exportPdf(page: Page) {
  await page.getByRole("button", { name: "Export PDF", exact: true }).click();
  return downloaded(page, "Download PDF");
}
async function revision(page: Page, n: number) {
  await expect(page.locator(".statusbar")).toContainText(`Revision ${n}`);
}

test("extract an existing drawn signature region as a transparent PNG without editing the PDF", async ({
  page,
}) => {
  const doc = await open(page);
  await page.getByTitle("Extract signature PNG").click();
  await drag(page, [80, 280], [240, 360]);
  await expect(
    page.getByRole("heading", { name: "Export signature as PNG" }),
  ).toBeVisible();
  await page.getByLabel("Make near-white paper transparent").check();
  const file = await downloaded(page, "Download signature PNG");
  const info = JSON.parse(
    generate(
      `from PIL import Image;import json;i=Image.open(${JSON.stringify(file)}).convert('RGBA');print(json.dumps({'size':i.size,'alpha':i.getchannel('A').getextrema(),'ink':sum(1 for r,g,b,a in i.getdata() if min(r,g,b)<100 and a>0)}))`,
    ).toString(),
  );
  expect(info.size[0]).toBeGreaterThan(600);
  expect(info.alpha).toEqual([0, 255]);
  expect(info.ink).toBeGreaterThan(100);
  expect(
    (await (await page.request.get(`/api/documents/${doc.id}`)).json())
      .revision,
  ).toBe(0);
});

test("extract an embedded signature image at original resolution and alpha", async ({
  page,
}) => {
  const pdf = generate(
    "import pymupdf as f,sys;from PIL import Image,ImageDraw;import io;im=Image.new('RGBA',(160,80));ImageDraw.Draw(im).line([(20,40),(40,20),(70,60),(130,30)],fill=(10,20,30,255),width=5);b=io.BytesIO();im.save(b,format='PNG');d=f.open();p=d.new_page();p.insert_image(f.Rect(100,250,260,330),stream=b.getvalue());sys.stdout.buffer.write(d.tobytes())",
  );
  await open(page, pdf);
  await page.getByLabel("Select image 1", { exact: true }).click();
  const file = await downloaded(page, "Export selected image as PNG");
  const info = JSON.parse(
    generate(
      `from PIL import Image;import json;i=Image.open(${JSON.stringify(file)});print(json.dumps({'size':i.size,'alpha':i.getchannel('A').getextrema()}))`,
    ).toString(),
  );
  expect(info.size).toEqual([160, 80]);
  expect(info.alpha).toEqual([0, 255]);
});

for (const kind of ["drawn", "uploaded", "typed", "reused"])
  test(`${kind} signature persists in exported PDF and is visible`, async ({
    page,
  }) => {
    await open(page);
    await page.getByLabel("Insert images behind page content").check();
    await page.getByLabel("Annotation opacity").fill("0.1");
    if (kind === "reused")
      await page.evaluate(
        (data) => localStorage.setItem("studio-signature", data),
        "data:image/png;base64," + signature().toString("base64"),
      );
    await page.getByTitle("Signature", { exact: true }).click();
    if (kind === "typed") {
      await page.getByLabel("Your name or signature text").fill("My Signature");
      await page
        .getByRole("button", { name: "Use typed signature", exact: true })
        .click();
    } else if (kind === "uploaded") {
      await page.getByLabel("Signature image file").setInputFiles({
        name: "my-signature.png",
        mimeType: "image/png",
        buffer: signature(),
      });
    } else if (kind === "reused")
      await page
        .getByRole("button", { name: "Reuse saved signature", exact: true })
        .click();
    else {
      await expect(
        page.getByRole("button", { name: "Use signature", exact: true }),
      ).toBeDisabled();
      const box = await page.getByLabel("Draw signature").boundingBox();
      if (!box) throw new Error("Missing canvas");
      await page.mouse.move(box.x + 40, box.y + 70);
      await page.mouse.down();
      await page.mouse.move(box.x + 100, box.y + 30, { steps: 8 });
      await page.mouse.move(box.x + 160, box.y + 90, { steps: 8 });
      await page.mouse.up();
      await page
        .getByRole("button", { name: "Use signature", exact: true })
        .click();
    }
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await revision(page, 1);
    const file = await exportPdf(page);
    const output = inspect(file);
    if (kind === "typed") expect(output.text[0]).toContain("My Signature");
    else expect(output.images[0]).toBeGreaterThan(0);
    const ink = Number(
      generate(
        `import pymupdf as f;d=f.open(${JSON.stringify(file)});p=d[0];pix=p.get_pixmap(clip=f.Rect(p.rect.width-240,p.rect.height-170,p.rect.width,p.rect.height));print(sum(1 for i in range(0,len(pix.samples),3) if max(pix.samples[i:i+3])<150))`,
      ).toString(),
    );
    expect(ink).toBeGreaterThan(20);
  });

test("insert text, reject unapplied drafts on export, then reopen persistent text", async ({
  page,
}) => {
  await open(page);
  await page.getByTitle("Add text", { exact: true }).click();
  await page.getByLabel("Text content").fill("New paragraph survives export");
  await drag(page, [70, 160], [450, 220]);
  await page.getByRole("button", { name: "Export PDF", exact: true }).click();
  await page.getByRole("button", { name: "Download PDF", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Apply the text edit");
  await page.getByLabel("Close dialog").click();
  await page
    .getByRole("button", { name: "Insert text block", exact: true })
    .click();
  await revision(page, 1);
  const output = inspect(await exportPdf(page));
  expect(output.text[0]).toContain("New paragraph survives export");
});

test("image upload placement, move/resize, replacement, PNG/ZIP export, deletion and undo", async ({
  page,
}) => {
  await open(page);
  await page.getByTitle("Add image", { exact: true }).click();
  await page.locator("input[type=file]").nth(1).setInputFiles({
    name: "photo.png",
    mimeType: "image/png",
    buffer: signature(),
  });
  await expect(page.locator(".toast[role=status]")).toContainText(
    "Image ready",
  );
  await drag(page, [100, 200], [260, 280]);
  await revision(page, 1);
  await page.getByLabel("Select image 1", { exact: true }).click();
  await page.getByLabel("X", { exact: true }).fill("120");
  await page
    .getByRole("button", { name: "Apply position, size & rotation" })
    .click();
  await revision(page, 2);
  await page
    .getByLabel("Select image 2", { exact: true })
    .click()
    .catch(async () => {
      await page.getByLabel("Select image 1", { exact: true }).click();
    });
  const png = await downloaded(page, "Export selected image as PNG");
  expect(png).toBeTruthy();
  const zip = await downloaded(page, "Extract images");
  expect(
    Number(
      generate(
        `import zipfile;print(len(zipfile.ZipFile(${JSON.stringify(zip)}).namelist()))`,
      ).toString(),
    ),
  ).toBeGreaterThan(0);
  await page.getByRole("button", { name: "Remove image resource" }).click();
  await revision(page, 3);
  await page.getByTitle("Undo (Ctrl+Z)").click();
  await revision(page, 4);
});

for (const annotation of [
  "highlight",
  "underline",
  "strikeout",
  "rect",
  "circle",
  "line",
  "arrow",
  "ink",
  "note",
  "stamp",
])
  test(`annotation ${annotation} persists in exported PDF`, async ({
    page,
  }) => {
    await open(page);
    await page.getByLabel("Annotation tool").selectOption(annotation);
    if (annotation === "note")
      await page.getByLabel("Text content").fill("Review this");
    await drag(
      page,
      [100, 190],
      annotation === "line" || annotation === "arrow" ? [260, 190] : [260, 230],
    );
    await revision(page, 1);
    const output = inspect(await exportPdf(page));
    expect(output.annotations[0]).toBe(1);
  });

test("organize last page, keyboard reorder, merge preview, rotate, reverse, split and delete", async ({
  page,
}) => {
  await open(page);
  await page.getByRole("button", { name: "Page 2", exact: true }).click();
  await page.getByTitle("Duplicate selected pages").click();
  await revision(page, 1);
  await page.getByTitle("Insert blank page").click();
  await revision(page, 2);
  await page.getByTitle("Rotate selected pages").click();
  await revision(page, 3);
  const handles = page.locator(".drag-handle");
  await handles.first().focus();
  await page.keyboard.press("Space");
  await expect(handles.first()).toHaveAttribute("aria-pressed", "true");
  // dnd-kit's keyboard sensor installs its window listener on the next turn.
  // Wait for paint/setup rather than firing the next key in that same turn.
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  );
  await page.keyboard.press("ArrowDown");
  const targetId = await page
    .locator(".thumbnail")
    .nth(1)
    .getAttribute("data-page-id");
  await expect(page.locator("[id^=DndLiveRegion]")).toContainText(
    `over droppable area ${targetId}`,
  );
  await page.keyboard.press("Space");
  await revision(page, 4);
  await page.getByRole("button", { name: "Reverse", exact: true }).click();
  await revision(page, 5);
  await page.locator("input[type=file]").nth(2).setInputFiles({
    name: "merge.pdf",
    mimeType: "application/pdf",
    buffer: native(),
  });
  await expect(
    page.getByRole("heading", { name: "Merge preview" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Merge selected pages" }).click();
  await revision(page, 6);
  await page.getByLabel("Select page 1", { exact: true }).check();
  await page
    .getByRole("button", { name: "Split / extract", exact: true })
    .click();
  const subset = inspect(await downloaded(page, "Extract selected pages"));
  expect(subset.pages).toBeGreaterThan(0);
  expect(subset.pages).toBeLessThan(6);
  await page.getByTitle("Delete selected pages").click();
  await revision(page, 7);
  expect(inspect(await exportPdf(page)).pages).toBeLessThan(6);
});

test("PDF to Word conversion produces editable DOCX", async ({ page }) => {
  await open(page);
  await page.getByRole("button", { name: "Convert", exact: true }).click();
  await page.getByRole("button", { name: "Convert to editable DOCX" }).click();
  await expect(page.getByRole("dialog")).toContainText("done", {
    timeout: 30000,
  });
  const file = await downloaded(page, "Download result");
  const text = generate(
    `from docx import Document;d=Document(${JSON.stringify(file)});print('\\n'.join(p.text for p in d.paragraphs))`,
  ).toString();
  expect(text).toContain("Review original text");
});

test("Word to PDF conversion and open result in editor", async ({ page }) => {
  const word = generate(
    "from docx import Document;import io,sys;d=Document();d.add_paragraph('Word UI conversion');d.add_table(rows=2,cols=2).cell(0,0).text='Table cell';d.sections[0].header.paragraphs[0].text='Header kept';b=io.BytesIO();d.save(b);sys.stdout.buffer.write(b.getvalue())",
  );
  await open(page, word, "source.docx");
  await page
    .getByRole("button", { name: "Convert Word to PDF", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("done", {
    timeout: 30000,
  });
  const output = inspect(await downloaded(page, "Download result"));
  expect(output.text.join(" ")).toContain("Word UI conversion");
  expect(output.text.join(" ")).toContain("Table cell");
  expect(output.text.join(" ")).toContain("Header kept");
  await page.getByRole("button", { name: "Open result in editor" }).click();
  await expect(page.locator(".paper")).toBeVisible();
});

test("local bilingual OCR creates searchable result and opens it", async ({
  page,
}) => {
  const scan = generate(
    "from PIL import Image,ImageDraw,ImageFont;import pymupdf as f,io,sys;im=Image.new('RGB',(1400,800),'white');draw=ImageDraw.Draw(im);font=ImageFont.truetype('backend/app/fonts/DejaVuSans.ttf',70);draw.text((80,200),'SEARCHABLE DOCUMENT',font=font,fill='black');draw.text((200,400),'مرحبا بالعالم',font=font,fill='black',direction='rtl');b=io.BytesIO();im.save(b,format='PNG');d=f.open();p=d.new_page(width=700,height=400);p.insert_image(p.rect,stream=b.getvalue());sys.stdout.buffer.write(d.tobytes())",
  );
  await open(page, scan);
  await page.getByRole("button", { name: "OCR", exact: true }).click();
  await page.getByLabel("Recognition language").selectOption("eng+ara");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Run local OCR" })
    .click();
  await expect(page.getByRole("dialog")).toContainText("done", {
    timeout: 30000,
  });
  const result = inspect(await downloaded(page, "Download result"));
  expect(result.text[0]).toContain("SEARCHABLE");
  expect(result.text[0]).toMatch(/[\u0600-\u06ff]/);
  await page.getByRole("button", { name: "Open result in editor" }).click();
  await expect(page.locator(".paper")).toBeVisible();
});

test("OCR preflight prevents launching when language packs are absent", async ({
  page,
}) => {
  await page.route("**/api/health", (route) =>
    route.fulfill({
      json: {
        status: "ok",
        libreoffice: true,
        ocr_languages: [],
        ocr: { available: true, error: "No OCR language data was found." },
        max_mb: 200,
        max_pages: 2000,
      },
    }),
  );
  await open(page);
  await page.getByRole("button", { name: "OCR", exact: true }).click();
  await expect(
    page.getByRole("dialog").getByRole("button", { name: "Run local OCR" }),
  ).toBeDisabled();
  await expect(page.getByRole("dialog")).toContainText(
    "Install-OCR-Languages.cmd",
  );
  await expect(
    page.getByRole("button", { name: "Refresh OCR status" }),
  ).toBeEnabled();
});

test("watermark, numbers, metadata, compression, search, print and close", async ({
  page,
}) => {
  const doc = await open(page);
  await page.getByRole("button", { name: "Watermark", exact: true }).click();
  await page.getByLabel("Watermark text").fill("PRIVATE");
  await page.getByRole("button", { name: "Apply to all pages" }).click();
  await revision(page, 1);
  await page.getByRole("button", { name: "Page numbers", exact: true }).click();
  await revision(page, 2);
  await page.getByRole("button", { name: "Properties", exact: true }).click();
  await page.getByLabel("title", { exact: true }).fill("Edited metadata");
  await page.getByRole("button", { name: "Save properties" }).click();
  await revision(page, 3);
  await page.getByRole("button", { name: "Compress", exact: true }).click();
  await revision(page, 4);
  await expect(page.locator(".toast[role=status]")).toContainText("before");
  await page.getByTitle("Search", { exact: true }).click();
  await page.getByLabel("Find text").fill("Review");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Search", exact: true })
    .click();
  await page.getByRole("button", { name: /Match 1/ }).click();
  await expect(page.locator(".search-hit")).toHaveCount(1);
  const popupEvent = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Print PDF" }).click();
  const popup = await popupEvent;
  await expect.poll(() => popup.url()).toContain("blob:");
  await popup.close();
  const output = inspect(await exportPdf(page));
  expect(output.title).toBe("Edited metadata");
  expect(output.text[0]).toContain("PRIVATE");
  await page.getByTitle("Settings", { exact: true }).click();
  await page
    .getByRole("button", { name: "Close & delete local working copy" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Great documents." }),
  ).toBeVisible();
  expect((await page.request.get(`/api/documents/${doc.id}`)).status()).toBe(
    404,
  );
});

test("password-protect export, reject wrong password, reopen with correct password", async ({
  page,
}) => {
  await open(page);
  await page.getByRole("button", { name: "Protect", exact: true }).click();
  await page.getByLabel("Optional export password").fill("test password");
  const file = await downloaded(page, "Download PDF");
  const data = generate(
    `import sys;sys.stdout.buffer.write(open(${JSON.stringify(file)},'rb').read())`,
  );
  await page.locator("input[type=file]").first().setInputFiles({
    name: "encrypted.pdf",
    mimeType: "application/pdf",
    buffer: data,
  });
  await expect(page.getByRole("heading", { name: "Unlock PDF" })).toBeVisible();
  await page.getByLabel("Document password").fill("wrong");
  await page.getByRole("button", { name: "Open PDF", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Unlock PDF" })).toBeVisible();
  await page.getByLabel("Document password").fill("test password");
  await page.getByRole("button", { name: "Open PDF", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("failed operation keeps its dialog and source unchanged", async ({
  page,
}) => {
  const d = await open(page);
  await page.route("**/operations", (route) =>
    route.fulfill({
      status: 422,
      json: { detail: "Simulated failed operation; original safe" },
    }),
  );
  await page.getByRole("button", { name: "Properties", exact: true }).click();
  await page.getByLabel("title", { exact: true }).fill("Must not commit");
  await page.getByRole("button", { name: "Save properties" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("alert")).toContainText(
    "Simulated failed operation",
  );
  expect(
    (await (await page.request.get(`/api/documents/${d.id}`)).json()).revision,
  ).toBe(0);
});

test("crop, zoom, fit, mobile inspector and 100-page lazy rendering", async ({
  page,
}) => {
  const hundred = generate(
    "import pymupdf as f,sys;d=f.open();[(d.new_page().insert_text((72,90),'Lazy page '+str(i+1))) for i in range(100)];sys.stdout.buffer.write(d.tobytes())",
  );
  let renders = 0;
  page.on("request", (r) => {
    if (r.url().includes("/render?")) renders++;
  });
  await open(page, hundred);
  await expect(
    page.getByRole("button", { name: "Page 100", exact: true }),
  ).toBeAttached();
  expect(renders).toBeLessThan(40);
  await page.getByTitle("Zoom in").click();
  await expect(page.locator(".zoom-value")).toHaveText("100%");
  await page.getByTitle("Zoom out").click();
  await page.getByTitle("Fit page width").click();
  await page.locator(".zoom-value").click();
  await page.getByRole("button", { name: "Crop", exact: true }).click();
  await drag(page, [40, 50], [500, 650]);
  await revision(page, 1);
  await page.setViewportSize({ width: 700, height: 850 });
  await page.getByTitle("Toggle properties").click();
  await expect(page.getByLabel("Text content")).toBeVisible();
});

test("working copy resumes after browser refresh", async ({ page }) => {
  await open(page);
  await page
    .getByLabel("Edit text Review original text", { exact: true })
    .click();
  await page.getByLabel("Text content").fill("Restored copy");
  await page.getByRole("button", { name: "Apply text replacement" }).click();
  await revision(page, 1);
  await page.reload();
  await expect(
    page.getByLabel("Edit text Restored copy", { exact: true }),
  ).toBeVisible();
  await revision(page, 1);
  expect(inspect(await exportPdf(page)).text[0]).toContain("Restored copy");
});

test("Arabic text insertion through the UI persists as Unicode", async ({
  page,
}) => {
  await open(page);
  await page.getByTitle("Add text", { exact: true }).click();
  await page.getByLabel("Text content").fill("مرحبا بالعالم");
  await drag(page, [72, 160], [460, 250]);
  await page
    .getByRole("button", { name: "Insert text block", exact: true })
    .click();
  await revision(page, 1);
  const file = await exportPdf(page);
  const text = generate(
    `import pymupdf as f,unicodedata;d=f.open(${JSON.stringify(file)});print(unicodedata.normalize('NFKC',d[0].get_text()))`,
  ).toString();
  expect(text).toContain("مرحبا بالعالم");
});

test("replace an image through the UI and export the applied replacement", async ({
  page,
}) => {
  await open(page);
  await page.getByTitle("Add image", { exact: true }).click();
  await page.locator("input[type=file]").nth(1).setInputFiles({
    name: "first.png",
    mimeType: "image/png",
    buffer: signature(),
  });
  await expect(page.locator(".toast")).toContainText("Image ready");
  await drag(page, [100, 200], [260, 280]);
  await revision(page, 1);
  await page.getByLabel("Select image 1", { exact: true }).click();
  await page.getByRole("button", { name: "Upload replacement" }).click();
  const replacement = generate(
    "from PIL import Image;import io,sys;b=io.BytesIO();Image.new('RGB',(160,80),'red').save(b,format='PNG');sys.stdout.buffer.write(b.getvalue())",
  );
  await page.locator("input[type=file]").nth(1).setInputFiles({
    name: "replacement.png",
    mimeType: "image/png",
    buffer: replacement,
  });
  await expect(page.locator(".toast")).toContainText("Replacement ready");
  await page
    .getByRole("button", { name: "Replace resource", exact: true })
    .click();
  await revision(page, 2);
  const file = await exportPdf(page);
  const pixel = JSON.parse(
    generate(
      `import pymupdf as f,json;d=f.open(${JSON.stringify(file)});print(json.dumps(d[0].get_pixmap().pixel(180,240)))`,
    ).toString(),
  );
  expect(pixel).toEqual([255, 0, 0]);
});

const scannedField = () =>
  generate(
    "from PIL import Image,ImageDraw,ImageFont;import io,pymupdf as f,sys;i=Image.new('RGB',(1224,1584),'white');draw=ImageDraw.Draw(i);draw.text((800,350),'2026/07/15',font=ImageFont.truetype('backend/app/fonts/DejaVuSans.ttf',36),fill='black');draw.line([(120,1000),(160,1040),(200,1000)],fill='blue',width=5);b=io.BytesIO();i.save(b,format='PNG');d=f.open();p=d.new_page(width=612,height=792);p.insert_image(p.rect,stream=b.getvalue());sys.stdout.buffer.write(d.tobytes())",
  );

test("edit a scanned date without OCR, resize, and persist real pixel replacement", async ({
  page,
}) => {
  await open(page, scannedField());
  await expect(
    page.getByRole("button", {
      name: "Select a scanned field to edit",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByTitle("Edit scanned field", { exact: true }).click();
  await drag(page, [395, 170], [525, 205]);
  await expect(
    page.getByAltText("Original scanned field for comparison"),
  ).toBeVisible();
  await page.getByLabel("Text content").fill("2026/08/01");
  await expect(
    page.getByLabel("Fit text to box", { exact: true }),
  ).toBeChecked();
  const frame = page.getByRole("group", {
      name: "Selected object; drag to reposition",
    }),
    before = await frame.boundingBox();
  const handle = page.getByRole("button", {
      name: "Resize bottom right",
      exact: true,
    }),
    box = await handle.boundingBox();
  if (!box || !before) throw new Error("Missing resize handle");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(
    box.x + box.width / 2 + 35,
    box.y + box.height / 2 + 25,
    { steps: 8 },
  );
  await page.mouse.up();
  expect((await frame.boundingBox())!.height).toBeGreaterThan(
    before.height + 15,
  );
  await page
    .getByRole("button", { name: "Apply scan replacement", exact: true })
    .click();
  await revision(page, 1);
  const out = inspect(await exportPdf(page));
  expect(out.text[0]).toContain("2026/08/01");
  expect(out.text[0]).not.toContain("2026/07/15");
});

test("recognize a selected date, review it, correct it, then apply", async ({
  page,
}) => {
  await open(page, scannedField());
  await expect(
    page.getByRole("button", {
      name: "Select a scanned field to edit",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByTitle("Edit scanned field", { exact: true }).click();
  await drag(page, [395, 170], [525, 205]);
  await page.getByLabel("Field recognition").selectOption("numbers");
  await page.getByLabel("OCR resolution").selectOption("400");
  await page
    .getByRole("button", { name: "Recognize selected field", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("done", {
    timeout: 30000,
  });
  await page
    .getByRole("button", { name: "Use recognized text", exact: true })
    .click();
  await expect(page.getByLabel("Text content")).toHaveValue("2026/07/15");
  await page.getByLabel("Text content").fill("2026/08/01");
  await page.getByRole("button", { name: "Apply scan replacement" }).click();
  await revision(page, 1);
  expect(inspect(await exportPdf(page)).text[0]).toContain("2026/08/01");
});

test("discard all changes restores the original pages and clears undo history", async ({
  page,
}) => {
  await open(page);
  await page
    .getByLabel("Edit text Review original text", { exact: true })
    .click();
  await page.getByLabel("Text content").fill("Changed field");
  await page.getByRole("button", { name: "Apply text replacement" }).click();
  await revision(page, 1);
  await page.getByTitle("Insert blank page").click();
  await revision(page, 2);
  await page.getByTitle("Discard all changes", { exact: true }).click();
  await page
    .getByRole("button", { name: "Discard all changes and restore original" })
    .click();
  await revision(page, 3);
  await expect(page.getByTitle("Undo (Ctrl+Z)")).toBeDisabled();
  await expect(page.getByTitle("Redo (Ctrl+Y)")).toBeDisabled();
  const out = inspect(await exportPdf(page));
  expect(out.pages).toBe(2);
  expect(out.text[0]).toContain("Review original text");
  expect(out.text[0]).not.toContain("Changed field");
});

for (const rotation of [0, 90, 180, 270])
  test(`drag and keyboard resize on a ${rotation}-degree page`, async ({
    page,
  }) => {
    const pdf = generate(
      `import pymupdf as f,sys;d=f.open();p=d.new_page();p.insert_text((200,300),'Editable text',fontsize=16);p.set_rotation(${rotation});sys.stdout.buffer.write(d.tobytes())`,
    );
    await open(page, pdf);
    await page.getByLabel("Edit text Editable text", { exact: true }).click();
    const frame = page.getByRole("group", {
        name: "Selected object; drag to reposition",
      }),
      initial = await frame.boundingBox();
    const handle = page.getByRole("button", {
      name: "Resize bottom right",
      exact: true,
    });
    await handle.focus();
    await page.keyboard.press("Shift+ArrowRight");
    await page.keyboard.press("Shift+ArrowDown");
    const resized = await frame.boundingBox();
    expect(resized!.width).toBeGreaterThan(initial!.width + 7);
    expect(resized!.height).toBeGreaterThan(initial!.height + 7);
    await page.getByRole("button", { name: "Apply text replacement" }).click();
    await revision(page, 1);
    expect(inspect(await exportPdf(page)).text[0]).toContain("Editable text");
  });

test("desktop Quit UI stops the app and shows a closed state", async ({
  page,
}) => {
  await page.route("**/api/health", async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      json: { ...(await response.json()), desktop_mode: true },
    });
  });
  await page.route("**/api/shutdown", (route) =>
    route.fulfill({ json: { stopping: true } }),
  );
  await open(page);
  await page.getByTitle("Settings", { exact: true }).click();
  await page.getByRole("button", { name: "Quit app", exact: true }).click();
  await page.getByRole("button", { name: "Quit app now", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "PDF Studio Pro has closed" }),
  ).toBeVisible();
});
