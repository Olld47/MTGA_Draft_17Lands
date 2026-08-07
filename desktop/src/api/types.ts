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
  typeCounts: Record<string, number>;
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
  desktopTheme: string;
  cardColorsEnabled: boolean;
  draftLogEnabled: boolean;
  updateNotificationsEnabled: boolean;
  missingNotificationsEnabled: boolean;
  autoSyncDatasets: boolean;
  arenaLogLocation: string;
  databaseLocation: string;
  columnConfigs: Record<string, string[]>;
  deckMidDistribution: number[];
  overlayGeometry: string;
}

export type SettingsPatch = Partial<Settings>;

export interface FilterOption {
  key: string;
  label: string;
  winRate: number | null;
}

export interface FilterOptions {
  options: FilterOption[];
  active: string;
  autoDetected: string;
  autoDetectedLabel: string;
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

export interface ColorMetric {
  mean: number;
  std: number;
}

/** Mean/std per (win-rate field, color) for the active dataset — inputs the
 *  frontend converts raw win rates into Grade/Rating display values. */
export interface SetMetrics {
  metrics: Record<string, Record<string, ColorMetric>>;
  hasData: boolean;
}

export interface DatasetSwitcherGroup {
  name: string;
  path: string;
}

export interface DatasetSwitcherEvent {
  name: string;
  groups: DatasetSwitcherGroup[];
}

/** Event-type → user-group dataset options for the currently detected set
 *  (masthead switcher; port of top_bar.update_data_sources). */
export interface DatasetSwitcher {
  setCode: string;
  detectedEvent: string | null;
  activeEvent: string | null;
  activeGroup: string | null;
  events: DatasetSwitcherEvent[];
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
  label: string;
  isLive: boolean;
}

export interface DraftLogList {
  logs: DraftLog[];
  current: string;
}

export interface Ack {
  ok: boolean;
  message: string;
}

// --- File-menu tools --------------------------------------------------------

export interface DraftExport {
  ok: boolean;
  message: string;
  text: string;
  fileName: string;
  format: string;
}

export interface LocateData {
  ok: boolean;
  message: string;
  path: string;
}

// --- Post-draft recap -------------------------------------------------------

export interface RecapCard {
  name: string;
  winRate: number | null;
}

export interface RecapPick {
  name: string;
  pack: number;
  pick: number;
  reference: number;
  delta: number;
}

export interface RecapArchetype {
  name: string;
  winRate: number | null;
}

export interface RecapRole {
  label: string;
  count: number;
}

export interface Recap {
  hasData: boolean;
  poolPower: number;
  grade: string;
  gradeStyle: string;
  top23Avg: number;
  formatAvg: number;
  archetypes: RecapArchetype[];
  bestCards: RecapCard[];
  steals: RecapPick[];
  reaches: RecapPick[];
  tribes: RecapRole[];
  roles: RecapRole[];
  staples: RecapCard[];
  nonBasicLands: RecapCard[];
  rares: RecapCard[];
  cmcDistribution: number[];
  typeCounts: Record<string, number>;
  isSealed: boolean;
  draftId: string;
}

export interface DraftRecord {
  found: boolean;
  wins: number;
  losses: number;
  url: string;
}

// --- Custom deck builder ------------------------------------------------------

export interface DeckRow {
  name: string;
  count: number;
  cmc: number;
  types: string[];
  colors: string[];
  manaCost: string;
  gihwr: number | null;
  rowTag: string;
  image: string[];
}

export interface DeckPip {
  symbol: string;
  name: string;
  count: number;
}

export interface DeckStats {
  totalCards: number;
  creatures: number;
  noncreatures: number;
  lands: number;
  avgCmc: number;
  pips: DeckPip[];
  curve: Record<string, number>;
  tribes: RecapRole[];
  tags: RecapRole[];
  basics: Record<string, number>;
}

export interface SimStats {
  mulligans: number;
  screwT3: number;
  screwT4: number;
  floodT5: number;
  castT2: number;
  castT3: number;
  castT4: number;
  curveOut: number;
  removalT4: number;
  colorScrewT3: number;
  avgHandSize: number;
}

export interface SimResult {
  ok: boolean;
  message: string;
  stats: SimStats | null;
  optimizationNote: string;
  advice: string[];
}

export interface DeckState {
  deck: DeckRow[];
  sideboard: DeckRow[];
  stats: DeckStats;
  mainCount: number;
  sideboardCount: number;
  activeFilter: string;
}

export interface SampleHand {
  cards: DeckRow[];
  message: string;
}

export interface DeckExport {
  text: string;
}

// --- Suggest deck (AI archetype builder) --------------------------------------

export interface SuggestArchetype {
  label: string;
  labelPrefix: string;
  rating: number;
  record: string;
  colors: string[];
  identityColors: string[];
  breakdown: string;
  mainCount: number;
}

export interface SuggestState {
  status: string;
  isBuilding: boolean;
  stale: boolean;
  archetypes: SuggestArchetype[];
  selected: string;
  deck: DeckRow[];
  sideboard: DeckRow[];
  stats: DeckStats;
  mainCount: number;
  sideboardCount: number;
  breakdown: string;
  sim: SimResult | null;
  activeFilter: string;
}

export interface SuggestProgress {
  kind: "status" | "variant";
  text: string;
  archetype: SuggestArchetype | null;
}

// --- Sealed studio ------------------------------------------------------------

export interface SealedVariant {
  name: string;
  isActive: boolean;
  mainCount: number;
}

export interface SealedState {
  hasPool: boolean;
  poolSize: number;
  sessionId: string;
  variants: SealedVariant[];
  activeVariant: string;
  deck: DeckRow[];
  sideboard: DeckRow[];
  stats: DeckStats;
  mainCount: number;
  sideboardCount: number;
  activeFilter: string;
}

export interface SealedAction {
  ok: boolean;
  message: string;
  state: SealedState;
}

export interface SealedDeckTech {
  ok: boolean;
  url: string;
  text: string;
  message: string;
}

// --- Practice pools (random / imported sealed) ----------------------------------

export interface PracticeSet {
  code: string;
  name: string;
  label: string;
  isActive: boolean;
}

export interface PracticeSets {
  sets: PracticeSet[];
  defaultCode: string;
}

// --- Compare workspace ---------------------------------------------------------

export interface CompareState {
  cards: Card[];
  activeFilter: string;
  availableNames: string[];
}

// --- Tier lists ------------------------------------------------------------------

export interface TierListEntry {
  setCode: string;
  label: string;
  date: string;
  fileName: string;
}

export interface TierLists {
  lists: TierListEntry[];
  sets: string[];
  activeFilter: string;
}

export interface TierAction {
  ok: boolean;
  message: string;
  lists: TierLists;
}
