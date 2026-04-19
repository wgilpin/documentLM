/* Global helpers — must be non-module scope (called from onclick / hx-on:: attributes) */

(function () {
    const STORAGE_KEY = 'sources-panel-width';
    const MIN_WIDTH = 200;
    const MAX_WIDTH = 600;
    const CSS_VAR = '--sources-panel-width';

    function setWidth(w) {
        document.documentElement.style.setProperty(CSS_VAR, w + 'px');
    }

    function initSourcesResizeHandle() {
        const handle = document.getElementById('sources-resize-handle');
        if (!handle) return;

        const saved = parseInt(localStorage.getItem(STORAGE_KEY), 10);
        if (saved && saved >= MIN_WIDTH && saved <= MAX_WIDTH) {
            setWidth(saved);
        }

        handle.addEventListener('mousedown', function (e) {
            e.preventDefault();
            handle.classList.add('resize-handle--dragging');
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';

            function onMove(ev) {
                const w = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, ev.clientX));
                setWidth(w);
            }

            function onUp() {
                handle.classList.remove('resize-handle--dragging');
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
                const current = parseInt(
                    getComputedStyle(document.documentElement).getPropertyValue(CSS_VAR),
                    10
                );
                if (current) localStorage.setItem(STORAGE_KEY, current);
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
            }

            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initSourcesResizeHandle);
    } else {
        initSourcesResizeHandle();
    }
}());

function switchTab(name) {
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
    event.target.classList.add('active');
}

function switchMiddleTab(name) {
    document.querySelectorAll('.middle-panel-body').forEach(function(p) { p.style.display = 'none'; });
    document.querySelectorAll('.middle-tab-btn').forEach(function(b) { b.classList.remove('middle-tab-btn--active'); });
    var panel = document.getElementById('middle-panel-' + name);
    if (panel) panel.style.display = '';
    var btn = document.getElementById('mid-tab-' + name);
    if (btn) btn.classList.add('middle-tab-btn--active');
}

function switchRightTab(name) {
    document.querySelectorAll('.right-panel-body').forEach(function(p) { p.style.display = 'none'; });
    document.querySelectorAll('.right-tab-btn').forEach(function(b) { b.classList.remove('right-tab-btn--active'); });
    var panel = document.getElementById('right-panel-' + name);
    if (panel) panel.style.display = '';
    var btn = document.getElementById('right-tab-' + name);
    if (btn) btn.classList.add('right-tab-btn--active');
}

function showSourceNotice() {
    var el = document.getElementById('source-processing-notice');
    if (el) {
        el.hidden = false;
        setTimeout(function () { el.hidden = true; }, 8000);
    }
}

function clearSourceViewerIfMatch(sourceId) {
    var el = document.getElementById('source-view-content');
    if (el && el.dataset.sourceId === sourceId) {
        var container = document.getElementById('source-view-container');
        if (container) {
            container.innerHTML = '<p class="side-panel-placeholder">Select a source to view its content here.</p>';
        }
    }
}

document.addEventListener('click', function (e) {
    if (e.target.tagName === 'IMG' && e.target.closest('.source-view-body')) {
        e.target.classList.toggle('source-img--expanded');
    }
});

/* Close any open source-menu <details> when clicking outside it. */
document.addEventListener('click', function (e) {
    document.querySelectorAll('details.source-menu[open]').forEach(function (d) {
        if (!d.contains(e.target)) d.open = false;
    });
});

function lockEditor()   { window.tiptapEditor?.setEditable(false); }
function unlockEditor() { window.tiptapEditor?.setEditable(true); }

(function () {
    function initChatEnterSubmit() {
        const textarea = document.querySelector('.chat-input-textarea');
        if (!textarea) return;
        textarea.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                textarea.closest('form').requestSubmit();
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initChatEnterSubmit);
    } else {
        initChatEnterSubmit();
    }
}());
