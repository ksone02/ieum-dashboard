import { ArrowUpRight, Building2, ChevronRight, Home, MapPin, PhoneCall, ScanSearch, Users, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { Field, Persona, PolicyRec } from './types';
import { KIND, PATH, REC_KIND, STATUS } from './types';
import { ListChecks } from 'lucide-react';

const SRC: Record<string, string> = {
  '연락·외출 예측': 'model',
  '주말 사람 흐름': 'flow',
  '소비 패턴': 'card',
  주의: 'warn',
};
const MODE_ICON: Record<string, typeof Users> = {
  '나가서 만남': Users,
  '전화·온라인': PhoneCall,
  '집으로 찾아옴': Home,
};

type Props = {
  persona: Persona;
  badge: string;
  fn: string;
  recs: PolicyRec[];
  onFn: (f: string) => void;
  onClose: () => void;
  onRec: (id: string) => void;
};

export default function PersonaPanel({ persona, badge, fn, recs, onFn, onClose, onRec }: Props) {
  const field = persona.fields.find(f => f.function === fn)!;
  const finding = persona.findings.find(f => f.function === fn);
  const first = persona.mode_order[0];
  const fixing = finding && finding.kind !== 'closed';
  const chip = (f: Field) => {
    const k = persona.findings.find(x => x.function === f.function)?.kind;
    if (k === 'closed') return { label: '모집 끝남', tone: 'muted' };
    return {
      label: STATUS[f.status].label + (f.status === 'open' || f.status === 'mismatch' ? ` ${f.programs.length}` : ''),
      tone: STATUS[f.status].tone,
    };
  };
  return (
    <aside className="panel" aria-label={`${persona.id} 분석`}>
      <header className="panel-head">
        <span className="avatar">{badge}</span>
        <div>
          <h2>{persona.title}</h2>
          <p>
            {persona.region === '강남' ? '강남구' : '춘천시'} {persona.dong ?? '전체 경향'} ·{' '}
            {persona.kind === 'rep' ? '대표 사례' : '동별 페르소나'} · 가상 인물
          </p>
        </div>
        <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="분석 창 닫기">
          <X />
        </Button>
      </header>

      <div className="panel-body">
        <section className={`level-box lv-${persona.level}`}>
          <div className="level-head">
            <b>{persona.level}단계</b>
            <span>{persona.level_name}</span>
          </div>
          <ul className="level-why">
            <li>
              <span>고립 쪽 신호</span>
              {persona.level_why.signal}
            </li>
            <li>
              <span>지원 공백</span>
              {persona.level_why.gap}
            </li>
          </ul>
          <p className="level-do-title">이 단계에서 할 일</p>
          <ol className="level-do">
            {persona.actions.map(a => (
              <li key={a}>{a}</li>
            ))}
          </ol>
          <div className="trace">
            <p className="trace-title">
              <ListChecks size={14} aria-hidden />
              에이전트가 이렇게 판단했어요
            </p>
            <ol>
              {persona.trace.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ol>
          </div>
        </section>
        <section className="step">
          <h3>
            <i>1</i>어떤 사람인가요
          </h3>
          <ul className="evidence">
            {persona.evidence.map(e => (
              <li key={e.text}>
                <span className={`src src-${SRC[e.source] ?? 'etc'}`}>{e.source}</span>
                {e.text}
              </li>
            ))}
          </ul>
          <p className="assume">이렇게 가정했어요 · {persona.assumptions.join(' · ')}</p>
        </section>

        <section className="step">
          <h3>
            <i>2</i>어떤 지원이 부족한가요
          </h3>
          <div className="fields" role="tablist" aria-label="지원 분야">
            {persona.fields.map(f => {
              const c = chip(f);
              return (
                <button
                  key={f.function}
                  role="tab"
                  aria-selected={f.function === fn}
                  className={`field-row ${f.function === fn ? 'on' : ''}`}
                  onClick={() => onFn(f.function)}
                >
                  <span>{f.function}</span>
                  <span className={`chip chip-${c.tone}`}>{c.label}</span>
                </button>
              );
            })}
          </div>
        </section>

        <section className="step">
          <h3>
            <i>3</i>왜 그런가요
          </h3>
          <div className={`agent-card tone-${finding ? KIND[finding.kind].tone : 'ok'}`}>
            <p className="agent-tag">
              <ScanSearch size={14} aria-hidden />
              에이전트 판단
            </p>
            {finding ? (
              <>
                <strong>{finding.title}</strong>
                <p>{finding.why}</p>
                <p className="agent-action">{finding.action}</p>
              </>
            ) : (
              <>
                <strong>
                  {fn} 사업 {field.total}개 중 {field.programs.length}개에 갈 수 있어요
                </strong>
                <p>이 사람에게는 「{first}」 방식이 먼저 맞아서, 그 순서로 정리했어요.</p>
              </>
            )}
            {field.reasons.length > 0 && (
              <p className="reasons">
                못 가는 사업이 걸린 조건 · {field.reasons.map(r => `${r.reason} ${r.count}개`).join(' · ')}
              </p>
            )}
          </div>
        </section>

        <section className="step">
          <h3>
            <i>4</i>
            {fixing ? '어떻게 보완할까요' : '어디로 연결할까요'}
          </h3>
          {field.programs.length > 0 && (
            <ol className="recs">
              {field.programs.map(r => {
                const Icon = MODE_ICON[r.delivery] ?? Building2;
                return (
                  <li key={r.id} className={r.fits ? 'fit' : ''}>
                    <span className="rank num">{r.rank}</span>
                    <div>
                      <strong>{r.name}</strong>
                      <p>
                        <span className="mode">
                          <Icon size={13} aria-hidden />
                          {r.delivery}
                          {r.delivery_sure === '추정' ? ' (추정)' : ''}
                        </span>
                        <span>{PATH[r.path] ?? r.path}</span>
                        {r.schedule === '야간·주말포함' && <span>저녁·주말에도 해요</span>}
                        {r.away && <span>{persona.region === '강남' ? '강남구' : '춘천시'} 안에는 지점이 없어요</span>}
                        {r.sites.length > 0 && (
                          <span>
                            <MapPin size={12} aria-hidden />
                            지도에 {r.sites.length}곳
                          </span>
                        )}
                      </p>
                    </div>
                    {r.source && (
                      <a href={r.source} target="_blank" rel="noreferrer" aria-label={`${r.name} 공고 원문 열기`}>
                        <ArrowUpRight size={16} />
                      </a>
                    )}
                  </li>
                );
              })}
            </ol>
          )}
          {field.opens_if.map(o => (
            <div key={o.change} className="whatif">
              <p>
                <b>{o.change}</b> {o.programs.length}개가 {field.status === 'open' ? '더 늘어나요' : '새로 열려요'}
              </p>
              <p className="dim">{o.programs.map(p => p.name).join(', ')}</p>
            </div>
          ))}
          {!field.programs.length && !field.opens_if.length && (
            <p className="dim">조건이 맞는 새 지원을 만들면 연결할 수 있어요.</p>
          )}
          {(() => {
            const mine = recs.filter(r => r.personas.includes(persona.id) && r.functions.includes(fn));
            return (
              mine.length > 0 && (
                <div className="mine">
                  <p className="mine-title">이 사람에게 해당하는 정책 추천</p>
                  {mine.map(r => (
                    <button key={r.id} onClick={() => onRec(r.id)}>
                      <span className={`rec-kind kind-${r.kind}`}>{REC_KIND[r.kind]}</span>
                      <span className="mine-text">
                        {r.title}
                        <small>같은 처지의 페르소나 {r.count}명</small>
                      </span>
                      <ChevronRight size={16} aria-hidden />
                    </button>
                  ))}
                </div>
              )
            );
          })()}
        </section>
      </div>
      <footer className="panel-foot">
        가상 인물이에요. 사업 공고에 적힌 조건으로 판정했고, 실제 주민 수를 뜻하지 않아요.
      </footer>
    </aside>
  );
}
