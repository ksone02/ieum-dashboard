import { useEffect, useRef } from 'react';
import L from 'leaflet';
import { renderToStaticMarkup } from 'react-dom/server';
import { X } from 'lucide-react';
import type { Agent, Persona, PolicyRec } from './types';
import { short } from './types';

export type MapSettings = { basemap: boolean; boundaries: boolean; lines: boolean };
type Props = {
  agent: Agent; region: string; persona: Persona | null; fn: string; settings: MapSettings; panelOpen: boolean;
  dong: string | null; hover?: string | null; tab: 'dong' | 'rep' | 'policy'; rec: PolicyRec | null; onPersona: (id: string) => void; onDong: (dong: string) => void;
};

const esc = (s: string) => s.replace(/[&<>"']/g, c => `&#${c.charCodeAt(0)};`);
const dongOf = (adm: string) => adm.split(' ').pop() ?? '';
const NO_ICON = renderToStaticMarkup(<X size={13} strokeWidth={3} aria-hidden />);
// 동 색은 그 동 페르소나 중 가장 심각한 상태. 진하지 않게 깔아서 핀과 배지가 먼저 보이게 함.
// 동 색은 그 동에서 가장 높은 위험 단계(1 긴급 ~ 4 관찰)
const FILL: Record<number, string> = { 1: '#f6c4cb', 2: '#fde1bd', 3: '#f7ebb4', 4: '#e3e8ee' };
// 화면 위에 떠 있는 브리핑·분석 창을 피해서 지도를 맞춤. 좁은 화면에서는 창이 아래에서 올라옴.
const pad = (panel: boolean) => innerWidth < 900
  ? { paddingTopLeft: L.point(20, panel ? 80 : 300), paddingBottomRight: L.point(20, panel ? innerHeight * 0.64 : 90) }
  : { paddingTopLeft: L.point(panel ? 350 : 380, panel ? 80 : 110), paddingBottomRight: L.point(panel ? 470 : 60, 60) };

// 지역 전체 경향 핀 자리: 동 핀과 겹치지 않는 지역 안 빈 곳. 위치 자체에는 의미 없음(핀에 "전체 경향" 표시).
const SPOTS: Record<string, [number, number][]> = { 강남: [[37.468, 127.1]], 춘천: [[37.985, 127.66], [37.79, 127.82]] };
function anchors(agent: Agent, region: string) {
  const out = new Map<string, L.LatLng>();
  const reps = agent.regions[region].personas.map(id => agent.personas.find(p => p.id === id)!);
  reps.filter(p => !p.location).forEach((p, i) => { const s = SPOTS[region]; const [lat, lng] = s[i % s.length]; out.set(p.id, L.latLng(lat, lng)); });
  for (const p of agent.personas) if (p.location && !out.has(p.id)) out.set(p.id, L.latLng(p.location.lat, p.location.lng));
  return out;
}

export default function AgentMap({ agent, region, persona, fn, settings, panelOpen, dong, hover, tab, rec, onPersona, onDong }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const tiles = useRef<L.TileLayer | null>(null);
  const layers = useRef<{ dongs?: L.GeoJSON; people?: L.LayerGroup; links?: L.LayerGroup }>({});
  const anchorRef = useRef(new Map<string, L.LatLng>());
  const cb = useRef({ onPersona, onDong }); cb.current = { onPersona, onDong };

  useEffect(() => {
    if (!box.current || map.current) return;
    const m = L.map(box.current, { zoomControl: false, attributionControl: true, zoomSnap: 0.25 }).setView([37.5, 127.06], 13);
    tiles.current = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(m);
    L.control.zoom({ position: 'bottomright' }).addTo(m);
    map.current = m;
    return () => { m.remove(); map.current = null; };
  }, []);

  useEffect(() => {
    const m = map.current, t = tiles.current; if (!m || !t) return;
    if (settings.basemap && !m.hasLayer(t)) t.addTo(m);
    if (!settings.basemap && m.hasLayer(t)) t.remove();
  }, [settings.basemap]);

  // 목록에서 마우스를 올린 동을 지도에서 강조(목록 ↔ 지도 연동)
  useEffect(() => {
    const geo = layers.current.dongs; if (!geo) return;
    geo.eachLayer(l => {
      const name = dongOf((l as L.Polygon & { feature?: GeoJSON.Feature }).feature?.properties?.adm_nm ?? '');
      geo.resetStyle(l as L.Path);
      if (hover && name === hover) { (l as L.Path).setStyle({ color: '#216be8', weight: 3 }); (l as L.Path).bringToFront(); }
    });
  }, [hover]);

  // 동 색칠 + 동 배지 + 대표 페르소나 핀
  useEffect(() => {
    const m = map.current; if (!m) return;
    layers.current.dongs?.remove(); layers.current.people?.remove();
    const R = agent.regions[region];
    const groups = new Map(R.dongs.map(d => [d.dong, d]));
    const focus = dong ?? persona?.dong;
    const geo = L.geoJSON(R.geojson, {
      style: f => {
        const name = dongOf(f?.properties?.adm_nm ?? ''), g = groups.get(name), on = name === focus;
        if (rec) {  // 정책 추천: 혜택 받는 동을 페르소나 수만큼 진하게
          const n = rec.dongs[name] ?? 0, top = Math.max(1, ...Object.values(rec.dongs));
          return { color: n ? '#216be8' : '#9aabbf', weight: n ? 1.6 : 1, fillColor: '#216be8', fillOpacity: n ? 0.12 + 0.5 * n / top : 0.04 };
        }
        return { color: on ? '#216be8' : '#7d93ad', weight: on ? 2.5 : 1, fillColor: on ? '#216be8' : g ? FILL[g.level] : '#ffffff', fillOpacity: on ? 0.18 : g ? 0.75 : 0.5 };
      },
      onEachFeature: (f, layer) => {
        const name = dongOf(f.properties?.adm_nm ?? '');
        if (groups.has(name)) layer.on('click', () => cb.current.onDong(name));
        else layer.bindTooltip(`${name} · 두드러진 집단이 없어요`, { sticky: true, direction: 'top', opacity: 0.95 });
      },
    });
    if (settings.boundaries) geo.addTo(m);
    layers.current.dongs = geo;
    anchorRef.current = anchors(agent, region);
    const people = L.layerGroup().addTo(m);
    // 동별 탭에서는 동 배지만, 대표 사례 탭에서는 대표 핀만 보여서 겹치지 않게 함
    const showDongs = !rec && (tab !== 'rep' || persona?.kind === 'dong');  // 정책 탭에서 추천을 고르기 전에도 동 배지를 보여 줌
    if (rec) for (const g of R.dongs) {
      const n = rec.dongs[g.dong]; if (!n || !g.location) continue;
      const html = `<span class="dong-badge tone-rec"><b class="num">${n}</b><span>${esc(g.dong)}</span></span>`;
      L.marker([g.location.lat, g.location.lng], { icon: L.divIcon({ html, className: 'pin-wrap', iconSize: [0, 0] }), interactive: false }).addTo(people);
    }
    for (const g of showDongs ? R.dongs : []) {
      if (!g.location || (persona?.kind === 'dong' && persona.dong === g.dong)) continue;
      const html = `<button class="dong-badge lv-${g.level}${g.dong === dong ? ' is-active' : ''}" aria-label="${esc(`${g.dong} 페르소나 ${g.personas.length}명 보기`)}"><b class="num">${g.personas.length}</b><span>${esc(g.dong)}</span></button>`;
      L.marker([g.location.lat, g.location.lng], { icon: L.divIcon({ html, className: 'pin-wrap', iconSize: [0, 0] }), zIndexOffset: 300 })
        .on('click', () => cb.current.onDong(g.dong)).addTo(people);
    }
    for (const id of R.personas) {
      if ((showDongs || rec || tab === 'policy') && persona?.id !== id) continue;
      const p = agent.personas.find(x => x.id === id)!;
      const html = `<button class="pin lv-${p.level}${persona?.id === p.id ? ' is-active' : ''}" aria-label="${esc(`${p.id} ${p.title}`)}">
        <span class="pin-code">${short(p)}</span><span class="pin-text"><b>${esc(p.title)}</b><small>대표 사례 · ${esc(p.dong ?? `${region} 전체 경향`)}</small></span></button>`;
      L.marker(anchorRef.current.get(id)!, { icon: L.divIcon({ html, className: 'pin-wrap', iconSize: [0, 0] }), zIndexOffset: persona?.id === id ? 900 : 500 })
        .on('click', () => cb.current.onPersona(id)).addTo(people);
    }
    // 동별 페르소나를 골랐으면 그 동 위에 그 사람 핀을 보여 줌
    if (persona?.kind === 'dong' && persona.location) {
      const html = `<button class="pin lv-${persona.level} is-active"><span class="pin-code">${short(persona)}</span><span class="pin-text"><b>${esc(persona.title)}</b><small>${esc(persona.dong ?? '')}</small></span></button>`;
      L.marker([persona.location.lat, persona.location.lng], { icon: L.divIcon({ html, className: 'pin-wrap', iconSize: [0, 0] }), zIndexOffset: 1000 }).addTo(people);
    }
    layers.current.people = people;
    if (rec && !persona) {  // 정책 추천: 혜택 받는 동이 분석 창을 피해 보이게
      const hits = geo.getLayers().filter(l => rec.dongs[dongOf((l as L.Polygon & { feature?: GeoJSON.Feature }).feature?.properties?.adm_nm ?? '')]) as L.Polygon[];
      const view = hits.length ? hits.reduce((b, l) => b.extend(l.getBounds()), L.latLngBounds(hits[0].getBounds().getSouthWest(), hits[0].getBounds().getNorthEast())) : geo.getBounds();
      m.flyToBounds(view, { ...pad(true), maxZoom: 14, duration: 0.5 });
    } else if (!persona && !dong) {  // 첫 화면: 해당 동 또는 지역 전체
      // 동별 탭은 페르소나가 있는 동이 꽉 차게, 대표 사례 탭은 지역 전체
      const hits = geo.getLayers().filter(l => groups.has(dongOf((l as L.Polygon & { feature?: GeoJSON.Feature }).feature?.properties?.adm_nm ?? ''))) as L.Polygon[];
      const view = tab !== 'rep' && hits.length ? hits.reduce((b, l) => b.extend(l.getBounds()), L.latLngBounds(hits[0].getBounds().getSouthWest(), hits[0].getBounds().getNorthEast())) : geo.getBounds();
      m.fitBounds(view, { ...pad(false), maxZoom: 14 });
    }
  }, [agent, region, persona, dong, tab, rec, settings.boundaries]);

  // 동을 고르면 그 동으로 이동
  useEffect(() => {
    const m = map.current; if (!m || !dong || persona) return;
    const hit = layers.current.dongs?.getLayers().find(l => dongOf((l as L.Polygon & { feature?: GeoJSON.Feature }).feature?.properties?.adm_nm ?? '') === dong) as L.Polygon | undefined;
    if (hit) m.flyToBounds(hit.getBounds(), { ...pad(false), maxZoom: 15, duration: 0.6 });
  }, [dong, persona]);

  // 선택한 페르소나: 추천 장소 번호 핀, 못 가는 장소, 연결선
  useEffect(() => {
    const m = map.current; if (!m) return;
    layers.current.links?.remove();
    if (!persona || persona.region !== region) return;
    const from = anchorRef.current.get(persona.id);
    if (!from) return;
    const field = persona.fields.find(f => f.function === fn);
    const links = L.layerGroup().addTo(m);
    const pts: L.LatLng[] = [from];
    for (const r of field?.programs ?? []) for (const s of r.sites) {
      const to = L.latLng(s.lat, s.lng); pts.push(to);
      if (settings.lines) L.polyline([from, to], { color: r.fits ? '#00765e' : '#7a8899', weight: 2, dashArray: '4 6', opacity: 0.8, interactive: false }).addTo(links);
      L.marker(to, { icon: L.divIcon({ html: `<div class="site ${r.fits ? 'site-fit' : ''}"><span class="num">${r.rank}</span></div>`, className: 'site-wrap', iconSize: [30, 30], iconAnchor: [15, 15] }) })
        .bindTooltip(`<b>${r.rank}. ${esc(r.name)}</b><br>${esc(s.place)}${s.outside ? ' · 지역 밖에 있어요' : ''}`, { direction: 'top', offset: [0, -14] })
        .addTo(links);
    }
    // 근처에 있지만 이 사람은 조건 때문에 못 가는 곳
    for (const b of field?.blocked ?? []) for (const s of b.sites) {
      L.marker([s.lat, s.lng], { icon: L.divIcon({ html: `<div class="site site-no">${NO_ICON}</div>`, className: 'site-wrap', iconSize: [24, 24], iconAnchor: [12, 12] }), zIndexOffset: -100 })
        .bindTooltip(`<b>${esc(b.name)}</b><br>${esc(b.reasons.join('·'))} 조건이 맞지 않아요`, { direction: 'top', offset: [0, -10] }).addTo(links);
    }
    layers.current.links = links;
    const view = L.latLngBounds(pts);
    const area = layers.current.dongs?.getBounds();
    if (persona.kind === 'rep' && area) view.extend(area);  // 대표 사례는 지역 전체, 동별은 그 동 주변
    if (pts.length === 1 && persona.kind === 'dong') {
      // 장소가 없으면 그 동을 화면 가운데(창을 뺀 영역)에 둠
      const hit = layers.current.dongs?.getLayers().find(l => dongOf((l as L.Polygon & { feature?: GeoJSON.Feature }).feature?.properties?.adm_nm ?? '') === persona.dong) as L.Polygon | undefined;
      if (hit) { m.flyToBounds(hit.getBounds(), { ...pad(panelOpen), maxZoom: 15, duration: 0.6 }); return; }
    }
    m.flyToBounds(view, { ...pad(panelOpen), maxZoom: 15, duration: 0.6 });
  }, [persona, fn, region, settings.lines, panelOpen]);

  return <div ref={box} className="agent-map" role="application" aria-label={`${region} 지도`} />;
}
