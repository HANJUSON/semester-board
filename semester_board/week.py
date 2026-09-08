"""학사 주차 계산과 1주차 월요일 추론.

한국 대학 학기는 월~일 주 단위로 돌아간다. 상황판의 모든 주차 표시가
1주차 월요일(W1) 하나에 매달려 있어서, 여기가 하루만 어긋나도 화면 전체가
한 주씩 밀린다. 사람이 손으로 넣게 두지 않고 LMS 사실에서 역산한다.
"""
import datetime
from collections import Counter

MON = 0


def monday_of(d: datetime.date) -> datetime.date:
    return d - datetime.timedelta(days=d.weekday())


def week_start(w1: datetime.date, n: int) -> datetime.date:
    return w1 + datetime.timedelta(days=(n - 1) * 7)


def week_end(w1: datetime.date, n: int) -> datetime.date:
    return week_start(w1, n) + datetime.timedelta(days=6)


def week_of(w1: datetime.date, d: datetime.date, weeks: int = 16) -> int:
    n = (d - w1).days // 7 + 1
    return max(1, min(weeks, n))


def infer_week1(pairs) -> datetime.date | None:
    """(주차번호, 그 주에 속한 날짜) 쌍들에서 1주차 월요일을 역산한다.

    각 쌍은 W1 후보 하나를 만든다 — 날짜가 속한 주의 월요일에서
    (주차-1)주를 뺀 날. 사실이 서로 맞는다면 후보가 한 점에 모인다.
    가장 많이 나온 후보를 고르고, 표가 갈리면 None 을 돌려준다.
    """
    votes = Counter()
    for w, d in pairs:
        if not w or not d:
            continue
        votes[monday_of(d) - datetime.timedelta(days=(w - 1) * 7)] += 1
    if not votes:
        return None
    (best, n), = votes.most_common(1)
    if len(votes) > 1 and n == votes.most_common(2)[1][1]:
        return None          # 동점 — 사람이 정해야 한다
    return best


def parse_ymd(s: str) -> datetime.date:
    return datetime.date(*(int(x) for x in str(s)[:10].split("-")))


def ymd(d: datetime.date) -> str:
    return d.strftime("%Y-%m-%d")
