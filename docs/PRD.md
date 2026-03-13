# Product Requirements Document: AI Document Workbench

## 1. Product Vision & Core Concept

The AI Document Workbench is a tool designed to shift the primary AI interaction model from "chat as the artifact" to "document as the artifact." It combines the grounded, corpus-based generation of NotebookLM with the autonomous data-gathering of Gemini Deep Research.

Users work within a text editor where they can ideate, draft, and refine documents. All AI actions—whether drafting initial outlines, expanding sections, or fact-checking—occur directly within the document or its immediate margins, maintaining continuous reading flow and strict version control.

## 2. Core User Workflow

The standard end-to-end journey within the workbench follows these steps:

1. **Ideation:** The user explains the initial idea or prompt.
2. **Ingestion:** Initial source materials are uploaded and categorized.
3. **Outlining:** The AI suggests an outline, which the user reviews and agrees upon.
4. **Drafting:** The AI generates an initial bullet-point or rough text draft.
5. **Refinement:** The user reviews the draft by editing directly or leaving margin comments for the AI to address (e.g., "flesh out this section").
6. **Cascading Updates:** As the user or AI makes foundational edits early in the text, the system ripples those logical changes downstream.

## 3. UI/UX: The "Anti-Chat" Interface

The workspace prioritizes the document over the conversational interface.

* **Margin Comments as Triggers:** Users highlight specific text and add margin comments (similar to Google Docs) to instruct the AI. The AI addresses these comments by generating or modifying the text.
* **"Suggested" State (Document Pull Requests):** AI-generated text is never immediately committed as permanent. It is dropped into the document in a "suggesting" mode (similar to MS Word Track Changes). The user must explicitly accept the change to commit it.
* **Git-Backed Markdown:** The underlying document format is Markdown, and the system uses a Git-like version control backend. This maintains a full history of all manual edits, AI suggestions, and accepted changes.
* **Dedicated Meta-Chat Pane:** A traditional chat pane exists as a secondary UI element, but it is strictly reserved for discussing the editing process of the current document (e.g., "Why did you phrase it this way?" or "Help me brainstorm a better title"), rather than generating the primary content.

## 4. Source Management & Grounding

> **Current Implementation (MVP):** The source management panel is live. Users can add URL, PDF, and note sources to a document; each appears in the sidebar list showing title, type, and date added. PDF text is extracted at upload time. Sources can be removed with a confirmation prompt. Invalid PDFs surface an inline error. The distinction between Core (trusted) and General Research (untrusted) sources, and all grounding/citation behaviour below, is planned for a future phase.

Information is strictly categorized to prevent AI hallucinations and maintain a single source of truth.

* **The Core Bucket (Gospel):** Trusted, user-uploaded source materials. The AI treats these as absolute truth.
* **Contradiction Handling:** If subsequent research uncovers information that subtly contradicts a premise in the Core Bucket, the AI will silently defer to the Core material but will insert a footnote warning into the document alerting the user to the discrepancy.
* **General Research (Untrusted):** Information gathered from autonomous web searches.
* **Visual Distinguishers:** General Research citations are visually marked in the document (e.g., with a `?` icon) to remind the user that the claim is unverified.
* **Dynamic Reference List:** The document features a live bibliography. If a user deletes a paragraph containing a specific citation, that reference is automatically removed from the master list.
* **Toggleable Citations:** Inline citations can be toggled on or off by the user to prioritize readability or academic rigor as needed.
* **Manual Sources:** Users can add a document by url, by direct pdf upload or by adding a typed note. Notes can be edited later

## 5. Web Research & Verification

Deep research and web browsing are not fully autonomous; they are user-directed and require explicit verification.

* **Explicit Triggering:** The AI only searches the live web when explicitly instructed by the user to fill a specific gap.
* **The Holding Pen:** When the AI discovers external links, it pauses before drafting. A "Holding Pen" appears in the side pane, listing the URLs alongside a one-sentence AI summary of why each link is relevant. The user must click "Import" to authorize the source into the General Research bucket.
* **The Snippet Sidebar:** To verify an untrusted claim without breaking reading flow, the user can click the `?` inline citation. A side pane immediately opens, displaying the exact paragraph/snippet from the original web source that the AI used.
* **Trust Promotion:** Once a user verifies a General Research source using the Snippet Sidebar, they can click "Promote to Core." This moves the source into the Core Bucket and globally strips the `?` warning flag from all associated citations in the document.

## 6. Cascading Auto-Updates (The Ripple Effect)

The system actively tracks the logical consistency of the document.

* **Context-Window MVP:** In the initial version, the system relies on the LLM's full context window up to a predefined token threshold. When an early section is edited (e.g., changing a core premise or date), the system re-evaluates the downstream text and proposes logical updates to later paragraphs in "suggesting" mode.
* **Future Implementation (Knowledge Graph):** Post-MVP, the system will transition to an external Knowledge Graph to track entities and claims, reducing token costs and allowing for infinitely scaling documents.

## 7. Multi-Document Ecosystem

The workbench supports complex, multi-layered projects.

* **Shared Workspace:** Multiple documents can live within the same workspace, all grounded in the exact same underlying source corpus.
* **Future Cross-Pollination (Post-MVP):** Once the foundational architecture is stable, Document B will be able to directly cite the drafted text of Document A as a source, and shared state updates will flag Document B if a new, crucial piece of research is added to the shared workspace.

## 8. Example Outputs

* Short story
* Business plan
* Technical research document
* Briefing note for an interviewer
*
