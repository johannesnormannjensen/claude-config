import { atom, read, update } from 'claude-code'
import type { EngineInterface as Engine, Register } from 'claude-code'

import type { Board, Tally, Ticket, Times, Worktree } from '../types'

const PANE = 'crew-board'
const CREW_SCRIPT = /(^|\/)(crew|preview|crew-resume)(\.js)?$/
// Background-task and harness notices arrive as prompts too; they are never the owner talking.
const NOTICE = /^\s*<(task-notification|system-reminder)>/
// A gap between two tool calls of one loop longer than this is idle time, not the model working.
const MAX_THINK_MS = 10 * 60_000
const OWNER_WAIT = 'waiting on the owner'
const MAX_OWNER_MS = 2 * 3600_000

const board = atom({ plugin: 'crew-board', key: 'board' } as const, null)
const lastPrompt = atom({ plugin: 'crew-board', key: 'lastPrompt' } as const, '')
const timesAtom = atom({ plugin: 'crew-board', key: 'times' } as const, null)

// Shell commands by kind of work; the first match wins, so a `npm test && git commit` is tests.
const BUILT_IN_SHELL: [RegExp, string][] = [
  [/\b(pytest|jest|vitest|mocha|rspec|ctest|phpunit)\b|\b(cargo|go|npm|pnpm|yarn|bun|dotnet|mix|mvn|gradlew?|make) (run )?(test|check)\b/, 'tests'],
  [/\bgit commit\b|\b(cargo|go|dotnet|mvn|gradlew?) (build|clippy|fmt|vet|run)\b|\b(npm|pnpm|yarn|bun) (run )?(build|lint|typecheck|format)\b|\b(tsc|eslint|prettier|ruff|black|mypy|make)\b/, 'build + lint'],
  [/\bgit (merge|push|pull|fetch|rebase|worktree)\b/, 'landing + git'],
]
const TOOLS: Record<string, string> = {
  Read: 'reading code', Grep: 'reading code', Glob: 'reading code', LSP: 'reading code',
  Edit: 'editing', Write: 'editing', NotebookEdit: 'editing',
  WebSearch: 'web research', WebFetch: 'web research',
}

// Session memory of the loops: when each last finished a tool call (main loop is 'main').
const lastEnd = new Map<string, number>()
let turnEndedAt = 0
const SLOWEST_KEPT = 5
const empty = (since: string): Times => ({ since, cats: {}, runs: {}, pending: {}, slowest: [] })
let times: Times = empty('')
// The main checkout and its git dir, found once per load from the session's working directory.
let root = ''
let gitDir = ''

type Run = (argv: readonly string[]) => Promise<string>

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

function parseShellKinds(spec: string): [RegExp, string][] {
  return spec.split(';').map(p => p.trim()).filter(Boolean).map(p => {
    const at = p.indexOf('=')
    return [new RegExp(p.slice(at + 1)), p.slice(0, at).trim()] as [RegExp, string]
  })
}

// `what` (a tool call's command or path) also enters the slowest-calls list.
function add(into: Record<string, Tally>, key: string, ms: number, what?: string) {
  const t = (into[key] ??= { ms: 0, n: 0, max: 0 })
  t.ms += ms
  t.n += 1
  t.max = Math.max(t.max ?? 0, ms)
  if (what === undefined) return
  times.slowest = [...times.slowest, { cat: key, what: what.slice(0, 70), ms }]
    .sort((a, b) => b.ms - a.ms)
    .slice(0, SLOWEST_KEPT)
}

// Times are kept per repo: the mod's store is shared by every project.
const timesKey = () => `times:${root}`

async function flush($: Engine) {
  if (!root) return
  await $.store.set(timesKey(), times)
  await update($, timesAtom, () => structuredClone(times))
  // A mirror Claude can read; inside the git dir, so it never shows as a change.
  await $.fs.write(`${gitDir}/crew-board-times.json`, JSON.stringify(times, null, 1)).catch(() => undefined)
}

// A background task's done notice: book its time where its start said.
async function onNotice($: Engine, text: string) {
  for (const m of text.matchAll(/<task-id>(\w+)<\/task-id>[\s\S]*?<status>(\w+)<\/status>/g)) {
    const p = times.pending[m[1]]
    if (!p || m[2] === 'running') continue
    const ms = Number(/<duration_ms>(\d+)</.exec(text)?.[1] ?? (await $.clock.now()) - p.t0)
    add(p.isRun ? times.runs : times.cats, p.cat, ms, p.isRun ? undefined : p.what)
    delete times.pending[m[1]]
  }
}

async function worktrees(git: Run): Promise<Worktree[]> {
  const out: Worktree[] = []
  for (const block of (await git(['worktree', 'list', '--porcelain'])).split('\n\n')) {
    const path = /^worktree (.+)$/m.exec(block)?.[1] ?? ''
    const branch = /^branch refs\/heads\/(.+)$/m.exec(block)?.[1] ?? ''
    if (!path.includes('/.claude/worktrees/') || !branch) continue
    const [age = '', last = ''] = (await git(['log', '-1', '--format=%cr|%s', branch])).trim().split('|')
    out.push({ slug: path.split('/').pop() ?? path, branch, last, age })
  }
  return out
}

function parseTracker(text: string, heading: string): { toTest: number; tickets: Ticket[] } {
  const body = new RegExp(`^#+ ${escape(heading)}[^\\n]*\\n([\\s\\S]*?)(?=^#+ |(?![\\s\\S]))`, 'm').exec(text)?.[1] ?? ''
  const toTest = body.split('\n').filter(l => l.startsWith('- ')).length
  const tickets: Ticket[] = []
  for (const m of text.matchAll(/^(\d+)\. \*\*(.+?)\*\*(.{0,300})/gm)) {
    const rest = m[3]
    if (rest.includes('— merged')) continue
    tickets.push({
      num: Number(m[1]),
      title: m[2],
      workflow: /workflow: ?([a-z:]+)/.exec(rest)?.[1] ?? '?',
      isParked: /PARKED/.test(rest),
    })
  }
  return { toTest, tickets }
}

async function version($: Engine): Promise<string> {
  const cargo = await $.fs.read(`${root}/Cargo.toml`).catch(() => '')
  const pkg = await $.fs.read(`${root}/package.json`).catch(() => '')
  return /^version = "(.+)"/m.exec(cargo)?.[1] ?? /"version":\s*"([^"]+)"/.exec(pkg)?.[1] ?? '?'
}

// The plugin's userConfig values (plugin.json), set on every load.
let tracker = ''
let toTestHeading = ''
let maxSlots = 0
let toTestLimit = 0
let start = /$^/
let guardAgent = ''
let releaseGrep = ''
let shell: [RegExp, string][] = BUILT_IN_SHELL

function categorize(tool: string, input: Record<string, unknown>): string | undefined {
  if (tool === 'Bash') {
    const cmd = String(input.command ?? '')
    return shell.find(([re]) => re.test(cmd))?.[1] ?? 'other shell'
  }
  return TOOLS[tool]
}

async function findRoot($: Engine) {
  const r = await $.process.run(['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'])
  gitDir = r.exitCode === 0 ? r.stdout.trim() : ''
  root = gitDir.replace(/\/\.git$/, '')
}

async function build($: Engine): Promise<Board> {
  const at = new Date(await $.clock.now()).toTimeString().slice(0, 5)
  if (!root) return { root, worktrees: [], toTest: 0, tickets: [], version: '?', release: 'none', sinceRelease: 0, at }
  const git: Run = async argv => (await $.process.run(['git', '-C', root, ...argv])).stdout
  const status = parseTracker(await $.fs.read(`${root}/${tracker}`).catch(() => ''), toTestHeading)
  const [hash = '', subject = '', age = ''] = (
    await git(['log', '-1', '-E', `--grep=${releaseGrep}`, '--format=%h|%s|%cr'])
  ).trim().split('|')
  const sinceRelease = hash ? Number((await git(['rev-list', '--count', `${hash}..HEAD`])).trim()) : 0
  return {
    root,
    worktrees: await worktrees(git),
    toTest: status.toTest,
    tickets: status.tickets,
    version: await version($),
    release: subject ? `${subject.replace(/^[a-z]+\(release\):\s*/, '')} (${age})` : 'none',
    sinceRelease,
    at,
  }
}

async function refresh($: Engine): Promise<Board> {
  const b = await build($)
  await update($, board, () => b)
  await flush($)
  return b
}

// Guardrails: a crew launch only in the owner's start turn, and never past maxSlots worktrees.
async function guard($: Engine, what: string): Promise<string | undefined> {
  const said = await read($, lastPrompt)
  if (!start.test(said)) {
    return `crew-board: ${what} needs the owner's start message ("start T12"); the latest is: "${said.slice(0, 80)}". Say what is next and wait.`
  }
  const b = await refresh($)
  if (b.worktrees.length > maxSlots) {
    return `crew-board: ${b.worktrees.length} worktrees (${b.worktrees.map(w => w.slug).join(', ')}) is past the ${maxSlots}-slot limit.`
  }
  return undefined
}

export const register: Register = (on, options) => {
  tracker = String(options.tracker)
  toTestHeading = String(options.toTestHeading)
  maxSlots = Number(options.maxSlots)
  toTestLimit = Number(options.toTestLimit)
  // The owner's start words: a launch only in the turn whose message is the start.
  start = new RegExp(`\\b(${String(options.startWords)})\\b`, 'i')
  guardAgent = String(options.guardAgent)
  releaseGrep = String(options.releaseGrep)
  shell = [...parseShellKinds(String(options.shellKinds)), ...BUILT_IN_SHELL]

  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'crew-board', description: 'Open the crew board' })
    await findRoot($)
    const kept = root ? ((await $.store.get(timesKey())) as Times | undefined) : undefined
    times = { ...empty(new Date(await $.clock.now()).toISOString().slice(0, 10)), ...kept }
    void refresh($)
    $.clock.every(60_000, () => void refresh($))
    return next(e)
  })

  on('command.run', { command: 'crew-board' }, async $ => {
    await refresh($)
    await $.ui.open({ id: PANE, title: 'Crew board' })
    return { text: 'Crew board opened.' }
  })

  on('prompt.submit', async ($, e, next) => {
    if (NOTICE.test(e.text)) {
      await onNotice($, e.text)
    } else if (!e.isMeta && !e.command) {
      await update($, lastPrompt, () => e.text)
      const now = await $.clock.now()
      if (turnEndedAt) add(times.cats, OWNER_WAIT, Math.min(now - turnEndedAt, MAX_OWNER_MS))
      turnEndedAt = 0
    }
    lastEnd.delete('main')
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    turnEndedAt = await $.clock.now()
    lastEnd.delete('main')
    void refresh($)
    return next(e)
  })

  // Times every tool call of the main loop and every agent: the call itself by kind of work, the
  // gap before it as the model thinking. Background starts are booked when their notice lands.
  on('tool.call', async ($, e, next) => {
    const loop = e.agentId ?? 'main'
    const t0 = await $.clock.now()
    const gap = t0 - (lastEnd.get(loop) ?? t0)
    if (gap > 0 && gap < MAX_THINK_MS) add(times.cats, loop === 'main' ? 'thinking (orchestrator)' : 'thinking (agents)', gap)
    const input = e as unknown as Record<string, unknown>
    const r = await next(e)
    const t1 = await $.clock.now()
    lastEnd.set(loop, t1)
    const id = /with ID: (\w+)|agentId: (\w+)|Task ID: (\w+)/.exec(String(r.text ?? ''))
    const taskId = id?.[1] ?? id?.[2] ?? id?.[3]
    if (e.tool === 'Agent' || e.tool === 'Workflow') {
      if (taskId) {
        const kind = e.tool === 'Agent'
          ? String(input.subagent_type ?? 'agent')
          : String(input.scriptPath ?? input.name ?? 'workflow').split('/').pop() ?? 'workflow'
        times.pending[taskId] = { cat: kind, what: kind, t0, isRun: true }
      }
      return r
    }
    const cat = categorize(e.tool, input)
    if (!cat) return r
    const what = String(input.command ?? input.file_path ?? input.pattern ?? e.tool)
    if (input.run_in_background && taskId) times.pending[taskId] = { cat, what, t0, isRun: false }
    else add(times.cats, cat, t1 - t0, what)
    return r
  })

  on('tool.call', { tool: 'Workflow' }, async ($, e, next) => {
    const script = e.scriptPath ?? e.name ?? ''
    if (e.resumeFromRunId || !CREW_SCRIPT.test(script)) return next(e)
    const deny = await guard($, `launching ${script.split('/').pop()}`)
    return deny ? { deny } : next(e)
  }).catch(($, e, next) => (next.called ? next(e) : next(e)))

  on('tool.call', { tool: 'Agent' }, async ($, e, next) => {
    if (!guardAgent || e.subagent_type !== guardAgent) return next(e)
    const deny = await guard($, `a ${guardAgent} launch`)
    return deny ? { deny } : next(e)
  }).catch(($, e, next) => (next.called ? next(e) : next(e)))

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const b = await read($, board)
    const t = await read($, timesAtom)
    if (b === null) return <Text dimColor>Loading the crew board…</Text>
    if (!b.root) return <Text dimColor>Not in a git repo.</Text>
    const slots = Math.min(b.worktrees.length, maxSlots)
    const isOver = b.toTest > toTestLimit
    const cats = Object.entries(t?.cats ?? {}).sort((x, y) => y[1].ms - x[1].ms)
    const work = cats.filter(([k]) => k !== OWNER_WAIT)
    const total = work.reduce((s, [, v]) => s + v.ms, 0)
    const top = work[0]?.[1].ms ?? 1
    const runs = Object.entries(t?.runs ?? {}).sort((x, y) => y[1].ms - x[1].ms)
    const waited = t?.cats[OWNER_WAIT]
    return (
      <Box flexDirection="column">
        <Text bold>
          Slots {b.worktrees.length}/{maxSlots}
          {b.worktrees.length > maxSlots ? '  (over!)' : slots === maxSlots ? '  (full)' : ''}
        </Text>
        {b.worktrees.length === 0 && <Text dimColor>  nothing running</Text>}
        {b.worktrees.map(w => (
          <Text>
            {'  '}
            {w.slug} <Text dimColor>· {w.age} · {w.last.slice(0, 50)}</Text>
          </Text>
        ))}
        <Text> </Text>
        <Text bold color={isOver ? 'yellow' : undefined}>
          {toTestHeading} {b.toTest}/{toTestLimit}
          {isOver ? '  (owner names every start)' : ''}
        </Text>
        <Text> </Text>
        <Text bold>
          v{b.version} · last release {b.release}
          {b.sinceRelease > 0 ? ` · ${b.sinceRelease} commits since` : ''}
        </Text>
        <Text> </Text>
        <Text bold>Where the time goes <Text dimColor>since {t?.since ?? '?'} · {duration(total)} of work</Text></Text>
        {work.length === 0 && <Text dimColor>  nothing timed yet</Text>}
        {work.map(([k, v]) => (
          <Text>
            {'  '}
            {k.padEnd(24)} <Text color="cyan">{'█'.repeat(Math.max(1, Math.round((v.ms / top) * 16))).padEnd(16)}</Text>
            {' '}{duration(v.ms).padStart(5)} {String(Math.round((v.ms / Math.max(total, 1)) * 100)).padStart(3)}%
            <Text dimColor> ×{v.n} · avg {secs(v.ms / v.n)} · max {secs(v.max ?? 0)}</Text>
          </Text>
        ))}
        {runs.length > 0 && <Text dimColor>  whole runs (wall clock):</Text>}
        {runs.map(([k, v]) => (
          <Text dimColor>
            {'    '}{k.padEnd(22)} ×{v.n} · avg {duration(v.ms / v.n)} · {duration(v.ms)} total
          </Text>
        ))}
        {(t?.slowest.length ?? 0) > 0 && <Text dimColor>  slowest single calls:</Text>}
        {t?.slowest.map(s => (
          <Text dimColor>
            {'    '}{secs(s.ms).padStart(5)} {s.cat.padEnd(20)} {s.what}
          </Text>
        ))}
        {waited && <Text dimColor>  {OWNER_WAIT}: {duration(waited.ms)} over {waited.n} turns</Text>}
        <Text> </Text>
        <Text bold>Open tickets</Text>
        {b.tickets.length === 0 && <Text dimColor>  none in {tracker}</Text>}
        {b.tickets.map(t => (
          <Text dimColor={t.isParked}>
            {'  '}T{t.num} {t.title.slice(0, 48)} <Text dimColor>· {t.isParked ? 'parked' : t.workflow}</Text>
          </Text>
        ))}
        <Text> </Text>
        <Text dimColor>updated {b.at}</Text>
      </Box>
    )
  })
}

function secs(ms: number): string {
  return ms >= 90_000 ? duration(ms) : `${(ms / 1000).toFixed(ms < 10_000 ? 1 : 0)}s`
}

function duration(ms: number): string {
  const m = Math.round(ms / 60_000)
  return m >= 60 ? `${Math.floor(m / 60)}h${String(m % 60).padStart(2, '0')}` : `${m}m`
}
