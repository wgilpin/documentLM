/* Global helpers — must be non-module scope (called from onclick / hx-on:: attributes) */

(function () {
    const STORAGE_KEY = 'sidebar-width';
    const MIN_SIDEBAR = 200;
    const MAX_SIDEBAR = 600;

    function initResizeHandle() {
        const handle = document.getElementById('resize-handle');
        const layout = handle && handle.closest('.editor-layout');
        if (!handle || !layout) return;

        function setWidth(w) {
            layout.style.gridTemplateColumns = `256px 1fr 5px ${w}px`;
        }

        const saved = parseInt(localStorage.getItem(STORAGE_KEY), 10);
        if (saved && saved >= MIN_SIDEBAR && saved <= MAX_SIDEBAR) {
            setWidth(saved);
        }

        let startX, startWidth;

        handle.addEventListener('mousedown', function (e) {
            e.preventDefault();
            startX = e.clientX;
            const cols = getComputedStyle(layout).gridTemplateColumns.split(' ');
            startWidth = parseInt(cols[cols.length - 1], 10);
            handle.classList.add('resize-handle--dragging');

            function onMove(e) {
                const delta = startX - e.clientX;
                const newWidth = Math.min(MAX_SIDEBAR, Math.max(MIN_SIDEBAR, startWidth + delta));
                setWidth(newWidth);
            }

            function onUp() {
                handle.classList.remove('resize-handle--dragging');
                const final = parseInt(getComputedStyle(layout).gridTemplateColumns.split(' ').pop(), 10);
                localStorage.setItem(STORAGE_KEY, final);
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
            }

            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initResizeHandle);
    } else {
        initResizeHandle();
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
