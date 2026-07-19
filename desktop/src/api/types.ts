// TS mirrors of the pydantic view-models in mtga_bridge/viewmodels.py
// (camelCase via pydantic alias_generator).

export interface CardStats {
  gihwr: number | null;
  ohwr: number | null;
  gpwr: number | null;
  alsa: number | null;
  ata: number | null;
  iwd: number | null;
  gih: number | null;
  ngp: number | null;
}

export interface Recommendation {
  cardName: string;
  baseWinRate: number;
  contextualScore: number;
  zScore: number;
  castProbability: number;
  wheelChance: number;
  functionalCmc: number;
  reasoning: string[];
  isElite: boolean;
  archetypeFit: string;
  tags: string[];
}

export interface Card {
  name: string;
  manaCost: string;
  cmc: number;
  colors: string[];
  types: string[];
  rarity: string;
  image: string[];
  count: number;
  stats: CardStats;
  recommendation: Recommendation | null;
  isPicked: boolean;
  returnableAt: number[];
  tier: string | null;
}

export interface PoolSummary {
  cmcDistribution: number[];
  cmcAverage: number;
  colorPips: Record<string, number>;
  creatureCount: number;
  noncreatureCount: number;
  cardCount: number;
}

export interface DraftState {
  booted: boolean;
  eventSet: string;
  eventType: string;
  eventString: string;
  draftId: string;
  startTime: string | null;
  pack: number;
  pick: number;
  activeFilter: string;
  filterLabel: string;
  packCards: Card[];
  missingCards: Card[];
  takenCount: number;
  signals: { scores: Record<string, number> };
  poolSummary: PoolSummary | null;
  datasetName: string | null;
  logSource: "live" | "history";
  logName: string;
}

export interface TakenCards {
  cards: Card[];
  poolSummary: PoolSummary;
  activeFilter: string;
}

export interface BootStatus {
  booted: boolean;
  lastMessage: string;
  error: string | null;
}

export interface Settings {
  deckFilter: string;
  filterFormat: string;
  resultFormat: string;
  uiSize: string;
  cardColorsEnabled: boolean;
  draftLogEnabled: boolean;
  updateNotificationsEnabled: boolean;
  missingNotificationsEnabled: boolean;
  autoSyncDatasets: boolean;
  arenaLogLocation: string;
  databaseLocation: string;
  columnConfigs: Record<string, string[]>;
}

export type SettingsPatch = Partial<Settings>;

export interface FilterOptions {
  options: string[];
  active: string;
  autoDetected: string;
}

export interface DatasetInfo {
  label: string;
  path: string;
  fileName: string;
  sizeBytes: number;
  modified: number;
  isActive: boolean;
}

export interface DatasetList {
  datasets: DatasetInfo[];
  activeDataset: string | null;
}

export interface AvailableSet {
  code: string;
  name: string;
}

export interface AvailableSets {
  sets: AvailableSet[];
}

export interface DownloadProgress {
  kind: "status" | "percent";
  text: string;
  value: number;
}

export interface DownloadResult {
  ok: boolean;
  message: string;
  dataset: DatasetInfo | null;
}

export interface DraftLog {
  path: string;
  fileName: string;
  modified: number;
}

export interface DraftLogList {
  logs: DraftLog[];
  current: string;
}

export interface Ack {
  ok: boolean;
  message: string;
}
