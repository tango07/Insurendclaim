/**
 * Integration test for the ClaimAssist chat against a REAL running backend (mock AI recommended).
 *   cd backend && LLM_PROVIDER=mock INSURE_DB_PATH=/tmp/it.db uvicorn app.main:app --port 8000
 *   cd frontend && npm run test:chat
 * Covers the slide "User Journey" steps 1–7 plus the conversational claim intake.
 */
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, beforeEach, expect, test } from "vitest";
import App from "../App";
import { session } from "../api";

beforeEach(() => session.set(null));
afterEach(() => cleanup());

const API = process.env.API_URL ?? "http://127.0.0.1:8000";

beforeAll(() => {
  const realFetch = globalThis.fetch;
  globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
    realFetch(typeof input === "string" && input.startsWith("/") ? API + input : input, init)) as typeof fetch;
  Element.prototype.scrollIntoView = () => {};
});

const T = { timeout: 15000 };

async function loginAsDaniel(u: ReturnType<typeof userEvent.setup>) {
  await screen.findByTestId("username", {}, T);
  await u.type(screen.getByTestId("username"), "daniel");
  await u.type(screen.getByTestId("password"), "wrongpass");
  await u.click(screen.getByTestId("auth-submit"));
  await screen.findByText(/Incorrect username or password/, {}, T);   // bad password handled
  await u.clear(screen.getByTestId("password"));
  await u.type(screen.getByTestId("password"), "Daniel@123");
  await u.click(screen.getByTestId("auth-submit"));
  await screen.findByTestId("current-profile", {}, T);
}

test("Daniel: chat → describe → follow-ups → AI summary → submit → speak with adjuster → slot → contact → on-site → confirmed", async () => {
  const u = userEvent.setup();
  render(<App />);

  // Step 1: open the site, log in, open the chat
  await loginAsDaniel(u);
  await screen.findByTestId("insurer-block", {}, T).catch(() => null);
  expect((await screen.findAllByText(/Northstar Motor Mutual/, {}, T)).length).toBeGreaterThan(0);
  await u.click(screen.getByTestId("open-chat"));
  await u.click(await screen.findByTestId("chat-asset-auto", {}, T));

  // Step 2: free-text question → offers Start a claim / Speak with an adjuster
  await u.type(screen.getByTestId("chat-input"), "My car was hit in a parking lot. How do I claim, and which garage nearby can repair it?");
  await u.click(screen.getByTestId("chat-send"));
  await screen.findByText(/I can help you start a claim with Northstar/, {}, T);
  expect(screen.getAllByTestId("act-speak_adjuster").length).toBeGreaterThan(0);

  // Conversational claim intake: the bot asks before summarising
  const startButtons = screen.getAllByTestId("act-start_claim");
  await u.click(startButtons[startButtons.length - 1]);
  await screen.findByText(/I'll start from what you told me/, {}, T);
  await screen.findByText(/When did this happen\?/, {}, T);
  await u.type(screen.getByTestId("chat-input"), "Yesterday around 6pm");
  await u.click(screen.getByTestId("chat-send"));
  // skip remaining questions until the review appears (wait for each question to finish loading)
  for (let i = 0; i < 8 && !screen.queryByTestId("claim-review"); i++) {
    const next = await waitFor(() => {
      if (screen.queryByTestId("claim-review")) return null;
      const live = screen.queryAllByTestId("skip-q").filter((b) => !(b as HTMLButtonElement).disabled);
      if (!live.length) throw new Error("waiting for next question");
      return live[live.length - 1];
    }, { timeout: 10000 });
    if (!next) break;
    await u.click(next);
  }
  const review = await screen.findByTestId("claim-review", {}, { timeout: 20000 });
  expect(within(review).getByText(/Guidance, not a decision/)).toBeTruthy();
  expect(within(review).getByText(/What you told me/)).toBeTruthy();
  const summary = within(review).getByTestId("summary") as HTMLTextAreaElement;
  await u.clear(summary);
  await u.type(summary, "Car hit while parked in a parking lot; rear bumper damaged. (edited)");
  await u.click(within(review).getByTestId("confirm"));
  await u.click(within(review).getByTestId("submit-claim"));
  await screen.findByText(/Your claim CLM-DEMO-.* has been submitted to Northstar/, {}, T);

  // Step 3: speak with an adjuster → list with name, office, specialization, slots
  const speak = screen.getAllByTestId("act-speak_adjuster").filter((b) => !(b as HTMLButtonElement).disabled);
  await u.click(speak[speak.length - 1]);
  await screen.findByText(/let me find a suitable adjuster/, {}, T);
  const list = await screen.findByTestId("adjuster-list", {}, T);
  expect(within(list).getByText("Maya Okafor")).toBeTruthy();
  expect(within(list).getAllByText(/Motor specialist/).length).toBe(3);
  expect(within(list).getAllByText(/Next available/).length).toBe(3);

  // Step 4: choose adjuster → asked to choose a slot
  await u.click(within(list).getByTestId("pick-adj-maya"));
  await screen.findByText(/Please choose a time slot/, {}, T);
  const slots = await screen.findByTestId("slot-list", {}, T);
  await u.click(within(slots).getAllByRole("button")[0]);

  // Step 5: slot recorded → asked for full name and contact number
  await screen.findByText(/Please share your full name and a contact number/, {}, T);
  const form = screen.getByTestId("contact-form");
  await u.type(within(form).getByLabelText("Contact number"), "12");
  await u.click(within(form).getByTestId("contact-submit"));
  expect(await within(form).findByRole("alert")).toBeTruthy(); // invalid phone handled
  await u.clear(within(form).getByLabelText("Contact number"));
  await u.type(within(form).getByLabelText("Contact number"), "+1 555 0199 123");
  await u.click(within(form).getByTestId("contact-submit"));

  // Step 6: asked for mode: audio, video, on-site, chat
  await screen.findByText(/How would you like to meet Maya/, {}, T);
  const modes = screen.getByTestId("mode-list");
  ["mode-audio", "mode-video", "mode-onsite", "mode-chat"].forEach((id) => expect(within(modes).getByTestId(id)).toBeTruthy());
  await u.click(within(modes).getByTestId("mode-onsite"));

  // Step 7: on-site → location → confirmation with instructions + directions; adjuster informed
  await screen.findByText(/Where should Maya inspect the car/, {}, T);
  await u.type(screen.getByTestId("chat-input"), "Riverton Mall car park, level 2, bay 41");
  await u.click(screen.getByTestId("chat-send"));
  const card = await screen.findByTestId("appointment-card", {}, T);
  expect(within(card).getByText(/Appointment confirmed/)).toBeTruthy();
  expect(within(card).getAllByText(/Riverton Mall car park/).length).toBeGreaterThan(0);
  expect(within(card).getByText(/Before the appointment/)).toBeTruthy();
  await screen.findByText(/Maya Okafor has been told to expect you/, {}, T);
}, 90000);


test("Typed adjuster request shows adjusters; add a second car policy; adjuster directory; logout", async () => {
  const u = userEvent.setup();
  render(<App />);
  await loginAsDaniel(u);

  // directory from DB
  const dir = await screen.findByTestId("adjuster-directory", {}, T);
  await within(dir).findByText(/Maya Okafor/, {}, T);
  expect(within(dir).getByText(/Samir Haddad/)).toBeTruthy();

  // add another car policy with a policy number
  await u.click(screen.getByTestId("add-policy"));
  const form = await screen.findByTestId("add-policy-form", {}, T);
  await within(form).findByRole("option", { name: /Northstar/ }, T);
  await u.type(within(form).getByTestId("ap-number"), "NSM-55" + String(Date.now()).slice(-4));
  await u.type(within(form).getByTestId("ap-asset"), "2019 Honda Jazz");
  await u.click(within(form).getByTestId("ap-submit"));
  await screen.findByText(/added to your profile/, {}, T);
  expect((await screen.findAllByText("2019 Honda Jazz", {}, T)).length).toBeGreaterThan(0);
  expect(screen.getAllByTestId("policy-auto").length).toBe(2);

  // typed request in chat → adjuster list appears directly (the reported bug)
  await u.click(screen.getByTestId("open-chat"));
  const assets = await screen.findAllByTestId("chat-asset-auto", {}, T);
  await u.click(assets[assets.length - 1]);  // the new Honda
  await u.type(screen.getByTestId("chat-input"), "Show me adjuster details");
  await u.click(screen.getByTestId("chat-send"));
  const list = await screen.findByTestId("adjuster-list", {}, T);
  expect(within(list).getByText("Maya Okafor")).toBeTruthy();
  expect(within(list).getAllByText(/Northstar Riverton Claims Centre|Remote team|Eastside/).length).toBeGreaterThan(0);

  await u.click(screen.getByText(/Back to policies/));
  await u.click(await screen.findByTestId("logout", {}, T));
  await screen.findByTestId("auth-submit", {}, T);
}, 60000);
