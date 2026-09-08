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


def cut(a, b, new):
    """1-indexed 줄 범위 [a,b]를 new 로 바꾼다 (뒤에서 앞으로 호출할 것)."""
    global L
    L = L[: a - 1] + ([new] if new is not None else []) + L[b:]


def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (s.count(old), old[:70])
    s = s.replace(old, new, n)


# ── 1) 줄 범위 치환: 뒤에서 앞으로 ────────────────────────────────
cut(1331, 1346, "var CTERM = PROFILE.terms || [];")
cut(1242, 1328, "var CMAP = PROFILE.concepts || [];")
cut(1124, 1139, "/* CRS 는 위 CORDER 루프에서 PROFILE.courses[].grading/materials 로 채운다 */")
cut(1093, 1120, """var P=(PROFILE.highlights||[]).map(function(p){
  return {c:p.course,t:p.title,w:p.weight,minor:!!p.minor,of:p.of,d:p.d,
          ms:(p.milestones||[]).map(function(m){
            return {d:(m.date?ymdParse(m.date):weekEnd(m.week)),n:m.n,p:m.p};
          })};
});""")
cut(546, 1084, """var CV=(PROFILE.school&&PROFILE.school.canvas)||'';
var C={},CORDER=(PROFILE.courseOrder||[]).slice(),WK={},LOCAL={},PROJ={},CRS={},T=[];
CORDER.forEach(function(k){
  var c=PROFILE.courses[k]; if(!c) return;
  C[k]={n:c.name,s:c.short,code:c.code,prof:c.prof,time:c.time,book:c.book,note:c.note};
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

/* LMS 링크 헬퍼 — 데이터가 아니라 로직이라 그대로 남긴다 */
function courseId(c){ return LMS.courses[c] ? LMS.courses[c].id : null; }
function modURL(c,w){
  var id=courseId(c); if(!id) return null;
  var m=LMS.mods[c] && LMS.mods[c][w];
  return m ? CV+'/courses/'+id+'/modules#module_'+m : CV+'/courses/'+id+'/modules';
}""")

# W1 · 주차 수 · 시험 주차를 프로필에서 끌어온다
cut(529, 530, """/* ===== 학사 주차: PROFILE.semester 에서 온다 ===== */
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
