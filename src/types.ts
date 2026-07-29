export type LanguageCode = 'fr' | 'en' | 'ja';

export interface SampleSentence {
  text: string;
  translation: string;
}

export type CefrLevel = 'starter' | 'A1' | 'A2' | 'B1' | 'B2' | 'C1' | 'C2' | 'ungraded';

export interface VocabEntry {
  id: string;
  language: LanguageCode;
  word: string;
  ipa: string;
  meaning: string;
  pos?: string;
  sentences: SampleSentence[];
  tags?: string[];
  /** Learner path level: starter (gentle everyday) then CEFR A1–C2 */
  level?: CefrLevel;
  /** Global teaching order (1 = easiest / earliest) */
  order?: number;
}

export interface Sm2State {
  /** SM-2 easiness factor */
  easiness: number;
  /** Successful repetitions in a row */
  repetitions: number;
  /** Interval in days until next review */
  interval: number;
  /** Next review due date (ISO date YYYY-MM-DD) */
  dueDate: string;
  /** Last review date (ISO date) */
  lastReviewDate?: string;
}

export interface ProgressEntry {
  wordId: string;
  sm2: Sm2State;
  /** Times this word was reviewed */
  reviewCount: number;
  /** Times marked forgotten */
  forgotCount: number;
  /** First seen */
  introducedAt: string;
}

export interface DailyStats {
  date: string;
  reviews: number;
  newWords: number;
  forgot: number;
  remembered: number;
}

export interface UserData {
  vocabularyBook: string[];
  progress: Record<string, ProgressEntry>;
  dailyStats: Record<string, DailyStats>;
  /** Study queue snapshot of word ids */
  lastSessionWordIds?: string[];
  lastSessionIndex?: number;
}

export type ViewMode = 'terminal' | 'ui';

export interface StudyCard {
  entry: VocabEntry;
  progress?: ProgressEntry;
  revealed: boolean;
  isDue: boolean;
  isNew: boolean;
  inBook: boolean;
}
