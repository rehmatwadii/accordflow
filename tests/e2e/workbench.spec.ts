import { expect, test } from "../../frontend/node_modules/@playwright/test";
import type { Page } from "../../frontend/node_modules/@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { randomBytes } from "node:crypto";

const credentials = JSON.parse(
  fs.readFileSync(
    path.resolve(process.cwd(), "../.demo-credentials.json"),
    "utf8",
  ),
) as { password: string };
async function login(page: Page, role = "analyst") {
  await page.goto("/");
  await page.getByLabel("Demo persona").selectOption(role + "@lcverify.demo");
  await page.getByLabel("Password", { exact: true }).fill(credentials.password);
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await expect(
    page.getByRole("button", { name: "Sign out", exact: true }),
  ).toBeVisible();
}
async function workflow(page: Page, action: string) {
  await page.getByRole("button", { name: action, exact: true }).click();
  await page
    .getByLabel("Decision reason (required)")
    .fill("Synthetic browser test review with evidence checked.");
  if (action === "Complete Review")
    for (const c of await page.getByRole("dialog").getByRole("checkbox").all())
      await c.check();
  await page
    .getByRole("button", {
      name: "Confirm " + action.toLowerCase(),
      exact: true,
    })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
}

test("analyst dashboard, case evidence, theme and notifications", async ({
  page,
}) => {
  await login(page);
  await expect(
    page.getByRole("heading", { name: "Good", exact: false }),
  ).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/dashboard.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Toggle color theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.screenshot({
    path: "../docs/screenshots/dashboard-dark.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Toggle color theme" }).click();
  await page.getByRole("link", { name: "LC workbench", exact: true }).click();
  await page.getByLabel("Search workbench").fill("01042");
  await page
    .getByRole("button", { name: new RegExp("^LC-\\d{4}-01042$") })
    .click();
  await page.getByRole("button", { name: "Validation", exact: true }).click();
  await expect(
    page.getByText("Invoice amount tolerance", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Compare", exact: false })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "Why this result?" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close dialog" }).click();
  await page.screenshot({
    path: "../docs/screenshots/validation.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome to your workbench" }),
  ).toBeVisible();
});

test("create, upload, submit, validate, reviewer and checker approval", async ({
  page,
}) => {
  await login(page);
  await page.getByRole("button", { name: "New LC case" }).click();
  const title = "Synthetic E2E credit " + Date.now();
  await page.getByLabel("Case title", { exact: true }).fill(title);
  await page
    .getByLabel("Applicant", { exact: true })
    .fill("E2E Synthetic Importer Limited");
  await page
    .getByLabel("Beneficiary", { exact: true })
    .fill("E2E Synthetic Exporter Limited");
  await page
    .getByRole("button", { name: "Create LC case", exact: true })
    .click();
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  const caseUrl = page.url();
  await page.getByRole("button", { name: "Documents", exact: true }).click();
  for (const type of [
    "COMMERCIAL_INVOICE",
    "BILL_OF_LADING",
    "PACKING_LIST",
    "CERTIFICATE_OF_ORIGIN",
  ]) {
    await page
      .getByRole("button", { name: "Upload document", exact: true })
      .click();
    await page.getByLabel("Document type", { exact: true }).selectOption(type);
    await page
      .getByText("Advanced structured fields / sample data", { exact: true })
      .click();
    await page
      .getByRole("button", { name: "Fill sample fields for manual review" })
      .click();
    const fields = await page
      .getByLabel("Reviewed structured fields (JSON)")
      .inputValue();
    await page.getByLabel("Document file", { exact: true }).setInputFiles({
      name: type + ".json",
      mimeType: "application/json",
      buffer: Buffer.from(fields),
    });
    await expect(
      page.getByText("Reading your document and extracting fields…"),
    ).toHaveCount(0);
    await page
      .getByRole("checkbox", {
        name: "I reviewed the extracted fields against the document.",
      })
      .check();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Upload document", exact: true })
      .click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
  }
  await workflow(page, "Submit");
  await page
    .getByRole("button", { name: "Run validation", exact: true })
    .click();
  await expect(
    page.getByText("Validation Completed", { exact: true }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, "reviewer");
  await page.goto(caseUrl);
  await workflow(page, "Start Review");
  await workflow(page, "Complete Review");
  await workflow(page, "Request Approval");
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, "checker");
  await page.goto(caseUrl);
  await workflow(page, "Approve");
  await expect(
    page.getByText("Approved", { exact: true }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Audit", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Case audit trail" }),
  ).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/approved-case.png",
    fullPage: true,
  });
});

test("auditor verifies integrity and admin has no operational access", async ({
  page,
}) => {
  await login(page, "auditor");
  await page.getByRole("link", { name: "Audit explorer" }).click();
  await page.getByRole("button", { name: "Verify audit integrity" }).click();
  await expect(page.getByText(/PASS: .*audit events checked/)).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/audit.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, "admin");
  await expect(
    page.getByRole("heading", { name: "Administration", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "LC workbench", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("link", { name: "Rules catalog" }).click();
  await expect(
    page.getByRole("heading", { name: "Business rules catalog" }),
  ).toBeVisible();
});

test("administrator provisions an account, runs jobs, and the new user can manage sessions", async ({
  page,
}) => {
  await login(page, "admin");
  const email = `browser.${Date.now()}@lcverify.demo`;
  const password = "Synthetic-" + randomBytes(18).toString("hex") + "7Aa";
  await page.getByRole("button", { name: "Create demo user" }).click();
  await page
    .getByLabel("Synthetic display name")
    .fill("Synthetic Browser Analyst");
  await page.getByLabel("Demo email", { exact: true }).fill(email);
  await page.getByLabel("Initial demo password").fill(password);
  await page
    .getByLabel("Provisioning reason")
    .fill("Synthetic browser provisioning regression");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByText(email, { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Run worker cycle", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("Worker complete");
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await page.getByLabel("Email address", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await expect(
    page.getByRole("heading", { name: /Good (morning|afternoon), Synthetic/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Manage my sessions" }).click();
  await expect(
    page.getByRole("heading", { name: "Your active sessions" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close dialog" }).click();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
});

test("OCR upload fills editable fields and saves reviewed evidence", async ({
  page,
}) => {
  await login(page);
  await page.getByRole("button", { name: "New LC case" }).click();
  const title = "OCR browser case " + Date.now();
  await page.getByLabel("Case title", { exact: true }).fill(title);
  await page
    .getByLabel("Applicant", { exact: true })
    .fill("Synthetic OCR Buyer");
  await page
    .getByLabel("Beneficiary", { exact: true })
    .fill("Synthetic OCR Seller");
  await page
    .getByRole("button", { name: "Create LC case", exact: true })
    .click();
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  await page.getByRole("button", { name: "Documents", exact: true }).click();
  await page.route("**/documents/extract", (route) =>
    route.fulfill({
      json: {
        text: "Invoice No: OCR-BROWSER-1\nInvoice Date: 2026-09-24\nGrand Total: USD 500.00",
        fields: {
          number: "OCR-BROWSER-1",
          issue_date: "2026-09-24",
          amount: "500.00",
          currency: "USD",
        },
        pages: 1,
        provider: "OCR.space",
        evidence: {
          number: { source: "OCR-BROWSER-1", method: "document label" },
        },
        review_required: true,
      },
    }),
  );
  await page
    .getByRole("button", { name: "Upload document", exact: true })
    .click();
  await page.getByLabel("Document file", { exact: true }).setInputFiles({
    name: "ocr-test.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4\n%synthetic test\n%%EOF"),
  });
  await expect(page.getByLabel("Number", { exact: true })).toHaveValue(
    "OCR-BROWSER-1",
  );
  await expect(page.getByLabel("Amount", { exact: true })).toHaveValue(
    "500.00",
  );
  await expect(
    page.getByText("Document source: OCR-BROWSER-1", { exact: true }),
  ).toBeVisible();
  const advancedRequest = page.waitForRequest(
    (request) =>
      request.url().endsWith("/documents/extract") &&
      (request.postData() || "").includes('name="advanced"\r\n\r\ntrue'),
  );
  await page.getByRole("button", { name: "Try advanced OCR" }).click();
  await advancedRequest;
  await expect(
    page.getByRole("button", { name: "Try advanced OCR" }),
  ).toBeVisible();
  await page.getByLabel("Number", { exact: true }).fill("OCR-BROWSER-REVIEWED");
  await page
    .getByRole("checkbox", {
      name: "I reviewed the extracted fields against the document.",
    })
    .check();
  await page.screenshot({
    path: "../docs/screenshots/ocr-review.png",
    fullPage: true,
  });
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Upload document", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByText("OCR-BROWSER-REVIEWED", { exact: false }).first(),
  ).toBeVisible();
});

test("local document fixtures populate upload fields", async ({ page }) => {
  const manifest = process.env.LOCAL_PDF_MANIFEST;
  test.skip(!manifest, "Optional private PDF manifest; never committed");
  const samples = JSON.parse(fs.readFileSync(manifest!, "utf8")) as Array<{
    file: string;
    type: string;
    fields: Record<string, string>;
  }>;
  await login(page);
  await page.getByRole("button", { name: "New LC case" }).click();
  const title = "Local document regression " + Date.now();
  await page.getByLabel("Case title", { exact: true }).fill(title);
  await page
    .getByLabel("Applicant", { exact: true })
    .fill("Synthetic Test Buyer");
  await page
    .getByLabel("Beneficiary", { exact: true })
    .fill("Synthetic Test Seller");
  await page
    .getByRole("button", { name: "Create LC case", exact: true })
    .click();
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  await page.getByRole("button", { name: "Documents", exact: true }).click();
  for (const sample of samples) {
    await page
      .getByRole("button", { name: "Upload document", exact: true })
      .click();
    await page
      .getByLabel("Document file", { exact: true })
      .setInputFiles(sample.file);
    await expect(
      page.getByText("fields extracted with PDF text.", { exact: false }),
    ).toBeVisible();
    await expect(page.getByLabel("Document type", { exact: true })).toHaveValue(
      sample.type,
    );
    for (const [label, value] of Object.entries(sample.fields))
      await expect(page.getByLabel(label, { exact: true })).toHaveValue(value);
    await page.getByRole("button", { name: "Close dialog" }).click();
  }
});
