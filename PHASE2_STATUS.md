# Phase 2: source and routing separation

## Implemented

- Extracted the supplied `untangled-nexus-api-main.zip` into the sibling
  `untangled-nexus-api-main/` directory. All 20 original files were byte-verified
  after extraction. Only its README was subsequently edited; its Python code,
  dependencies, and Render configuration still match the ZIP.
- Made the Website Vite proxy target the Node backend at `http://localhost:5001`
  by default, configurable through `WEBSITE_API_PROXY_TARGET`. The browser API
  contract remains `/api` and all Website page code is unchanged.
- Preserved the desktop's existing dedicated Nexus API URL and `API_BASE_URL`
  override. No desktop runtime code changed.
- Retained every Node route, model, alternative entry script, and the existing
  desktop EXE release workflow. Node runtime changes are comments only.
- Added the architecture/deployment boundary, a secret-free Nexus API environment
  example, and Python/environment ignores. Corrected documentation that said to
  replace the Node deployment with FastAPI.

## Validation on this workspace

| Check | Result |
| --- | --- |
| FastAPI source compared with ZIP | All runtime files unchanged |
| FastAPI Python syntax | Passed |
| Node `npm test` | 11 passed |
| Default Website proxy target | Verified Node port 5001 |
| Configured Website proxy | Reached the actual local Node `/api/health` handler |
| Vite production bundling | Passed: 1,856 modules transformed |
| Standard Website `npm run build` | Blocked by existing TypeScript/configuration errors |
| Node `npm run typecheck` | Existing `server/models/Quote.ts:79` interface/schema mismatch (`assignedTo`) |
| Desktop test collection | Local Python 3.14 lacks `requests`; project targets Python 3.12 |

The proxy smoke check used an unreachable local MongoDB address, verified that
the Node health response reported `database.connected=false`, and made no
business writes. Temporary Node/Vite servers were stopped. This proves HTTP
routing, not MongoDB connectivity or customer end-to-end workflows.

Website compilation blockers include TypeScript 5.7 not supporting the existing
`erasableSyntaxOnly` option, missing Node types, page/prop type mismatches,
JSX namespace issues, and unused declarations. Bundling alone does not satisfy
the standard TypeScript build gate. Those files were not changed for separation.

## Remaining boundary

The production Website Node URL has not been supplied. No deployed routing,
server environment, account, database, or GitHub release was changed. Confirm
that URL and configure the production Website host/build as described in
`ARCHITECTURE.md` before production cutover.

Legacy Node desktop routes and desktop commerce calls remain deliberately
compatible during the staged work. Missing FastAPI endpoints, security defects,
and UI freezes from Phase 1 remain subsequent phases. This phase does not
declare Nexus ready for staff distribution.
