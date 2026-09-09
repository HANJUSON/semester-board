/* 손으로 만든 상황판 HTML → profiles/*.json
 *
 * 이 도구를 만들기 전에 쓰던 단일 파일 상황판을 프로필로 들여온다.
 * JS 리터럴을 정규식으로 파싱하지 않고 Node 로 그대로 평가해 손실을 없앤다.
 * 블록은 줄 번호가 아니라 선언 패턴으로 찾는다 — 원본이 수정돼도 따라간다.
 *
 *   node tools/import_dashboard.js <dashboard.html> <출력.json> [프로필ID]
 */
const fs = require('fs');

const [src, dst, pid = 'imported'] = process.argv.slice(2);
if (!src || !dst) { console.error('사용법: node tools/import_dashboard.js <입력.html> <출력.json> [id]'); process.exit(1); }
const L = fs.readFileSync(src, 'utf8').split('\n');

const find = (re, from = 0) => {
  for (let i = from; i < L.length; i++) if (re.test(L[i])) return i;
  throw new Error('원본에서 찾지 못했습니다: ' + re);
};
const close = (a) => {
  for (let i = a + 1; i < L.length; i++) if (/^[\]}];$/.test(L[i].trimEnd())) return i;
  throw new Error('블록의 끝을 찾지 못했습니다 (줄 ' + (a + 1) + ')');
};
const block = (startRe, endRe) => {
  const a = find(startRe);
  const b = endRe ? find(endRe, a + 1) - 1 : close(a);
  return L.slice(a, b + 1).join('\n');
};

/* W1 은 원본에서 읽고, weekEnd 는 주차를 그대로 보존하도록 표식을 돌려준다 */
const w1line = L[find(/^var W1\s*=/)];
const m = w1line.match(/new Date\((\d+),(\d+),(\d+)\)/);
if (!m) throw new Error('W1 을 읽지 못했습니다: ' + w1line);
const W1 = new Date(+m[1], +m[2], +m[3]);

const shim = `
  var W1 = new Date(${+m[1]},${+m[2]},${+m[3]});
  function weekStart(n){ var d=new Date(W1); d.setDate(d.getDate()+(n-1)*7); return d; }
  function weekEnd(n){ return {__week:n}; }
`;
const G = new Function([shim,
  block(/^var C=\{/, /^T\.forEach\(/),
  block(/^var P=\[/),
  block(/^var CRS=\{/),
  block(/^var CMAP=\[/),
  block(/^var CTERM=\[/),
  'return {C:C,CORDER:CORDER,LMS:LMS,CV:CV,WK:WK,LOCAL:LOCAL,PROJ:PROJ,T:T,P:P,CRS:CRS,CMAP:CMAP,CTERM:CTERM};'
].join('\n'))();

const ymd = d => d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') +
                 '-' + String(d.getDate()).padStart(2, '0');

function normTask(t) {
  const o = { title: t.t, kind: t.kind };
  if (t.w != null) o.week = t.w;
  if (t.date instanceof Date) o.date = ymd(t.date);
  if (t.pts) o.pts = t.pts;
  if (t.note) o.note = t.note;
  if (t.est) o.est = true;
  if (t.tbd) o.tbd = true;
  return o;
}
function normMs(x) {
  const o = { n: x.n, p: x.p };
  if (x.d instanceof Date) o.date = ymd(x.d);
  else if (x.d && x.d.__week != null) o.week = x.d.__week;
  return o;
}

const courses = {};
for (const k of G.CORDER) {
  const c = G.C[k], crs = G.CRS[k] || {}, pj = G.PROJ[k];
  courses[k] = {
    name: c.n, short: c.s, code: c.code, prof: c.prof, time: c.time, book: c.book, note: c.note,
    grading: (crs.parts || []).map(p => ({ label: p[0], pct: p[1], kind: p[2] })),
    materials: (crs.mat || []).map(x => ({ have: !!x[0], text: x[1] })),
    project: pj ? { title: pj.t, weight: pj.w, minor: !!pj.minor, aim: pj.aim,
                    out: pj.out, idea: pj.idea, check: pj.ck } : null,
    weeks: (G.WK[k] || []).map(w => {
      const o = { w: w.w, t: w.t, q: w.q || '', src: w.src, pts: w.pts };
      if (w.tag) o.tag = w.tag;
      if (w.range) o.range = w.range;
      if (w.emph) o.emph = w.emph;
      return o;
    }),
    local: G.LOCAL[k] || {},
    tasks: G.T.filter(t => t.c === k).map(normTask)
  };
}

const profile = {
  schema: 1,
  id: pid,
  semester: { label: '가져온 학기', week1Monday: ymd(W1), weeks: 16,
              examWeeks: { 8: '중간', 16: '기말' } },
  school: { id: 'ku', canvas: G.CV },
  courseOrder: G.CORDER,
  courses,
  highlights: G.P.map(p => ({ course: p.c, title: p.t, weight: p.w, minor: !!p.minor,
                              of: p.of, d: p.d, milestones: (p.ms || []).map(normMs) })),
  concepts: G.CMAP,
  terms: G.CTERM
};

fs.writeFileSync(dst, JSON.stringify(profile, null, 1), 'utf8');
const nw = Object.values(courses).reduce((a, c) => a + c.weeks.length, 0);
const nt = Object.values(courses).reduce((a, c) => a + c.tasks.length, 0);
console.log(`과목 ${G.CORDER.length} · 주차카드 ${nw} · 마감 ${nt} · 개념 ${profile.concepts.length}`);
console.log(`→ ${dst} (${(fs.statSync(dst).size / 1024).toFixed(1)} KB) · 1주차 월요일 ${ymd(W1)}`);
