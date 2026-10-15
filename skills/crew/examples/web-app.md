# Crew config — Ledgerly

## Project
Ledgerly, a Next.js 15 + TypeScript invoicing app on Postgres (Prisma). Deployed on Vercel;
customers are small businesses in the EU, so GDPR and VAT rules apply.

## Rules
- Database changes go through a Prisma migration in the same commit; never edit an applied one.
- No new npm dependency without listing it in the plan's decisions.
- UI must meet WCAG 2.2 AA and work at 360 px width.
- Never call the live Stripe API; use the test keys in `.env.test`.
- Never run `prisma migrate deploy` or `vercel --prod`. Conventional Commits; the version is
  bumped by the release workflow, not by branches.

## Gates
- gate: `pnpm lint && pnpm typecheck`
- test: `pnpm test`
- evidence: `pnpm test:e2e` (Playwright, headless) when a page changes; screenshots land in
  `test-results/`. `pnpm build` when routing or config changes.
- evidence record: omit (CI reruns everything on the pushed commit)

## Show it
- page change: the Playwright screenshot in `test-results/` at 360 px and 1280 px.
- API change: a sample request and response saved to a file.

## Implement
- Skills to invoke: superpowers:test-driven-development
- Implementer agent: omit
- Kept-in-sync docs: `docs/api.md` for API routes, `CHANGELOG.md` (Unreleased section).

## References
- Stripe Billing, FreshBooks and Linear for UX; the EU VAT directive for tax rules.

## Tickets
- Tracker: `TODO.md`, numbered list.
- Questions: browsers and screen widths, accessibility, GDPR (what is stored, for how long),
  what changes for existing invoices.

## Workflow field
- `workflow: preview` — one "Show it" artifact to judge before building; the ticket stays open.
- `workflow: crew:quick` — read this repo, build, review.
- `workflow: crew:full` — default. The same build after web research.

## Verify before merge
- `pnpm lint && pnpm typecheck && pnpm test && pnpm test:e2e && pnpm build`
