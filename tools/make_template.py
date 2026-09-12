#!/usr/bin/env python3
"""dashboard.html(개인 상황판) → 데이터가 빠진 렌더러 템플릿.

한 번만 돌리는 출처 기록용 스크립트다. 원본 상황판에서 개인 데이터와
학교 종속 상수를 걷어내고, 빌드 시 PROFILE / LMS 두 블록만 주입하면
같은 화면이 나오도록 바꾼다.

    python3 tools/make_template.py <원본 dashboard.html> <출력 template.html>
"""
import os
import re
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()
L = s.split("\n")


def _find(pat, start=0):
    """정규식에 맞는 첫 줄의 0-indexed 위치. 없으면 죽는다."""
    rx = re.compile(pat)
    for i in range(start, len(L)):
        if rx.search(L[i]):
            return i
    raise SystemExit(f"원본에서 찾지 못했습니다: {pat}")


def _close(start):
    """블록 시작 줄에서 최상위 종료(`];` 또는 `};`)를 찾는다."""
    for i in range(start + 1, len(L)):
        if L[i].rstrip() in ("];", "};"):
            return i
    raise SystemExit(f"블록의 끝을 찾지 못했습니다 (줄 {start + 1})")


def block(start_pat, end_pat=None):
    """(시작, 끝) 0-indexed 포함 범위. 원본이 바뀌어도 따라간다."""
    a = _find(start_pat)
    b = _find(end_pat, a + 1) - 1 if end_pat else _close(a)
    return a, b


def cut(rng, new):
    """block() 이 준 범위를 new 로 바꾼다 (뒤에서 앞으로 호출할 것)."""
    global L
    a, b = rng
    L = L[:a] + ([new] if new is not None else []) + L[b + 1:]


def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (s.count(old), old[:70])
    s = s.replace(old, new, n)


# 범위를 먼저 전부 계산한다 — 하나를 자르면 뒤의 줄 번호가 밀리기 때문이다.
_r0 = block(r"^var CTERM=\[")
_r1 = block(r"^var CMAP=\[")
_r2 = block(r"^var CRS={")
_r3 = block(r"^var P=\[")
_r4 = block(r"^var C={", r"^T\.forEach\(")
_r5 = block(r"^/\* ===== \ud559\uc0ac \uc8fc\ucc28", r"^function weekStart\(")

# ── 1) 줄 범위 치환: 뒤에서 앞으로 ────────────────────────────────
cut(_r0, "var CTERM = PROFILE.terms || [];")
cut(_r1, "var CMAP = PROFILE.concepts || [];")
cut(_r2, "/* CRS 는 위 CORDER 루프에서 PROFILE.courses[].grading/materials 로 채운다 */")
cut(_r3, """var P=(PROFILE.highlights||[]).map(function(p){
  return {c:p.course,t:p.title,w:p.weight,minor:!!p.minor,of:p.of,d:p.d,
          ms:(p.milestones||[]).map(function(m){
            return {d:(m.date?ymdParse(m.date):weekEnd(m.week)),n:m.n,p:m.p};
          })};
});""")
cut(_r4, """var CV=(PROFILE.school&&PROFILE.school.canvas)||'';
var C={},CORDER=(PROFILE.courseOrder||[]).slice(),WK={},LOCAL={},PROJ={},CRS={},T=[];
CORDER.forEach(function(k){
  var c=PROFILE.courses[k]; if(!c) return;
  C[k]={n:c.name,s:c.short,code:c.code,prof:c.prof,time:c.time,book:c.book,
        note:c.note,board:c.board};
  WK[k]=c.weeks||[];
  LOCAL[k]=c.local||{};
  if(c.project){
    var j=c.project;
    PROJ[k]={t:j.title,w:j.weight,minor:!!j.minor,aim:j.aim,out:j.out,idea:j.idea,ck:j.check};
  }
  CRS[k]={parts:(c.grading||[]).map(function(g){ return [g.label,g.pct,g.kind]; }),
          mat:(c.materials||[]).map(function(m){ return [m.have?1:0,m.text]; })};
  (c.tasks||[]).forEach(function(t){
    var o={c:k,t:t.title,kind:t.kind,w:(t.week==null?null:t.week)};
    if(t.date) o.date=ymdParse(t.date);
    if(t.pts)  o.pts=t.pts;
    if(t.note) o.note=t.note;
    if(t.est)  o.est=true;
    if(t.tbd)  o.tbd=true;
    T.push(o);
  });
});

/* ===== LMS 확정 마감 =====
   프로필의 tasks 는 강의계획서의 주차만 보고 추정한 것이라 실제와 어긋난다.
   실제로 내야 하는 것은 LMS 에 제출란이 열린 것뿐이므로 그쪽을 확정(real)으로
   두고, 추정은 참고로 내린다. 확정이 생긴 과목은 추정을 버린다. */
function dayOf(d){ var x=new Date(d); x.setHours(0,0,0,0); return x; }
function hhmm(d){ var p=function(n){return n<10?'0'+n:''+n}; return p(d.getHours())+':'+p(d.getMinutes()); }
function asgKind(a){
  var n=a.n||'';
  if(a.st==='online_quiz') return '퀴즈';
  if(a.st==='on_paper' || /midterm|final exam|중간|기말/i.test(n)) return '시험';
  if(/presentation|발표/i.test(n)) return '발표';
  if(/project|proposal|프로젝트|제안/i.test(n)) return '프로젝트';
  return '과제';
}
var ANOTE=PROFILE.assignmentNotes||{};
var SUPERSEDED=PROFILE.supersededEstimates||{};   /* {과목키:true | 과목키:['퀴즈',…]} */
var EST=T; T=[];
(LMS.asg||[]).forEach(function(a){
  if(!a.due) return;                       /* 마감이 없으면 제출 대상이 아니다 */
  var at=new Date(a.due), day=dayOf(at);
  T.push({id:'a'+a.i,c:a.c,t:a.n,kind:asgKind(a),real:true,at:at,date:day,
          w:Math.floor((day-W1)/86400000/7)+1,
          pts:(a.pts!=null?a.pts+'점':''),url:a.url,sub:a.sub,state:a.state,lock:a.lock,
          note:ANOTE[a.i]||''});
});
EST.forEach(function(x){
  var sup=SUPERSEDED[x.c];
  if(sup===true) return;
  if(sup && sup.indexOf(x.kind)>=0) return;
  T.push(x);
});
function realTasks(w){
  return T.filter(function(x){ return x.real && (w?x.w===w:true); })
          .sort(function(a,b){ return a.at-b.at; });
}
function nextReal(from){
  return T.filter(function(x){ return x.real && x.date>=from; })
          .sort(function(a,b){ return a.at-b.at; })[0] || null;
}

/* LMS 링크 헬퍼 — 데이터가 아니라 로직이라 그대로 남긴다 */
function courseId(c){ return LMS.courses[c] ? LMS.courses[c].id : null; }
function modURL(c,w){
  var id=courseId(c); if(!id) return null;
  var m=LMS.mods[c] && LMS.mods[c][w];
  return m ? CV+'/courses/'+id+'/modules#module_'+m : CV+'/courses/'+id+'/modules';
}""")

# W1 · 주차 수 · 시험 주차를 프로필에서 끌어온다
cut(_r5, """/* ===== 학사 주차: PROFILE.semester 에서 온다 ===== */
function ymdParse(v){ var p=String(v).split('-'); return new Date(+p[0],+p[1]-1,+p[2]); }
var SEM=PROFILE.semester||{}, NW=SEM.weeks||16;
var EXAMW=SEM.examWeeks||{};
var SBKEY='sb.'+(PROFILE.id||'default')+'.';
var W1=ymdParse(SEM.week1Monday);""")

s = "\n".join(L)

# ── 2) 데이터 주입 지점 ───────────────────────────────────────────
rep('(function(){\n"use strict";\n', """(function(){
"use strict";

/* ===== 빌드 시 주입되는 데이터 =====
   semester-board build 가 아래 두 블록을 통째로 갈아 끼운다.
   PROFILE = 사람이 쓰거나 LLM 이 만든 학기 내용, LMS = API 로 긁어온 사실. */
var PROFILE = /*<<PROFILE>>*/{"id":"sample","semester":{"label":"샘플 학기","week1Monday":"2026-03-02","weeks":16},"school":{},"courseOrder":[],"courses":{},"highlights":[],"concepts":[],"terms":[]}/*<</PROFILE>>*/;
var LMS = /*<<LMS>>*/{"courses":{},"mods":{},"vids":[],"att":[],"files":[],"asg":[],"done":[],"status":{},"asof":""}/*<</LMS>>*/;

""")

# ── 3) 남은 하드코딩 걷어내기 ────────────────────────────────────
rep("return Math.min(16,Math.max(1,n));", "return Math.min(NW,Math.max(1,n));")
rep("<small>/ 16\uc8fc</small>", "<small>/ '+NW+'\uc8fc</small>")
rep("for(var i=1;i<=16;i++){\n    var exam=(i===8||i===16);",
    "for(var i=1;i<=NW;i++){\n    var exam=!!EXAMW[i];")
rep('if(exam){ h+=\'<div class="ex">\'+(i===8?\'\uc911\uac04\':\'\uae30\ub9d0\')+\'</div>\'; }',
    'if(exam){ h+=\'<div class="ex">\'+EXAMW[i]+\'</div>\'; }')
rep("\u300c\uc804\uccb4 16\uc8fc\u300d", "\u300c\uc804\uccb4 '+NW+'\uc8fc\u300d")
rep(">\uc804\uccb4 16\uc8fc</button>", ">\uc804\uccb4 '+NW+'\uc8fc</button>")
rep('<span class="idx">16W</span>\ud559\uae30 \uc804\uccb4 \ud750\ub984</h2><span class="hint">09.01 \u2013 12.21</span>',
    '<span class="idx">\'+NW+\'W</span>\ud559\uae30 \uc804\uccb4 \ud750\ub984</h2><span class="hint">\'+fmt2(weekStart(1))+\' \u2013 \'+fmt2(weekEnd(NW))+\'</span>')
rep('<span class="idx">16W</span>\uc8fc\ucc28\ubcc4 \ud559\uc2b5 \uc9c0\ub3c4',
    '<span class="idx">\'+NW+\'W</span>\uc8fc\ucc28\ubcc4 \ud559\uc2b5 \uc9c0\ub3c4')
# 값이 없는 과목 정보 항목은 라벨째 빼둔다 (학수번호·수업이 비면 라벨만 떠 있었다)
rep("""     '<div class="cfacts">'+
     '<span><b>\ud559\uc218\ubc88\ud638</b>'+esc(co.code)+'</span>'+
     (co.prof!=='\u2014'?'<span><b>\ub2f4\ub2f9</b>'+esc(co.prof)+'</span>':'')+
     '<span><b>\uc218\uc5c5</b>'+esc(co.time)+'</span>'+
     '<span><b>\uad50\uc7ac</b>'+esc(co.book)+'</span></div>'+""",
    """     '<div class="cfacts">'+
     [['\ud559\uc218\ubc88\ud638',co.code],['\ub2f4\ub2f9',co.prof],
      ['\uc218\uc5c5',co.time],['\uad50\uc7ac',co.book]]
       .filter(function(f){ return f[1] && f[1]!=='\u2014'; })
       .map(function(f){ return '<span><b>'+f[0]+'</b>'+esc(f[1])+'</span>'; }).join('')+
     '</div>'+""")

# 프로젝트 산출물·점검 항목만 esc() 로 나가 태그가 글자로 보였다. aim·idea 와 통일한다.
rep("""(pr.out||[]).map(function(s){return '<li>'+esc(s)+'</li>';})""",
    """(pr.out||[]).map(function(s){return '<li>'+s+'</li>';})""")
rep("""(pr.ck||[]).map(function(s){return '<li>'+esc(s)+'</li>';})""",
    """(pr.ck||[]).map(function(s){return '<li>'+s+'</li>';})""")

# 내 PC 자료는 절대경로가 그대로 찍혀 칩이 화면을 넘겼다. 끝 두 조각만 보이고
# 전체 경로는 툴팁으로 넘긴다.
rep("""    h+='<span class="matlink local"><span class="ty">\ub0b4 PC</span><span class="nm">'+esc(p)+'</span></span>';""",
    """    var seg=String(p).split(/[\\\\/]/).filter(Boolean), shortp=seg.slice(-2).join('/');
    h+='<span class="matlink local" title="'+esc(p)+'"><span class="ty">\ub0b4 PC</span>'+
       '<span class="nm">'+esc(shortp)+'</span></span>';""")

rep("if(homeWeek<16)", "if(homeWeek<NW)")
rep("var vw=(jumpWeek>=1 && jumpWeek<=16)?jumpWeek:cw;", "var vw=(jumpWeek>=1 && jumpWeek<=NW)?jumpWeek:cw;")
rep("for(w=1;w<=16;w++) h+=", "for(w=1;w<=NW;w++) h+=")
rep("for(w=1;w<=16;w++){", "for(w=1;w<=NW;w++){")

# 학기 병목 안내는 프로필에 있을 때만 띄운다
rep("""  h+='<section><div class="shead"><h2><span class="idx">JAM</span>15·16주차 병목</h2></div>'+
     '<div class="notice"><b>12월 둘째 주에 발표가 겹친다.</b> 빅데이터 발표(12/08) · 딥러닝응용 Term Project 발표 · 데이터베이스 프로젝트 발표 · 소프트웨어응용 제안 발표가 같은 주에 몰리고, '+
     '바로 다음 주에는 기말고사와 빅데이터 보고서(12/16), 거대언어모델 결과보고서가 이어진다. <b>11월 중순부터 발표 자료를 만들어 두는 것이 유일한 해법이다.</b></div></section>';""",
    """  if(SEM.jam){
    h+='<section><div class="shead"><h2><span class="idx">JAM</span>'+esc(SEM.jam.title||'병목 구간')+'</h2></div>'+
       '<div class="notice">'+SEM.jam.body+'</div></section>';
  }""")

# localStorage 키를 프로필별로 분리
for k in ("state", "done", "seen"):
    s = s.replace("'ku26f.%s'" % k, "SBKEY+'%s'" % k)
assert "ku26f" not in s, "localStorage 키가 남았다"

# 사이드바 각주의 학교 링크
rep("""    강의자료·마감은 <a href="https://canvas.korea.ac.kr/login" target="_blank" rel="noopener">KU LMS</a>에서 가져왔습니다.
    체크와 메모는 자동 저장됩니다.""",
    """    강의자료·마감은 <a id="lmslink" href="#" target="_blank" rel="noopener">LMS</a>에서 가져왔습니다.
    체크와 메모는 자동 저장됩니다.""")
rep("var navOpen=true;", """(function(){
  var a=document.getElementById('lmslink');
  if(a && CV){ a.href=CV+'/login'; a.textContent=(PROFILE.school&&PROFILE.school.short)||'LMS'; }
})();
var navOpen=true;""")

open(dst, "w", encoding="utf-8").write(s)

fn = lambda t: set(re.findall(r"^\s*function\s+(\w+)", t, re.M))
lost = fn(open(src, encoding="utf-8").read()) - fn(s) - {"add"}
assert not lost, f"\ud15c\ud50c\ub9bf\uc5d0\uc11c \ud568\uc218\uac00 \uc0ac\ub77c\uc84c\uc2b5\ub2c8\ub2e4: {sorted(lost)}"

bad = [w for w in (os.environ.get("TEMPLATE_FORBID") or "").split(",") if w.strip()]
left = [w for w in bad if w in s]
print("템플릿 생성:", dst, f"({len(s)/1024:.1f} KB)")
print("개인·학교 종속 문자열 잔존:", left or "없음")
