# Local Developer Notes

## JS Bundle

`static/editor.js` is bundled into `static/editor.bundle.js` via esbuild.

**Always tell the user to run `npm run build:dev` after any change to `static/editor.js`.**

CSS (`static/style.css`) is served directly — no rebuild needed for CSS changes.
