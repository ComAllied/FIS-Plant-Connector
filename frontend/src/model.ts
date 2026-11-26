export type Reader = {
  id: string;
  label: string;
  plantId: string | null;
  lineId: string | null;
  areaId: string | null;
  description: string | null;
  eventCount: number;
  distinctCaseCount: number;
  qualityFlags: string[];
};

export type Transition = {
  id: string;
  source: string;
  target: string;
  transitionCount: number;
  distinctCaseCount: number;
  activeDaysUtc: number;
  outgoingShare: number;
  minDurationSeconds: number;
  medianDurationSeconds: number;
  p90DurationSeconds: number;
  maxDurationSeconds: number;
  longGapCount: number;
};

export type Quality = {
  inputRows: number;
  normalizedRows: number;
  deduplicatedRows: number;
  missingCaseRows: number;
  missingReaderRows: number;
  missingTimeRows: number;
  conflictingEventKeys: number;
  casesWithUnplacedEvent: number;
  ambiguousOrderRows: number;
  candidatePairs: number;
  includedPairs: number;
  excludedPairs: Record<string, number>;
  firstObservationUtc: string | null;
  lastObservationUtc: string | null;
  longGapSeconds: number;
};

export type Graph = {
  topologyId: string;
  mappingStatus: "synthetic" | "candidate" | "confirmed";
  nodes: Reader[];
  edges: Transition[];
  quality: Quality;
  source: {fileCount: number; repeatedContentFiles: number};
  variants: {distinctVariantCount: number; observableCaseCount: number};
};

export type Point = {x: number; y: number};
export type Rectangle = Point & {width: number; height: number};
export type Layout = {
  engine: "elk-layered" | "grouped-grid";
  version: number;
  width: number;
  height: number;
  groups: Array<Rectangle & {id: string; label: string}>;
  nodes: Record<string, Rectangle>;
  edges: Record<string, Point[][]>;
};

export const groupId = (reader: Reader) =>
  JSON.stringify([reader.plantId, reader.lineId]);

export const groupLabel = (reader: Reader) =>
  [reader.plantId, reader.lineId ?? "Unassigned line"].filter(Boolean).join(" / ");
