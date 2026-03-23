import pytest
from playwright.sync_api import Page, expect

_TEST_DOC_ID = "00000000-0000-0000-0000-000000000001"


@pytest.mark.e2e
def test_tiptap_accept_reject_flow(page: Page, live_server: str) -> None:
    # 1. Navigate to the document page via the in-process test server.
    # No session cookie needed — get_current_user is overridden in conftest.
    page.goto(f"{live_server}/documents/{_TEST_DOC_ID}")

    # 2. Wait for TipTap to mount
    editor = page.locator(".ProseMirror")
    expect(editor).to_be_visible()

    # 3. Directly assemble the TipTap activeBlock selection state and pop the modal.
    # Synthetic mouse events are unreliable in headless mode due to ProseMirror's
    # pixel-based offset calculation, so we set the hidden form fields directly.
    page.evaluate("""
        document.getElementById('modal-sel-start').value = 1;
        document.getElementById('modal-sel-end').value = 18;
        document.getElementById('modal-sel-text').value = 'Game Fundamentals';
        document.getElementById('command-modal').showModal();
    """)

    modal = page.locator("#command-modal")
    expect(modal).to_be_visible()

    # 4. Mock the AI endpoint so the test never hits the real LLM
    def mock_ai_response(route):
        mock_html = """
        <div class="suggestion-card" id="suggestion-mock">
            <div class="suggestion-content">
                <p>Mock AI Update</p>
                <div class="suggestion-actions">
                    <button class="accept-btn" hx-post="/api/suggestions/mock/accept" hx-target="#document-content">Accept</button>
                    <button class="reject-btn" hx-post="/api/suggestions/mock/reject">Reject</button>
                </div>
            </div>
        </div>
        """
        route.fulfill(
            status=200,
            content_type="text/html",
            headers={"HX-Trigger": '{"suggestion-created": {"value": "~~Old Test~~ ***New Test***"}}'},
            body=mock_html,
        )

    page.route("**/api/documents/*/comments", mock_ai_response)

    # 5. Submit the command
    cmd_input = modal.locator(".modal-body-input")
    cmd_input.fill("Expand this paragraph playfully")
    submit_btn = modal.locator(".ai-modal-send")
    submit_btn.click()

    # 6. Assert the suggestion card was injected by HTMX
    suggestion_card = page.locator("#suggestion-mock")
    expect(suggestion_card).to_be_visible(timeout=5000)

    accept_btn = page.locator(".accept-btn")
    expect(accept_btn).to_be_visible()
