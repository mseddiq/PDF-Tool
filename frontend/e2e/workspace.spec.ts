import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";
const root = path.resolve("..");
test("upload, genuine text editing, history, page tools and export", async ({
  page,
}) => {
  const pdf = execFileSync(
    path.join(
      root,
      ".venv",
      process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
    ),
    [
      "-c",
      "import pymupdf as f,sys;d=f.open();p=d.new_page();p.insert_text((72,90),'Original editable text',fontsize=16);p.insert_text((72,180),'Keep this content');d.new_page();sys.stdout.buffer.write(d.tobytes())",
    ],
  );
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Great documents." }),
  ).toBeVisible();
  await page.locator("input[type=file]").first().setInputFiles({
    name: "browser-test.pdf",
    mimeType: "application/pdf",
    buffer: pdf,
  });
  await expect(
    page.getByLabel("Edit text Original editable text", { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Edit text Original editable text", { exact: true })
    .click();
  await page.getByLabel("Text content").fill("Changed text");
  await page.getByRole("button", { name: "Apply text replacement" }).click();
  await expect(
    page.getByLabel("Edit text Changed text", { exact: true }),
  ).toBeVisible();
  await page.getByTitle("Undo (Ctrl+Z)").click();
  await expect(
    page.getByLabel("Edit text Original editable text", { exact: true }),
  ).toBeVisible();
  await page.getByTitle("Redo (Ctrl+Y)").click();
  await expect(
    page.getByLabel("Edit text Changed text", { exact: true }),
  ).toBeVisible();
  await page.getByTitle("Insert blank page").click();
  await expect(
    page.getByRole("button", { name: "Page 3", exact: true }),
  ).toBeVisible();
  await page.getByTitle("Rotate selected pages").click();
  await expect
    .poll(async () =>
      Math.round(
        await page
          .locator(".paper")
          .evaluate((el) => el.getBoundingClientRect().width),
      ),
    )
    .toBe(758);
  await page.screenshot({
    path: test.info().outputPath("workspace.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Export PDF", exact: true }).click();
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download PDF", exact: true }).click();
  const file = await downloaded;
  const filename = await file.path();
  const text = execFileSync(
    path.join(
      root,
      ".venv",
      process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
    ),
    [
      "-c",
      "import pymupdf as f,sys;d=f.open(sys.argv[1]);print(d[0].get_text());print(len(d))",
      filename!,
    ],
  ).toString();
  expect(text).toContain("Changed text");
  expect(text).not.toContain("Original editable text");
  expect(text).toContain("Keep this content");
  expect(text).toContain("3");
});
test("theme and responsive home", async ({ page }) => {
  await page.goto("/");
  await page.getByTitle("Toggle theme").click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("button", { name: /Drop your document here/ }),
  ).toBeVisible();
  await page.screenshot({
    path: test.info().outputPath("mobile.png"),
    fullPage: true,
  });
});
