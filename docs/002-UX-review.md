# UX/UI Review: AI Document Workbench

## Objective
* Evaluate current MVP UI against PRD requirements.

## Requirement Traceability Gaps
* **Margin Comments:** PRD requires inline text annotation. UI uses a static "ASK AI" sidebar box.
* **Suggested State:** PRD requires MS Word-style inline track changes. UI uses an empty "AI SUGGESTIONS" sidebar box.
* **Meta-Chat Pane:** PRD requires a dedicated chat for meta-editing. UI lacks this distinct element.

## UI/UX Friction Points
* **Cognitive Load:** The "Add Note" form permanently occupies significant vertical space in the right sidebar.
* **Competing Actions:** The bright red 'x' delete button on sources is visually dominant over primary generative actions.
* **Workflow Disruption:** Forcing users to select text in the main pane and interact with the "ASK AI" box in the right sidebar breaks the continuous reading flow.

## Recommended Actions

* **Action 1: Global Command Modal**
  * Replace the static "ASK AI" sidebar form with an on-demand modal pop-up.
  * Trigger via keyboard shortcut or floating action button.
  * Use for global document commands independent of specific text selection.

* **Action 2: Contextual AI Triggers**
  * Implement a floating menu appearing near highlighted text.
  * Include an "Add AI Instruction" button to capture inline margin comments.

* **Action 3: Inline Track Changes**
  * Remove the "AI SUGGESTIONS" sidebar box.
  * Inject AI-generated text directly into the document editor.
  * Style suggestions distinctly with inline accept/reject controls.

* **Action 4: Collapsed Source Entry**
  * Hide the permanent Note, URL, and PDF input fields.
  * Use a single "Add Source" button to trigger an expanding menu.

* **Action 5: De-emphasized Delete**
  * Remove the persistent red 'x' buttons from the source list.
  * Implement a subtle gray trash icon visible only on mouse hover.

* **Action 6: Global Meta-Chat Panel**
  * Add a persistent, collapsible pane dedicated strictly to conversational brainstorming.