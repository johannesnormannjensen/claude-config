# Crew config — Ledgerly

## Project
Ledgerly, a Next.js 15 + TypeScript invoicing app on Postgres (Prisma). Deployed on Vercel;
customers are small businesses in the EU, so GDPR and VAT rules apply.

## Rules
- Database changes go through a Prisma migration in the same commit; never edit an applied one.
- No new npm dependency without listing it in the plan's decisions.
- UI must meet WCAG 2.2 AA and work at 360 px width.
- Never call the live Stripe API; use the test keys in `.env.test`.

## Gates
- gate: `pnpm lint && pnpm typecheck`
- test: `pnpm test`
- evidence: `pnpm test:e2e` (Playwright, headless) when a page changes; screenshots land in
  `test-results/`. `pnpm build` when routing or config changes.

## Implement
- Skills to invoke: superpowers:test-driven-development
- Kept-in-sync docs: `docs/api.md` for API routes, `CHANGELOG.md` (Unreleased section).

## References
- Stripe Billing, FreshBooks and Linear for UX; the EU VAT directive for tax rules.

## Verify before merge
- `pnpm lint && pnpm typecheck && pnpm test && pnpm test:e2e && pnpm build`
