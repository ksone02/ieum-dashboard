import { ArrowUpRight, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { PersonaLite, PolicyRec } from './types';
import { REC_KIND } from './types';

type Props = {
  rec: PolicyRec;
  region: string;
  byId: Map<string, PersonaLite>;
  onClose: () => void;
  onPersona: (id: string) => void;
};

const HOW: Record<PolicyRec['kind'], string> = {
  condition: '이 사업의 조건 하나만 바꿔서 다시 따져 봤을 때, 새로 갈 수 있게 되는 페르소나를 셌어요.',
  new: '지금 사업의 조건을 바꿔도 열리지 않거나, 열려도 이 사람들에게 맞는 방식이 아니에요.',
  notice: '공고에 운영 시간이 적혀 있지 않아서, 평일 낮에 못 가는 사람이 갈 수 있는지 판정할 수 없어요.',
  round: '조건 문제가 아니라 올해 신청 기간이 지났어요.',
};

export default function PolicyPanel({ rec, region, byId, onClose, onPersona }: Props) {
  const reps = rec.personas.filter(id => byId.get(id)?.kind === 'rep');
  const dongs = Object.entries(rec.dongs);
  return (
    <aside className="panel" aria-label="정책 추천 상세">
      <header className="panel-head">
        <span className={`rec-kind kind-${rec.kind}`}>{REC_KIND[rec.kind]}</span>
        <div>
          <h2>{rec.title}</h2>
          <p>
            {region === '강남' ? '강남구' : '춘천시'} · {rec.functions.join(', ')}
          </p>
        </div>
        <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="정책 추천 닫기">
          <X />
        </Button>
      </header>
      <div className="panel-body">
        <section className="step">
          <div className="rec-hero">
            <b className="num">{rec.count}</b>
            <span>명의 페르소나에게 해당해요</span>
          </div>
          <p className="rec-why">{rec.why}</p>
          <p className="assume">{HOW[rec.kind]}</p>
          {rec.source && (
            <a className="rec-link" href={rec.source} target="_blank" rel="noreferrer">
              {rec.program} 공고 원문 보기
              <ArrowUpRight size={14} aria-hidden />
            </a>
          )}
        </section>

        {rec.examples && rec.examples.length > 0 && (
          <section className="step">
            <h3>다른 지역은 이렇게 하고 있어요</h3>
            <ul className="examples">
              {rec.examples.map(x => (
                <li key={x.program}>
                  <strong>
                    {x.region} · {x.program}
                  </strong>
                  <p>
                    {x.form} · {x.time}
                  </p>
                  <p className="dim">
                    {x.checked === '원문 일치' ? '공고 원문과 대조했어요' : '공고 원문 대조 전이에요'}
                  </p>
                  <a href={x.url} target="_blank" rel="noreferrer" aria-label={`${x.program} 원문 열기`}>
                    <ArrowUpRight size={16} />
                  </a>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className="step">
          <h3>어느 동에 해당하나요</h3>
          {dongs.length ? (
            <ul className="dong-bars">
              {dongs.map(([d, n]) => (
                <li key={d}>
                  <span>{d}</span>
                  <i style={{ width: `${(n / dongs[0][1]) * 100}%` }} />
                  <b className="num">{n}</b>
                </li>
              ))}
            </ul>
          ) : (
            <p className="dim">동 단위가 아닌 대표 사례에만 해당해요.</p>
          )}
          {reps.length > 0 && (
            <p className="assume">대표 사례 {reps.map(id => byId.get(id)!.id).join(', ')}도 해당해요.</p>
          )}
        </section>

        <section className="step">
          <h3>해당하는 페르소나</h3>
          <ul className="who">
            {rec.personas.slice(0, 40).map(id => {
              const p = byId.get(id);
              if (!p) return null;
              return (
                <li key={id}>
                  <button onClick={() => onPersona(id)}>
                    <span className={`dot lvd-${p.level}`} aria-hidden />
                    {p.dong ? `${p.dong} · ` : ''}
                    {p.title}
                  </button>
                </li>
              );
            })}
          </ul>
          {rec.personas.length > 40 && <p className="dim">외 {rec.personas.length - 40}명</p>}
        </section>
      </div>
      <footer className="panel-foot">
        숫자는 가상 페르소나 수예요. 실제 주민 수가 아니에요. 판정은 사업 공고에 적힌 조건으로 했어요.
      </footer>
    </aside>
  );
}
