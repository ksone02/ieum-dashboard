import { useCallback, useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { ChevronDown, ChevronLeft, ChevronRight, CircleCheck, ScanSearch, Settings2, X as XIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import AgentMap, { type MapSettings } from './AgentMap';
import PersonaPanel from './PersonaPanel';
import PolicyPanel from './PolicyPanel';
import ScanLoader from './ScanLoader';
import type { Agent, Level, Persona, PersonaLite, Policy } from './types';
import { LEVEL_NAME, REC_KIND, short } from './types';
import './agent.css';

const REGIONS = [
  ['강남', '강남구'],
  ['춘천', '춘천시'],
] as const;
const LEVELS: Level[] = [1, 2, 3, 4];
// 결과는 export_dashboard_static.py가 미리 만든 정적 JSON이라 서버 없이도 돌아감(Vercel 배포용)
const getJSON = <T,>(url: string): Promise<T> =>
  fetch(url).then(r => (r.ok ? r.json() : Promise.reject(new Error('자료를 불러오지 못했어요'))));
let personasCache: Promise<Record<string, Persona>> | null = null;
const loadPersonas = () => (personasCache ??= getJSON<Record<string, Persona>>('/data/personas.json'));
const regionName = (r: string) => (r === '강남' ? '강남구' : '춘천시');
// 페르소나 제목 "밖에 잘 안 나가는 20대 남성" → 유형 "밖에 잘 안 나가는", 사람 "20대 남성"
const typeTitle = (t: string) => t.replace(/ (\d0대|60대 이상) (남성|여성)$/, '');
const who = (t: string) => (t.match(/(\d0대|60대 이상) (남성|여성)$/)?.[0] ?? t).replace('60대 이상', '60대+');
const firstFn = (p: PersonaLite) => (p.findings.find(f => f.kind !== 'closed') ?? { function: '관계 형성' }).function;

function Row({ p, on, onClick, label }: { p: PersonaLite; on: boolean; onClick: () => void; label?: string }) {
  const top = p.findings.find(f => f.kind !== 'closed');
  return (
    <button className={on ? 'on' : ''} onClick={onClick}>
      <span className={`lv-chip lv-${p.level}`}>{p.level_name}</span>
      <span className="bl-text">
        <b>{label ?? p.title}</b>
        <small>{top ? top.title : '연결할 사업이 있어요'}</small>
      </span>
      <ChevronRight size={16} className="bl-go" aria-hidden />
    </button>
  );
}

export default function AgentApp() {
  const [agent, setAgent] = useState<Agent | null>(null);
  const [error, setError] = useState('');
  const [scanning, setScanning] = useState(true);
  const [region, setRegion] = useState('강남');
  const [tab, setTab] = useState<'dong' | 'rep' | 'policy'>('dong');
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [recId, setRecId] = useState<string | null>(null);
  const [dong, setDong] = useState<string | null>(null);
  const [persona, setPersona] = useState<Persona | null>(null);
  const [fn, setFn] = useState('관계 형성');
  const [settings, setSettings] = useState<MapSettings>({ basemap: true, boundaries: true, lines: true });
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [hover, setHover] = useState<string | null>(null);

  const choose = useCallback(
    (id: string, list: PersonaLite[] | undefined = agent?.personas, f?: string | null) => {
      const lite = list?.find(x => x.id === id);
      if (!lite) return;
      loadPersonas()
        .then(all => all[id] ?? Promise.reject(new Error('페르소나를 찾지 못했어요')))
        .then((p: Persona) => {
          setRecId(null);
          setPersona(p);
          setRegion(p.region);
          setFn(f ?? firstFn(lite));
          if (p.kind === 'dong') {
            setDong(p.dong);
            setTab('dong');
          } else {
            setDong(null);
            setTab('rep');
          }
        })
        .catch(e => setError(e.message || '페르소나를 불러오지 못했어요'));
    },
    [agent],
  );

  useEffect(() => {
    getJSON<Agent>('/data/agent.json')
      .then(v => {
        setAgent(v);
        const q = new URLSearchParams(location.search); // 발표 캡처용 바로가기: ?p=P3&fn=관계 형성, ?d=논현1동, ?r=춘천, ?now
        if (q.has('now')) setScanning(false);
        if (q.get('r') && v.regions[q.get('r')!]) setRegion(q.get('r')!);
        if (q.get('d')) setDong(q.get('d'));
        if (q.get('p')) choose(q.get('p')!, v.personas, q.get('fn'));
        if (q.get('tab') === 'policy') setTab('policy');
        if (q.get('rec')) {
          setTab('policy');
          setRecId(q.get('rec'));
        }
      })
      .catch(e => setError(e.message || '자료를 불러오지 못했어요'));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    getJSON<Policy>('/data/policy.json')
      .then(setPolicy)
      .catch(() => setPolicy(null));
  }, []);

  const finishScan = useCallback(() => setScanning(false), []);

  if (error)
    return (
      <div className="agent-empty">
        <b>자료를 불러오지 못했어요</b>
        <span>서버를 켠 뒤 새로고침하면 다시 볼 수 있어요</span>
      </div>
    );
  if (!agent || scanning) return <ScanLoader done={!!agent} onFinish={finishScan} />;

  const R = agent.regions[region];
  const byId = new Map(agent.personas.map(p => [p.id, p]));
  const inRegion = agent.personas.filter(p => p.region === region);
  const reps = R.personas.map(id => byId.get(id)!);
  const group = dong ? R.dongs.find(d => d.dong === dong) : null;
  const urgent = R.dongs[0]; // 위험 단계가 가장 높은 동이 맨 앞
  const recs = policy?.[region]?.recs ?? [];
  const rec = recs.find(r => r.id === recId) ?? null;
  const openRec = (id: string) => {
    setRecId(id);
    setPersona(null);
    setDong(null);
    setTab('policy');
  };

  return (
    <div className={`agent-app ${persona || rec ? 'with-panel' : ''}`}>
      <AgentMap
        agent={agent}
        region={region}
        persona={persona}
        fn={fn}
        settings={settings}
        panelOpen={!!persona || !!rec}
        dong={dong}
        hover={hover}
        tab={tab}
        rec={persona ? null : rec}
        onPersona={id => choose(id)}
        onDong={d => {
          setDong(d);
          setTab('dong');
          setPersona(null);
          setRecId(null);
        }}
      />

      <header className="topbar">
        <div className="brand">
          <img className="logo" src="/icons/logo-128.png" alt="" width={32} height={32} />
          <div>
            <strong>이음</strong>
            <small>고립 지원을 잇는 에이전트</small>
          </div>
        </div>
        <div className="seg" role="tablist" aria-label="지역 고르기">
          {REGIONS.map(([k, label]) => (
            <button
              key={k}
              role="tab"
              aria-selected={region === k}
              className={region === k ? 'on' : ''}
              onClick={() => {
                setRegion(k);
                setPersona(null);
                setDong(null);
                setRecId(null);
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <Button variant="ghost" size="icon" aria-label="설정 열기" onClick={() => setSettingsOpen(true)}>
          <Settings2 />
        </Button>
      </header>

      <section className={`brief${group ? ' dong-view' : ''}`} aria-label="에이전트 브리핑">
        {group ? (
          <>
            <button
              className="back"
              onClick={() => {
                setDong(null);
                setPersona(null);
              }}
            >
              <ChevronLeft size={16} aria-hidden />
              {regionName(region)} 전체 보기
            </button>
            <h1>
              {group.dong} 페르소나 {group.personas.length}명
            </h1>
            <p className="brief-sub">
              같은 성별·나이대보다 고립 쪽 특성이 두드러진 집단이에요. 혼자 산다고 가정했어요.
            </p>
            <ul className="brief-list groups">
              {Object.entries(
                group.personas
                  .map(id => byId.get(id)!)
                  .reduce<Record<string, PersonaLite[]>>((g, p) => ((g[p.trait] ??= []).push(p), g), {}),
              ).map(([trait, ps], i) => (
                <motion.li
                  key={trait}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.05 * i, type: 'spring', stiffness: 380, damping: 32 }}
                >
                  <p className="g-title">{typeTitle(ps[0].title)}</p>
                  <p className="g-gap">
                    {(() => {
                      const t = ps.map(p => p.findings.find(f => f.kind !== 'closed')?.title ?? '연결할 사업이 있어요');
                      return t.sort((a, b) => t.filter(x => x === b).length - t.filter(x => x === a).length)[0];
                    })()}
                  </p>
                  <div className="g-chips">
                    {[...ps]
                      .sort((a, b) => a.level - b.level)
                      .map(p => (
                        <button
                          key={p.id}
                          className={`g-chip lv-${p.level}${persona?.id === p.id ? ' on' : ''}`}
                          onClick={() => choose(p.id)}
                          aria-label={`${p.title} · ${p.level}단계 ${p.level_name}`}
                        >
                          <i className={`dot lvd-${p.level}`} aria-hidden />
                          {who(p.title)}
                        </button>
                      ))}
                  </div>
                </motion.li>
              ))}
            </ul>
          </>
        ) : (
          <>
            <p className="agent-tag">
              <ScanSearch size={14} aria-hidden />
              에이전트 브리핑<span className="virtual">모두 가상 인물</span>
            </p>
            <h1>
              {urgent ? (
                <>{urgent.dong}부터 살펴보면 좋아요</>
              ) : (
                <>
                  {regionName(region)} 페르소나 {inRegion.length}명을 확인했어요
                </>
              )}
            </h1>
            <p className="brief-sub">
              {regionName(region)} 페르소나 {inRegion.length}명 중{' '}
              {urgent
                ? `${urgent.dong}에 ${urgent.level}단계(${LEVEL_NAME[urgent.level]})가 ${urgent.levels[urgent.level]}명 있어요`
                : '먼저 볼 곳이 없어요'}
            </p>
            <details className="worklog" open={innerWidth >= 900 && innerHeight >= 900}>
              <summary>
                <ScanSearch size={14} aria-hidden />
                에이전트가 한 일<ChevronDown size={14} className="chev" aria-hidden />
              </summary>
              <ol>
                {[
                  <>
                    {region === '강남' ? '연락·외출 예측과 주말 사람 흐름' : '주말 사람 흐름'}으로 동 × 성별 × 나이대{' '}
                    <b>{R.scan.groups}개</b> 집단을 살펴봤어요
                  </>,
                  <>
                    고립 쪽 특성이 두드러진 집단 <b>{R.scan.found}개</b>를 페르소나로 만들고, 대표 사례 {reps.length}
                    명과 함께 봤어요
                  </>,
                  <>
                    사업 <b>{R.scan.programs}개</b>의 신청 조건을 한 명씩 확인했어요
                  </>,
                  <>
                    사업 조건 <b>{Object.keys(policy?.[region]?.whole ?? {}).length || 5}가지</b>를 바꿔 보며 누가 갈 수
                    있는지 다시 따져 봤어요
                  </>,
                  <>
                    신호와 지원 공백으로 단계를 정했어요
                    {urgent ? (
                      <>
                        {' '}
                        · 먼저 볼 곳은 <b>{urgent.dong}</b>
                      </>
                    ) : null}
                  </>,
                ].map((t, i) => (
                  <li key={i}>
                    <CircleCheck size={15} aria-hidden />
                    <span>{t}</span>
                  </li>
                ))}
              </ol>
            </details>
            <div className="brief-stats four">
              {LEVELS.map(l => (
                <div key={l} className={`stat lv-${l}`}>
                  <b className="num">{R.levels[l]}</b>
                  <span>
                    {l}단계 {LEVEL_NAME[l]}
                  </span>
                </div>
              ))}
            </div>
            <p className="checked">
              자료 2025년 7~12월 · 공고 기준 {agent.checked_at} · 새 공고가 들어오면 다시 점검해요
            </p>
            {R.narrow && tab !== 'policy' && (
              <p className="whatif-all narrow" title={R.narrow.programs.join(' · ')}>
                <b>
                  {R.narrow.level}단계 {R.narrow.count}명
                </b>
                은 맞는 {R.narrow.function} 사업이 같은 {R.narrow.programs.length}곳뿐이라 할 일이 같아요. 사업 선택지가
                좁다는 뜻이에요.{' '}
                <button className="link" onClick={() => setTab('policy')}>
                  정책 추천 보기
                </button>
              </p>
            )}
            {new Set(inRegion.map(p => p.level)).size === 1 && (
              <p className="ended">
                {regionName(region)}은 신호가 주말 사람 흐름 하나뿐이라 단계가 나뉘지 않아요. 같은 단계 안에서는
                페르소나가 많은 동이 위에 있어요.
              </p>
            )}
            <div className="brief-tabs" role="tablist" aria-label="목록 고르기">
              <button
                role="tab"
                aria-selected={tab === 'dong'}
                className={tab === 'dong' ? 'on' : ''}
                onClick={() => setTab('dong')}
              >
                동별 {R.dongs.length}곳
              </button>
              <button
                role="tab"
                aria-selected={tab === 'rep'}
                className={tab === 'rep' ? 'on' : ''}
                onClick={() => setTab('rep')}
              >
                대표 사례 {reps.length}명
              </button>
              <button
                role="tab"
                aria-selected={tab === 'policy'}
                className={tab === 'policy' ? 'on' : ''}
                onClick={() => setTab('policy')}
              >
                정책 추천 {recs.length}건
              </button>
            </div>
            {tab === 'policy' &&
              policy?.[region] &&
              (() => {
                const w = Object.entries(policy[region].whole).filter(([, n]) => n > 0);
                return (
                  <div className="whatif-all">
                    <p className="whatif-title">지역 전체에서 조건을 바꾸면</p>
                    {w.map(([k, n]) => (
                      <p key={k}>
                        <b>{k}</b> → 페르소나 <b className="num">{n}</b>명에게 길이 새로 열려요
                      </p>
                    ))}
                    <p className="dim">
                      {w.length ? '나머지 조건' : '조건 5가지 모두'}은 바꿔도 새로 열리는 페르소나가 없어요
                    </p>
                  </div>
                );
              })()}
            <ul className="brief-list scroll">
              <AnimatePresence initial>
                {tab === 'policy'
                  ? recs.map((r, i) => (
                      <motion.li
                        key={r.id}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: Math.min(0.05 * i, 0.4) }}
                      >
                        <button className={recId === r.id ? 'on' : ''} onClick={() => openRec(r.id)}>
                          <b className="rec-count num">
                            {r.count}
                            <small>명</small>
                          </b>
                          <span className="bl-text">
                            <b>{r.title}</b>
                            <small>
                              {REC_KIND[r.kind]} · {r.functions.join(', ')}
                            </small>
                          </span>
                          <ChevronRight size={16} className="bl-go" aria-hidden />
                        </button>
                      </motion.li>
                    ))
                  : tab === 'rep'
                    ? reps.map((p, i) => (
                        <motion.li
                          key={p.id}
                          initial={{ opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: 0.08 * i }}
                        >
                          <Row p={p} on={persona?.id === p.id} onClick={() => choose(p.id)} />
                        </motion.li>
                      ))
                    : R.dongs.map((d, i) => (
                        <motion.li
                          key={d.dong}
                          initial={{ opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: Math.min(0.04 * i, 0.4) }}
                        >
                          <button
                            aria-label={`${d.dong} · 페르소나 ${d.personas.length}명 · ${LEVELS.filter(l => d.levels[l])
                              .map(l => `${l}단계 ${d.levels[l]}명`)
                              .join(' · ')}`}
                            title={LEVELS.filter(l => d.levels[l])
                              .map(l => `${l}단계 ${d.levels[l]}명`)
                              .join(' · ')}
                            onClick={() => {
                              setDong(d.dong);
                              setPersona(null);
                              setHover(null);
                            }}
                            onMouseEnter={() => setHover(d.dong)}
                            onMouseLeave={() => setHover(null)}
                            onFocus={() => setHover(d.dong)}
                            onBlur={() => setHover(null)}
                          >
                            <span className={`lv-chip lv-${d.level}`}>{LEVEL_NAME[d.level]}</span>
                            <span className="bl-text">
                              <b>{d.dong}</b>
                              <small>
                                페르소나 {d.personas.length}명{d.gaps > 0 && ` · 공백 분야 최대 ${d.gaps}개`}
                              </small>
                              <span
                                className="lv-bar"
                                aria-hidden
                                style={{
                                  width: `${(d.personas.length / Math.max(...R.dongs.map(x => x.personas.length))) * 100}%`,
                                }}
                              >
                                {LEVELS.filter(l => d.levels[l]).map(l => (
                                  <i key={l} className={`lvd-${l}`} style={{ flexGrow: d.levels[l] }} />
                                ))}
                              </span>
                            </span>
                            <ChevronRight size={16} className="bl-go" aria-hidden />
                          </button>
                        </motion.li>
                      ))}
              </AnimatePresence>
            </ul>
            {tab === 'policy' && !policy && <p className="dim">정책 추천을 계산하고 있어요</p>}
            {tab === 'policy' && !!policy?.[region]?.ended.length && (
              <p className="ended">
                {policy[region].ended.join(', ')} 사업은 올해 모집이 끝나서 모든 페르소나가 신청할 수 없어요. 다음
                모집이 열리면 다시 점검해요.
              </p>
            )}
            {!persona && !rec && tab !== 'policy' && urgent && (
              <Button
                className="brief-cta"
                onClick={() => {
                  setDong(urgent.dong);
                  setTab('dong');
                }}
              >
                {urgent.dong} 먼저 살펴보기
              </Button>
            )}
          </>
        )}
      </section>

      {!persona && !dong && !rec && <p className="hint">지도에서 동이나 인물을 누르면 부족한 지원을 볼 수 있어요</p>}

      <div className="legend" aria-label="지도 표시 안내">
        {LEVELS.map(l => (
          <span key={l}>
            <i className={`dot lvd-${l}`} />
            {l}단계 {LEVEL_NAME[l]}
          </span>
        ))}
        {persona && (
          <>
            <span>
              <i className="dot dot-ok" />
              추천 장소
            </span>
            <span>
              <i className="x">
                <XIcon size={11} strokeWidth={3} />
              </i>
              조건이 안 맞는 장소
            </span>
          </>
        )}
      </div>

      {persona && (
        <PersonaPanel
          key={persona.id}
          persona={persona}
          badge={short(persona)}
          fn={fn}
          recs={recs}
          onFn={setFn}
          onClose={() => setPersona(null)}
          onRec={openRec}
        />
      )}
      {!persona && rec && (
        <PolicyPanel
          key={rec.id}
          rec={rec}
          region={region}
          byId={byId}
          onClose={() => setRecId(null)}
          onPersona={id => choose(id)}
        />
      )}

      <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
        <DialogContent className="agent-dialog" showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>설정</DialogTitle>
            <DialogDescription>지도에 보일 것을 고를 수 있어요</DialogDescription>
          </DialogHeader>
          {(
            [
              ['basemap', '배경 지도', '인터넷에 연결돼 있으면 보여요'],
              ['boundaries', '동 경계', '행정동 경계와 동별 색을 보여줘요'],
              ['lines', '연결선', '인물에서 추천 장소까지 점선으로 이어줘요'],
            ] as const
          ).map(([k, t, d]) => (
            <label key={k} className="set-row">
              <span>
                <b>{t}</b>
                <small>{d}</small>
              </span>
              <Switch checked={settings[k]} onCheckedChange={v => setSettings(s => ({ ...s, [k]: v }))} />
            </label>
          ))}
          <div className="set-note">
            <b>이 화면의 자료</b>
            <p>{agent.notice}</p>
            <p>위험 단계는 이렇게 정했어요. {agent.level_rule}. 고립 확률이 아니라 먼저 살펴볼 순서예요.</p>
            <p>동별 페르소나는 이렇게 골랐어요. {agent.rule}. 혼자 살고, 60세 미만은 평일 낮에 일한다고 가정했어요.</p>
            <p>
              에이전트는 연락·외출 예측 모델의 결과와 주말 사람 흐름을 신호로 쓰고, 사업마다 신청 조건을 하나씩 확인해서
              판단해요. 문장은 그 판단 결과를 정해진 양식에 채워서 만들어요.
            </p>
            <p>
              연락·외출이 적다고 꼭 외롭거나 고립된 건 아니에요. 재택근무나 돌봄 때문일 수도 있어요. 춘천은 주말 사람
              흐름 하나로만 골라서 대학가처럼 주말에 사람이 빠지는 동이 함께 걸릴 수 있어요.
            </p>
            <p>강남 37개·춘천 17개 사업 공고를 조사했어요. 지도 위 장소는 주소를 근사해서 찍었어요.</p>
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="secondary">닫기</Button>
            </DialogClose>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
