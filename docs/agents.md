# ADK Agent Architecture: AI Document Workbench

## 1. The Root Agent (Coordinator)

* **Role**: Main dispatcher and intent router.
* **Function**: Receives user input (margin comments, edits, research requests).
* **Action**: Delegates tasks to specialist sub-agents based on intent.

## 2. Specialist Sub-Agents

* **The Drafter Agent**
  * **Role**: Prose generator.
  * **Function**: Processes margin comments and surrounding context to generate "suggested" text updates.
  * **State Access**: Reads active document context from `session.state`.
* **The Researcher Agent**
  * **Role**: Data gatherer for the "Holding Pen".
  * **Function**: Executes explicit web search requests.
  * **Tools**: Uses `Google Search` and custom web scraping tools (via Model Context Protocol) to extract source snippets.

## 3. The Dependency Workflow (The "Ripple Effect")

* **Type**: `SequentialAgent`
* **Role**: Pipeline for cascading downstream updates triggered by foundational edits.
* **Execution Sequence**:
    1. **Evaluator Agent**: Analyzes edited text against downstream context to identify logical breaks.
    2. **Drafter Agent (Re-invoked)**: Rewrites flagged downstream paragraphs to align with the new premise, outputting as suggestions.

## 4. State & Source Management

* **Session State (`session.state`)**: Acts as shared memory. Holds active text selection, surrounding chunks, and the current user command.
* **Artifacts**: Stores structured data independently of conversation history. Used to maintain the **Core Bucket** and **General Research** URL lists for deterministic access.
