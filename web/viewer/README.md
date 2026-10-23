# Build instructions

Model cards in Gallery, My Models and chat conversations open
`/viewer/instructions.html?model=<encoded LDraw URL>&parts=<optional count>`.
The shared viewer modal also offers this mode; the standalone page supports
`&step=N` to open a particular step.

The page uses [buildinginstructions.js](https://github.com/LasseD/buildinginstructions.js)
(`LDR.StepHandler` and `LDR.PLIBuilder`) from the existing Docker-pinned
`ldraw-org/ldraworg-library` assets. Its Three.js, loader and instruction engine
stay at the same revision, controlled by `LDRAWORG_REF` in the Dockerfile.
No CDN or additional runtime dependency is needed. Parts and colour definitions
come from the app's bundled LDraw library.

The instruction engine follows LDraw `STEP` / `ROTSTEP` commands, expands
subassemblies and shows repeated-assembly quantities. Previous parts appear
grey and each step has an illustrated parts list. Models without authored steps
show a notice; this viewer does not infer a physically valid assembly sequence.
It always loads the LDraw source, even if the model also has a GLB preview.

Controls: Previous / Next, left / right arrows, Home / End, and the step number
field. Drag to orbit, Shift+drag to pan, scroll to zoom, or Reset view to fit the
current step. Step changes update the standalone URL without adding history.

Build the frontend with `npm run build` in `web/frontend`. Rebuild the Docker
image to serve the updated frontend and the new files in `web/viewer`.
For the browser integration tests, run in `web/xr`:

```sh
VIEWER_TEST_URL=http://localhost:8765 PLAYWRIGHT_CHANNEL=chrome npm run test:instructions
```

Use the app's configured port. Omit `PLAYWRIGHT_CHANNEL` to use Playwright's
installed Chromium. Tests use fixture models and API responses; they do not
modify saved models or conversations.
