export interface Factor { icon: string; text: string; favors: 'home' | 'away' | 'none' }
export interface Contribution { factor: string; delta: number }
export interface Explain { baseline_home: number; contributions: Contribution[] }
export interface Squad { home: number; away: number; home_big5: number; away_big5: number }

export interface Prediction {
  number: number; date: string; round: string; venue: string | null; city: string | null
  team1: string; team2: string; iso1: string; iso2: string
  probs: [number, number, number]
  pred_score: [number, number]; pred_outcome: number
  exp_goals: [number, number]; elo: [number, number]; form: [number, number]
  explain: Explain; squad: Squad | null; factors: Factor[]
  played: boolean; apparent_temp: number | null
  market_probs?: [number, number, number]; model_probs?: [number, number, number]
  actual_score?: [number, number]; actual_outcome?: number
  correct?: boolean; exact_hit?: boolean; rps?: number
}

export interface Meta {
  updated_utc: string; tournament: string; matches_total: number; matches_played: number
  matches_upcoming_known: number; model: string; sims: number
  accuracy_rps: number | null; accuracy_pct: number | null; sources: string[]; note: string
}

export interface Accuracy {
  n: number; rps: number; log_loss: number; brier: number; accuracy: number; ece: number
  n_correct: number; exact_accuracy: number | null; n_exact: number; avg_goal_err: number | null
  running_rps: { date: string; rps: number }[]
  calibration: { conf: number; acc: number; n: number }[]
}

export interface TeamOdds {
  team: string; iso: string; conf: string; elo: number
  squad_strength: number | null; n_big5: number | null; avg_age: number | null
  reach_r16: number; reach_qf: number; reach_sf: number; reach_final: number; champion: number
}

export interface BracketSlot { team?: string; iso?: string; champion?: number | null; placeholder?: string }
export interface BracketMatch {
  number: number; round: string; date: string; half: 'l' | 'r' | 'c'
  feeders: number[]; venue: string | null
  team1: BracketSlot; team2: BracketSlot; score: [number, number] | null
}

export interface StandingRow {
  team: string; iso: string; P: number; W: number; D: number; L: number
  GF: number; GA: number; GD: number; Pts: number
}
export type Standings = Record<string, StandingRow[]>

export interface Player {
  name: string; pos: string; club: string | null; club_country: string | null
  league: number; age: number | null
}
export interface SquadTeam {
  team: string; iso: string; strength: number; n_big5: number; avg_age: number | null
  champion: number | null; players: Player[]
}

export interface HistoryRow { year: number; champion: string; iso: string }

export interface ModelZoo {
  n_eval: number; oracle_rps: number; avg_error_corr: number
  leaderboard: { model: string; rps: number; acc: number; ece: number; note: string }[]
}

export interface GoalBench {
  years: number; ad_lambda: number; n: number; winner: string
  rows: { model: string; rps: number; score_ll: number; exact_pct: number
    goal_mae: number; pred_draw: number; real_draw: number }[]
}

export interface OddsProof {
  n_total: number; n_test: number; from: string; to: string
  market_rps: number; model_rps: number; model_plus_odds_rps: number
  odds_gain: number; error_corr: number; ceiling: number; best_blend_w: number
  rows: { model: string; rps: number; acc: number }[]
}

export interface Benchmark {
  test_window_years: number; n_matches: number; date_from: string; date_to: string
  models: Record<string, { rps: number; log_loss: number; brier: number; accuracy: number; ece: number; n: number }>
  best_model: string
  ablation: { full: number; groups: Record<string, { rps_without: number; delta: number }> }
}
