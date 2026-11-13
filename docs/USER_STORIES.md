# User stories & acceptance criteria

Persona: **Daniel Reyes, 34**. Recently relocated, new car and home policies, unfamiliar with his cover and the claims process.

## Feature 1: Profile and policy overview

**US-1 Select or create a profile.** As a policyholder I want to pick my profile, or create one, so I see my own policies.
- AC1: The landing page lists sample profiles with name, photo/initials placeholder, city and policy count.
- AC2: I can create a profile with a full name (2–80 chars) and optional city; invalid names show an inline error.
- AC3: I can optionally attach the sample car + home policies to a new profile; otherwise I see a helpful empty state.
- AC4: The selected profile's name and avatar stay visible in the header, with a "Switch profile" action.

**US-2 See my policies and insured assets.** As Daniel I want to see what I'm insured for so I know which policy applies.
- AC1: Each policy shows product, number, status, term and its insured asset(s) with key details.
- AC2: Expanding a policy shows coverages with limit and deductible, plus exclusions and claim conditions.
- AC3: All policy data is labelled as fictional sample wording from a fictional insurer.
- AC4: A policy without loaded wording shows a warning that coverage guidance isn't available.

**US-3 Start a claim on the right asset.** As Daniel I want to start a claim from the car itself so it isn't attached to the wrong policy.
- AC1: Each insured asset has a "Get help with this …" button that opens ClaimAssist for that asset.
- AC2: The intake screen always shows the asset, policy number and policyholder the claim will be filed against.
- AC3: The API rejects an asset that doesn't belong to the selected policy, or a policy that doesn't belong to the policyholder.

## Feature 2: AI-assisted claim intake

**US-4 Describe the incident and attach evidence.**
- AC1: Free-text description (min 15 chars), optional date (not in the future) and location.
- AC2: Multiple files can be attached (JPG/PNG/WEBP/HEIC/PDF/TXT, ≤10 MB each, ≤10 files).
- AC3: Disallowed types, oversized or empty files show a clear message and are not added; the server re-validates (extension + magic bytes).

**US-5 Get structured guidance grounded in my policy.**
- AC1: The response contains a suggested category (with confidence), incident summary, relevant coverages, possible exclusions, missing information, documents to collect, next steps, limitations and attachment notes.
- AC2: Coverages and exclusions reference only codes present in the selected policy; limits and deductibles come from the database, not the model.
- AC3: If the policy has no wording, no coverage is suggested and a limitation recommends contacting an adjuster.
- AC4: With an AI key, photos are analysed by Claude's vision model and shown under "What the AI saw in your photos" (labelled AI, no cost estimates or fraud judgements). Unsupported formats, oversized photos and mock mode report "received, not analysed".
- AC5: The guidance is labelled as not a coverage decision, approval, valuation or fraud assessment.
- AC6: Works without an API key (mock mode, visible in the header). Provider timeouts or errors and invalid output fall back to rule-based guidance with a visible reason.

**US-6 Review and edit before submitting.**
- AC1: Category, summary, documents and next steps are editable; each is tagged as an AI suggestion, policy wording or user-provided.
- AC2: My original description is stored unchanged alongside the edited summary.
- AC3: Submit is enabled only after I confirm I've reviewed and understand it's not a decision.
- AC4: If guidance fails, I can still fill in the claim manually.

**US-7 See confirmation, status and what happens next.**
- AC1: After submitting I see a claim number, the status "Submitted", a timeline of events and the expected upcoming steps (marked as typical, not guaranteed).
- AC2: The claim appears in my claims list on the dashboard.
- AC3: Next steps and documents to have ready are shown.

## Stretch: virtual assistant

**US-8 Ask questions about my policy or claim.**
- AC1: A panel answers questions using only the selected sample policy (and the open claim, if any), citing clause codes.
- AC2: If the answer isn't in the data, it says so and suggests contacting an adjuster.

## Iteration 2: insurers, conversational intake, adjuster booking

**US-9 See who insures me.** As Daniel I want to see which insurer covers each policy and how to reach them.
- AC1: Each policy shows its (fictional) insurer: name, claims phone, email, hours and address.
- AC2: Adjusters, partner garages and claim submission are scoped to that policy's insurer.

**US-10 Chat first, form second.** As Daniel I want to describe what happened in a conversation, and be asked for anything missing, before I see a summary.
- AC1: The chat greets Daniel, asks which insured item it's about, and accepts free text such as "My car was hit in a parking lot. How do I claim, and which garage nearby can repair it?".
- AC2: The reply offers **Start a claim** and **Speak with an adjuster** (and partner garages when repairs are mentioned).
- AC3: When starting a claim, the assistant reuses the incident already described and asks up to 5 follow-up questions, one at a time, each with a "why I ask" note. Every question can be skipped. Photos can be attached at any point.
- AC4: Questions are chosen only from known gaps (date, other party, injuries, police report, drivable, water source, photos…). An LLM may reorder and rephrase them but cannot invent new topics, and never asks for medical, ID or bank details.
- AC5: Only after the questions does the AI generate the summary, category, cover, missing info and next steps. Answered topics are not listed as missing again.
- AC6: The summary is editable inline in the chat; submitting creates the claim and posts its number back into the chat.

**US-11 Speak with an adjuster (slide "User Journey", steps 3–7).**
- AC1: "Speak with an adjuster" replies "Sure, let me find a suitable adjuster for you." and lists adjusters for the policy's insurer and line (motor, property or devices), with full name, office location, specialisation, languages, experience and next available slots.
- AC2: Selecting an adjuster confirms the choice and asks for a slot; slots are grouped by day.
- AC3: Selecting a slot asks for full name (prefilled) and contact number; an invalid phone shows an error. Name and phone are shared only with the adjuster.
- AC4: The user chooses a mode: phone, video (Teams/Zoom), on-site inspection or chat. Remote-only adjusters can't be booked on-site.
- AC5: On-site asks for the inspection location. Confirmation shows a reference, time, instruction note (documents and photos to keep ready), location directions, and a mock meeting link for video.
- AC6: The adjuster is "informed" and the uploaded incident photos are shared with them. If a claim is linked, a timeline event is added and the status moves to In review.
- AC7: A slot can't be double-booked (409 with fresh slots offered). The booking appears on the dashboard and the claim page.

## Iteration 3: login, adjuster directory, add a policy

**US-12 Log in.** As a policyholder I log in with a username and password so only I can see my policies and claims.
- AC1: The login page has Log in and Create account tabs. A wrong password shows "Incorrect username or password".
- AC2: Registration validates the username (3–30 characters), password (must contain at least one letter, one number and one special symbol; no other rules) and confirmation; duplicate usernames are rejected.
- AC3: Passwords are hashed (PBKDF2 with salt); sessions expire after 12h; logging out revokes the token; the session is restored on refresh within the same tab.
- AC4: The API rejects requests without a token (401) and access to other users' data (403/404).

**US-13 See adjuster details.** Typing "show me adjuster details" in ClaimAssist lists adjusters straight away. The floating assistant answers "Who is my adjuster?" from the database (booked adjuster first). The dashboard shows a **Your adjusters** directory for all my insurers.

**US-14 Add a policy.** I can add another policy (e.g. a second car) with its policy number, insurer, vehicle and optional details.
- AC1: The insurer list is filtered to those offering that policy type; the policy number must be 6–20 letters, numbers or dashes and unique.
- AC2: The new policy appears immediately with its insurer, cover, deductibles and exclusions, and supports claims, AI guidance and adjuster booking.
