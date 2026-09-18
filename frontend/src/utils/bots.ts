// Bot opponents, easiest to hardest. The hints are the rough 501
// three-dart averages the backend's accuracy tables were tuned to.

import type { BotDifficulty } from '../api/types'

export const BOT_CHOICES: { value: BotDifficulty; label: string; hint: string }[] = [
  { value: 'noob', label: 'Noob', hint: '~25 avg' },
  { value: 'easy', label: 'Easy', hint: '~40 avg' },
  { value: 'medium', label: 'Medium', hint: '~60 avg' },
  { value: 'hard', label: 'Hard', hint: '~80 avg' },
  { value: 'pro', label: 'Pro', hint: '~100 avg' },
]
