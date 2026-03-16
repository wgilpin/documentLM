/* Global helpers — must be non-module scope (called from onclick / hx-on:: attributes) */

function switchTab(name) {
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
    event.target.classList.add('active');
}

function lockEditor()   { window.tiptapEditor?.setEditable(false); }
function unlockEditor() { window.tiptapEditor?.setEditable(true); }
