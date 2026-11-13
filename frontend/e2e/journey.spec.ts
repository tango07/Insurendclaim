import { expect, test, type Page } from "@playwright/test";

const PNG = Buffer.from("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da63f8ffff3f0005fe02fea7d6a5b90000000049454e44ae426082", "hex");

async function say(page: Page, text: string) {
  await page.getByTestId("chat-input").fill(text);
  await page.getByTestId("chat-send").click();
}
async function login(page: Page) {
  await page.getByTestId("demo-daniel").click();
  await page.getByTestId("auth-submit").click();
  await expect(page.getByTestId("current-profile")).toHaveText("Daniel Reyes");
}
const lastEnabled = (page: Page, id: string) => page.locator(`[data-testid="${id}"]:not([disabled])`).last();

test("Slide journey: chat → claim via follow-ups → submit → adjuster → slot → contact → on-site → confirmed", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("ai-mode")).toContainText("Mock mode");
  await login(page);
  await expect(page.getByTestId("insurer-block").first()).toContainText("Northstar");
  await page.getByTestId("open-chat").click();
  await page.getByTestId("chat-asset-auto").click();

  await say(page, "My car was hit in a parking lot. How do I claim, and which garage nearby can repair it?");
  await expect(page.getByText(/I can help you start a claim with Northstar/)).toBeVisible();
  await lastEnabled(page, "act-start_claim").click();
  await expect(page.getByText("When did this happen?", { exact: false })).toBeVisible();
  await say(page, "Yesterday around 6pm");

  await page.getByTestId("chat-file").setInputFiles([{ name: "dent.png", mimeType: "image/png", buffer: PNG }]);
  await expect(page.getByText(/Attached: dent.png/)).toBeVisible();

  const review = page.getByTestId("claim-review");
  for (let i = 0; i < 6 && !(await review.isVisible()); i++) {
    const skip = lastEnabled(page, "skip-q");
    if (await skip.count()) await skip.click();
    await page.waitForTimeout(400);
  }
  await expect(review).toBeVisible();
  await expect(review.getByText("Guidance, not a decision")).toBeVisible();
  await review.getByTestId("summary").fill("Car hit while parked; rear bumper dented. (edited by Daniel)");
  await review.getByTestId("confirm").check();
  await review.getByTestId("submit-claim").click();
  await expect(page.getByText(/has been submitted to Northstar/)).toBeVisible();

  await lastEnabled(page, "act-speak_adjuster").click();
  const list = page.getByTestId("adjuster-list").last();
  await expect(list).toContainText("Maya Okafor");
  await list.getByTestId("pick-adj-maya").click();
  await page.getByTestId("slot-list").last().getByRole("button").first().click();
  const form = page.getByTestId("contact-form").last();
  await form.getByLabel("Contact number").fill("+1 555 0199 123");
  await form.getByTestId("contact-submit").click();
  await page.getByTestId("mode-onsite").last().click();
  await say(page, "Riverton Mall car park, level 2");

  const card = page.getByTestId("appointment-card").last();
  await expect(card).toContainText("Appointment confirmed");
  await expect(card).toContainText("dent.png");
  await expect(page.getByText(/Maya Okafor has been told to expect you/)).toBeVisible();

  await page.getByTestId("view-claim").click();
  await expect(page.getByTestId("claim-status")).toHaveText("In review");
  await expect(page.getByTestId("timeline")).toContainText("Adjuster appointment booked");
});

test("Missing policy wording shows limitation, not invented cover", async ({ page }) => {
  await page.goto("/");
  await login(page);
  await page.getByTestId("start-claim-gadget").click();
  await say(page, "I dropped my work laptop at home and the screen cracked badly.");
  await lastEnabled(page, "act-start_claim").click();
  for (let i = 0; i < 6 && !(await page.getByTestId("claim-review").isVisible()); i++) {
    const skip = lastEnabled(page, "skip-q");
    if (await skip.count()) await skip.click();
    await page.waitForTimeout(400);
  }
  await expect(page.getByText(/Limitations: an adjuster should review/)).toBeVisible();
  await expect(page.getByText(/No matching cover found/)).toBeVisible();
});
