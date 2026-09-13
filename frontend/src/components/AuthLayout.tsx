// Split layout for login/register: brand panel with the board on the
// left (desktop only), the form on the right.

import type { ReactNode } from 'react'

import { Dartboard } from './Dartboard'
import { BoardGlyph } from './Logo'

export function AuthLayout({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle: string
  children: ReactNode
}) {
  return (
    <div className="flex min-h-screen">
      <aside className="relative hidden w-1/2 flex-col justify-between overflow-hidden bg-ink-900 p-10 lg:flex">
        <div className="flex items-center gap-2.5">
          <BoardGlyph />
          <span className="font-display text-2xl font-bold tracking-wide">
            Dart<span className="text-felt-400">Metrics</span>
          </span>
        </div>
        <div className="relative z-10">
          <p className="font-display text-5xl font-extrabold leading-tight">
            Every dart,
            <br />
            <span className="text-felt-400">counted.</span>
          </p>
          <p className="mt-4 max-w-xs text-ink-300">
            501, Cricket and Halve It scored dart by dart, with the averages,
            checkouts and 180s that fall out of the raw throws.
          </p>
        </div>
        <p className="relative z-10 text-xs text-ink-500">Play a friend, a guest, or one of five bots.</p>
        <Dartboard className="absolute -bottom-28 -right-28 h-[28rem] w-[28rem] opacity-80" />
      </aside>

      <main className="flex w-full items-center justify-center px-4 py-12 lg:w-1/2">
        <div className="w-full max-w-sm animate-rise">
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <BoardGlyph />
            <span className="font-display text-2xl font-bold tracking-wide">
              Dart<span className="text-felt-400">Metrics</span>
            </span>
          </div>
          <h1 className="font-display text-4xl font-bold">{title}</h1>
          <p className="mb-8 mt-1 text-ink-400">{subtitle}</p>
          {children}
        </div>
      </main>
    </div>
  )
}
