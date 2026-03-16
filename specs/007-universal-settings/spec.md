# Feature Specification: Universal App Settings

**Feature Branch**: `007-universal-settings`
**Created**: 2026-03-16
**Status**: Draft
**Input**: User description: "there need to be some universal settings in the app. Add a settings icon left of the delete button, opens a settings modal where users can set: their name, l18n and language preferences, Universal instructions to the AI which will be appended to every session"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Access Settings Modal via Settings Icon (Priority: P1)

The user sees a settings (gear) icon in the document toolbar, positioned immediately to the left of the Delete button. Clicking it opens a modal with all configurable settings. The user can save or dismiss the modal without losing their current work.

**Why this priority**: The settings modal entry point must exist before any settings can be configured. It is the gateway to all other user stories and represents the minimum viable change to the UI.

**Independent Test**: Click the settings icon in the toolbar; verify the modal opens with the correct fields visible, can be cancelled without side effects, and saved changes persist.

**Acceptance Scenarios**:

1. **Given** the user is on a document page, **When** they click the settings icon, **Then** a modal opens containing the name, language, and AI instructions fields.
2. **Given** the modal is open, **When** the user clicks Cancel or closes the modal, **Then** no changes are persisted and the previous settings remain intact.
3. **Given** the modal is open and fields are filled, **When** the user clicks Save, **Then** the modal closes and settings are persisted.

---

### User Story 2 - Configure Universal AI Instructions (Priority: P1)

The user opens the settings modal and enters universal instructions that will be automatically appended to every AI session. For example, they might enter "Always respond in a formal academic tone" or "Prefer concise answers under 100 words." From that point on, every AI interaction in the app includes those instructions without the user needing to repeat them.

**Why this priority**: This is the highest-value differentiator — it allows the user to personalise AI behaviour globally without per-session setup. It directly improves the core AI writing workflow.

**Independent Test**: Open settings, enter an instruction, save, start a new AI session, and verify the AI response reflects the instruction.

**Acceptance Scenarios**:

1. **Given** no AI instructions are set, **When** the user opens the settings modal, **Then** the AI instructions textarea is empty.
2. **Given** the user has typed custom instructions and saved, **When** any AI session starts, **Then** the saved instructions are appended to every AI prompt automatically.
3. **Given** the user clears the AI instructions field and saves, **When** a new AI session starts, **Then** no extra instructions are appended.
4. **Given** the AI instructions textarea, **When** the user types more than 2,000 characters, **Then** input is blocked at the limit and a character count is shown.

---

### User Story 3 - Set Display Name (Priority: P2)

The user can enter their name in the settings modal. This name is stored as a global preference and is available to the AI as context, enabling personalised responses (e.g., "Hi Sarah, here is a draft…").

**Why this priority**: Personalisation enhances the experience but is not required for the AI instruction or language features to function independently.

**Independent Test**: Enter a name in the settings modal, save, reopen the modal, and verify the name is still populated.

**Acceptance Scenarios**:

1. **Given** no name is set, **When** the user opens settings, **Then** the name field is blank.
2. **Given** the user enters a name and saves, **When** they reopen settings, **Then** the saved name appears pre-filled.
3. **Given** a name is saved, **When** the AI generates a response, **Then** the name is available as context in the AI system prompt.

---

### User Story 4 - Set Language and Localisation Preference (Priority: P2)

The user selects their preferred language from a list of common locales (e.g., English, French, German). The AI uses this preference to respond in the chosen language by default, without the user needing to specify the language in each prompt.

**Why this priority**: Language personalisation is important for non-English users but does not block the core settings infrastructure or AI instructions feature.

**Independent Test**: Set language to a non-English locale, save, start an AI session, and verify the AI responds in the selected language.

**Acceptance Scenarios**:

1. **Given** no language is set, **When** the user opens settings, **Then** the language selector defaults to English (en).
2. **Given** the user selects a language and saves, **When** any AI session starts, **Then** the AI is instructed to respond in the selected language.
3. **Given** the user reopens settings, **Then** the previously saved language is pre-selected.

---

### Edge Cases

- What happens if the user saves settings when the server is unavailable? The user sees an error message; settings are not silently lost.
- What happens on the very first launch before any settings are configured? All fields default to sensible empty/default values and the AI functions as it did before this feature.
- What happens if the user enters an extremely long AI instruction? Input is capped at 2,000 characters with a visible counter; the Save button remains available at the limit.
- What happens if the user's chosen language is one the AI handles poorly? No special handling — the AI best-efforts a response in the requested language.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The document toolbar MUST display a settings icon immediately to the left of the Delete button on all document pages.
- **FR-002**: Clicking the settings icon MUST open a modal dialog containing: display name field, language/locale selector, and AI instructions textarea.
- **FR-003**: The settings modal MUST provide Save and Cancel/Close actions; Cancel MUST discard unsaved changes and leave persisted settings unchanged.
- **FR-004**: The system MUST persist user settings (name, language, AI instructions) server-side so they survive page reloads and device changes.
- **FR-005**: The AI instructions text MUST be automatically appended to the system prompt for every AI session in the application.
- **FR-006**: The user display name MUST be available as context in every AI session prompt.
- **FR-007**: The selected language/locale MUST be passed to the AI as an instruction to respond in that language.
- **FR-008**: The AI instructions textarea MUST enforce a maximum of 2,000 characters and MUST display a live character count to the user.
- **FR-009**: The language selector MUST offer at minimum: English (en), English UK (en-GB), French (fr), German (de), Spanish (es), Italian (it), Portuguese (pt), Dutch (nl), Japanese (ja), Chinese Simplified (zh), Arabic (ar).
- **FR-010**: Settings MUST be stored as a single shared user profile (single-user app — no multi-user isolation required).

### Key Entities

- **UserSettings**: Represents global user preferences. Attributes: display name (optional text), language/locale code (default: "en"), AI instructions (optional text up to 2,000 characters), last updated timestamp.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can open the settings modal, fill in all three fields, and save in under 60 seconds.
- **SC-002**: After saving settings, every subsequent AI session reflects the configured AI instructions without any additional user action.
- **SC-003**: Settings survive a full page reload — no data is lost after saving.
- **SC-004**: The settings icon is visible and reachable in the document toolbar without scrolling on a standard desktop viewport.
- **SC-005**: The selected language preference is correctly communicated to the AI in 100% of new sessions started after saving.

## Assumptions

- This is a single-user application; there is no need for per-user account isolation or authentication.
- Settings are stored server-side (persisted to the database), not only in browser local storage.
- The AI instructions are appended as a suffix to the existing system prompt rather than replacing it.
- The name and language are also injected into the system prompt (not displayed in the UI elsewhere in this iteration).
- Settings only apply to AI sessions started after saving — no retroactive effect on existing sessions.
- A single language code is sufficient; no separate date format, number format, or timezone preferences are needed in this iteration.
- The settings icon uses a standard gear/cog symbol available in the existing icon set or as a Unicode character.
