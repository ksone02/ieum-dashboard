import type { FeatureCollection } from 'geojson';

export type Status = 'open' | 'mismatch' | 'unknown' | 'blocked';
export type FindingKind = 'blocked' | 'mismatch' | 'unknown' | 'closed';
export type Site = { lat: number; lng: number; place: string; outside: boolean };
export type Rec = { rank: number; id: string; name: string; delivery: string; delivery_sure: string; path: string; schedule: string; fits: boolean; source: string; sites: Site[]; away?: boolean };
export type Field = {
  function: string; status: Status; portfolio: string; total: number; programs: Rec[];
  reasons: { reason: string; count: number }[]; blocked: { name: string; reasons: string[]; sites: Site[] }[];
  opens_if: { change: string; programs: { id: string; name: string }[] }[];
};
export type Finding = { kind: FindingKind; function: string; title: string; why: string; action: string };
export type Persona = {
  id: string; kind: 'rep' | 'dong'; region: string; dong: string | null; title: string; trait: string; mode_order: string[];
  evidence: { source: string; text: string }[]; assumptions: string[]; location: { lat: number; lng: number } | null;
  fields: Field[]; findings: Finding[];
  level: Level; level_name: string; level_why: { signal: string; gap: string }; actions: string[]; trace: string[];
};
export type Tone = 'bad' | 'warn' | 'muted' | 'ok';
export type Level = 1 | 2 | 3 | 4;
export const LEVEL_NAME: Record<Level, string> = { 1: '긴급', 2: '높음', 3: '주의', 4: '관찰' };
export type PersonaLite = Pick<Persona, 'id' | 'kind' | 'region' | 'dong' | 'title' | 'trait' | 'location' | 'level' | 'level_name'> & {
  severity: Tone; findings: Pick<Finding, 'kind' | 'function' | 'title'>[];
};
export type DongGroup = { dong: string; location: { lat: number; lng: number } | null; personas: string[]; severity: Tone; level: Level; levels: Record<Level, number>; counts: Record<FindingKind, number>; gaps: number };
export type Agent = {
  personas: PersonaLite[]; functions: string[]; notice: string; rule: string; checked_at: string; level_rule: string;
  regions: Record<string, { geojson: FeatureCollection; personas: string[]; dongs: DongGroup[]; dong_personas: number; levels: Record<Level, number>; scan: { groups: number; found: number; programs: number }; narrow: { level: Level; count: number; function: string; programs: string[] } | null }>;
};
/** 지도 핀·아바타에 쓰는 짧은 표시. 대표는 P1, 동별은 여20처럼. */
export const short = (p: Pick<Persona, 'id' | 'kind'>) => (p.kind === 'rep' ? p.id : p.id.split('-').pop()!);

export const STATUS: Record<Status, { label: string; tone: string }> = {
  open: { label: '갈 곳', tone: 'ok' },
  mismatch: { label: '방식 다름', tone: 'warn' },
  unknown: { label: '확인 필요', tone: 'muted' },
  blocked: { label: '갈 곳 없음', tone: 'bad' },
};
export const KIND: Record<FindingKind, { label: string; tone: string }> = {
  blocked: { label: '막힘', tone: 'bad' }, mismatch: { label: '방식 안 맞음', tone: 'warn' },
  unknown: { label: '정보 부족', tone: 'muted' }, closed: { label: '모집 종료', tone: 'muted' },
};
export const PATH: Record<string, string> = { '이용 가능': '바로 신청해요', '조건부(심사)': '심사를 거쳐요', '조건부(부가정보 미확인)': '확인이 더 필요해요' };

export const TONE_LABEL: Record<Tone, string> = { bad: '갈 곳 없음', warn: '방식 다름', muted: '확인 필요', ok: '갈 곳 있음' };

export type RecKind = 'condition' | 'new' | 'notice' | 'round';
export type PolicyRec = {
  kind: RecKind; id: string; title: string; why: string; functions: string[];
  count: number; personas: string[]; dongs: Record<string, number>;
  program?: string; program_id?: string; action?: string; source?: string; function?: string; mode?: string;
  examples?: { region: string; program: string; form: string; time: string; url: string; checked: string }[];
};
export type Policy = Record<string, { recs: PolicyRec[]; whole: Record<string, number>; personas: number; ended: string[] }>;
export const REC_KIND: Record<RecKind, string> = { condition: '조건 바꾸기', new: '새 사업 필요', notice: '공고 보완', round: '모집 회차' };
