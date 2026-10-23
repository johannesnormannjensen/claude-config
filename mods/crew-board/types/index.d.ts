/** `isActive`: HEAD moved within the activeHours window, so the worktree takes a slot. */
export type Worktree = { slug: string; branch: string; last: string; age: string; isActive: boolean }
export type Ticket = { num: number; title: string; workflow: string; isParked: boolean }
export type Board = {
  /** The main checkout's path; empty when the session is not in a git repo. */
  root: string
  worktrees: Worktree[]
  toTest: number
  tickets: Ticket[]
  version: string
  release: string
  sinceRelease: number
  at: string
}

/** Total time and count of one kind of work. */
export type Tally = { ms: number; n: number; max: number }
/** One of the slowest single calls: the first target to speed up. */
export type Slow = { cat: string; what: string; ms: number }
/** A background task started but not yet reported done: what it counts toward and when it began. */
export type Pending = { cat: string; what: string; t0: number; isRun: boolean }
/** Where the development time goes in this repo, across sessions. */
export type Times = {
  since: string
  /** Tool time by kind of work, main loop and every agent together. */
  cats: Record<string, Tally>
  /** Wall time of whole background runs (implementers, workflows): not part of `cats`' total. */
  runs: Record<string, Tally>
  pending: Record<string, Pending>
  /** The SLOWEST_KEPT slowest single tool calls, slowest first. */
  slowest: Slow[]
}

declare module 'claude-code' {
  interface PluginState {
    'crew-board': { board: Board | null; lastPrompt: string; times: Times | null }
  }
}
