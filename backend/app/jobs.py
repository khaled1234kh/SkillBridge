"""Real, recent, career-fitting job listings for students.

Aggregates live openings from multiple free, no-key job feeds and matches
them to a student's actual profile:

- **Sources**: Remotive (global remote) + RemoteOK (global remote/tech).
- **Relevance**: every job is scored against the student's skill names
  (a weighted keyword overlap) and their target role.
- **Experience fit**: the student's seniority is inferred from their skill
  levels (Beginner/Intermediate/Advanced) plus verified-skill depth; each job's
  seniority is inferred from its title. Senior roles are de-ranked (and, for a
  clear undergrad, filtered out entirely) so a student isn't shown "Senior"
  roles they aren't qualified for.
- **Country**: where a job listing carries a country/location tag, jobs in the
  student's own country get a relevance boost. Both feeds are remote-first, so
  country is a soft signal, not a hard filter.
- **Ranking**: results are sorted most-fitting → least-fitting, marked with a
  ``match_pct`` and a short ``match_reason`` the UI can show.

Results are cached in memory for a short TTL so a demo never hammers upstream.
When every feed is unreachable (offline demo / no network), a small curated
fallback list is served so the UI never looks broken — the caller is told
whether results are ``live`` or ``fallback``.
"""
import re
import threading
import time

import httpx

REMOTIVE_URL = "https://remotive.com/api/remote-jobs"
REMOTEOK_URL = "https://remoteok.com/api"
TTL_SECONDS = 15 * 60

_HEADERS = {"User-Agent": "SkillBridge/1.0 (career platform; student job matching)"}

_level_score = {"Beginner": 1, "Intermediate": 2, "Advanced": 3}
_level_to_want = {"Beginner": "entry", "Intermediate": "junior", "Advanced": "mid"}

_cache = {"at": 0.0, "key": "", "data": None}
_lock = threading.Lock()

# Curated offline stand-ins, aligned with the app's own seeded companies and
# catalog, so a no-network demo still shows believable, dated roles.
FALLBACK_JOBS = [
    {"title": "Junior AI Engineer", "company": "Northstar Labs",
     "url": "https://www.google.com/search?q=junior+AI+engineer+job", "date": "2026-08-28",
     "location": "Remote", "country": "United States",
     "tags": ["AI", "Python", "Machine Learning"], "seniority": "junior"},
    {"title": "Data Analyst (Entry)", "company": "Signal Works",
     "url": "https://www.google.com/search?q=data+analyst+job", "date": "2026-08-26",
     "location": "Remote", "country": "United States",
     "tags": ["SQL", "Data", "Analytics"], "seniority": "entry"},
    {"title": "Backend Engineer, AI Products", "company": "Northstar Labs",
     "url": "https://www.google.com/search?q=backend+engineer+AI+job", "date": "2026-08-24",
     "location": "Remote", "country": "United Kingdom",
     "tags": ["Python", "Docker", "APIs"], "seniority": "junior"},
    {"title": "Machine Learning Engineer", "company": "Signal Works",
     "url": "https://www.google.com/search?q=machine+learning+engineer+job", "date": "2026-08-20",
     "location": "Remote", "country": "India",
     "tags": ["Machine Learning", "Python"], "seniority": "mid"},
    {"title": "Junior Data Engineer", "company": "Northstar Labs",
     "url": "https://www.google.com/search?q=junior+data+engineer+job", "date": "2026-08-18",
     "location": "Remote", "country": "Canada",
     "tags": ["SQL", "Docker", "ETL"], "seniority": "junior"},
    {"title": "Software Developer (Graduate)", "company": "Signal Works",
     "url": "https://www.google.com/search?q=graduate+software+developer+job", "date": "2026-08-15",
     "location": "Remote", "country": "United States",
     "tags": ["Python", "Git", "SQL"], "seniority": "entry"},
]

# Seniority markers extracted from a job title.
_SENIORITY_PATTERNS = [
    (("senior", "staff", "principal", "lead", "sr", "sr.", "architect"), 3),
    (("mid", "mid-level", "intermediate"), 2),
    (("junior", "jr", "jr.", "entry", "graduate", "grad", "associate", "intern", "trainee"), 0),
]

# Country-name normalisation: common country names a job's location/tags might
# use, mapped to the canonical monthy names the app stores.
_COUNTRY_ALIASES = {
    "usa": "United States", "us": "United States", "united states": "United States",
    "uk": "United Kingdom", "england": "United Kingdom", "britain": "United Kingdom",
    "uae": "United Arab Emirates", "emirates": "United Arab Emirates",
    "ksa": "Saudi Arabia", "saudi": "Saudi Arabia",
    "canada": "Canada", "india": "India", "germany": "Germany", "egypt": "Egypt",
}


def _normalise_country(raw):
    if not raw:
        return ""
    low = re.sub(r"[^a-z ]", "", raw.lower()).strip()
    if low in _COUNTRY_ALIASES:
        return _COUNTRY_ALIASES[low]
    return low.title() if low else ""


def _job_seniority(title):
    """Return 0..3 seniority bucket for a job title (0 senior, 3 very senior)."""
    low = (title or "").lower()
    for words, rank in _SENIORITY_PATTERNS:
        if any(re.search(r"\b" + w.replace(".", r"\.") + r"\b", low) for w in words):
            return rank
    return 1  # unmarked -> treat as junior-to-mid


def _student_seniority(skill_levels):
    """Infer a student's career seniority from their skill levels."""
    if not skill_levels:
        return 0  # no skills -> treat as beginner / entry
    vals = [_level_score.get(l, 1) for l in skill_levels]
    avg = sum(vals) / len(vals)
    if avg >= 2.6:
        return 3  # mostly Advanced -> mid/strong
    if avg >= 2.0:
        return 2  # mostly Intermediate -> mid
    if avg >= 1.4:
        return 1  # mixed beginner/intermediate -> junior
    return 0  # mostly Beginner -> entry


_ROLE_FAMILIES = {
    # role family token -> synonyms/role-type words that mark a matching job title
    "engineer": ["engineer", "developer", "software", "programmer", "backend", "frontend", "fullstack", "full-stack"],
    "developer": ["developer", "engineer", "software", "programmer", "cod"],
    "data": ["data", "analyst", "scientist", "analytics", "bi "],
    "scientist": ["scientist", "research", "ml", "machine learning", "ai ", "deep learning"],
    "analyst": ["analyst", "data", "business intelligence", "bi "],
    "cloud": ["cloud", "devops", "aws", "azure", "gcp", "infrastructure"],
    "security": ["security", "cyber", "pentest", "appsec"],
    "design": ["design", "ux", "ui ", "product designer"],
    "marketing": ["marketing", "growth", "seo", "content"],
    "finance": ["finance", "accounting", "financial"],
    "product": ["product", "program"],
    "project": ["project", "program", "delivery"],
    "support": ["support", "helpdesk", "service desk", "it support"],
    "qa": ["qa", "quality", "test"],
    "backend": ["backend", "server-side", "api"],
    "frontend": ["frontend", "front-end", "web", "react", "javascript"],
}

_ROLE_FAMILY_HINTS = [
    "ai", "machine learning", "ml", "data", "software", "developer", "engineer",
    "cloud", "devops", "security", "analyst", "scientist", "fullstack", "backend",
    "frontend", "qa", "product", "design", "web",
]


def _role_family(role):
    """Return the family token(s) for a target role title, used to spot jobs in
    the same discipline even when specific skill keywords are absent."""
    low = (role or "").lower()
    for token, syns in _ROLE_FAMILIES.items():
        for s in syns:
            if s in (" " + low.replace("-", " ")) or s.rstrip() and s.rstrip(" ") in low:
                return token
    for hint in _ROLE_FAMILY_HINTS:
        if hint in low:
            return hint
    return ""


def _term_keywords(skills, role):
    """Keywords used to match a job against the student's profile: skill names
    plus the target-role title fragments."""
    words = []
    for s in skills:
        for part in re.split(r"[/&\s]+", s):
            if 2 <= len(part) <= 24:
                words.append(part.lower())
    if role:
        for part in re.split(r"[/&\s]+", role):
            if len(part) > 2:
                words.append(part.lower())
    return words


def _score_job(job, keywords, student_seniority, country, role_family=""):
    """Compute 0-100 fit score + a human reason for one job."""
    title = (job.get("title", "") or "")
    haystack = (f"{title} {' '.join(job.get('tags') or [])} "
                f"{job.get('location', '')}").lower()
    tlow = title.lower()

    hits = 0
    matched = []
    for kw in keywords:
        if kw and kw in haystack:
            hits += 1
            matched.append(kw)

    # Relevance (primary signal) — base 0-70 points.
    relevance = min(56, hits * 14)
    # Strong bonus when the job's own title indicates the student's discipline.
    family = role_family
    title_family_hit = False
    if family:
        syns = _ROLE_FAMILIES.get(family, [family])
        if any(s in (" " + tlow) or s and s in tlow for s in syns):
            title_family_hit = True
            relevance += 24
    if title_family_hit:
        relevance = min(70, relevance)
    # A few named skill hits on real tech stack words push a family match to the top.
    if title_family_hit and relevance >= 40:
        relevance = min(80, relevance + 6)

    # Experience-level fit — 20% of the score.
    job_sen = _job_seniority(title)
    if job_sen > student_seniority:
        exp = 0
    elif job_sen == student_seniority:
        exp = 20
    else:
        exp = 12

    # Country affinity — 10% of the score.
    job_country = _normalise_country(job.get("country") or job.get("location") or "")
    geo = 0
    if country and job_country:
        geo = 10 if job_country == country else 4

    score = max(0, min(100, int(round(relevance + exp + geo))))

    if job_sen > student_seniority:
        reason = "Labeled more senior than your current level — listed for context."
        if student_seniority == 0:
            reason = "This is a mid/senior role; not a fit for your experience yet."
    elif title_family_hit:
        reason = "Matches your target career."
        if relevance >= 60:
            reason = f"Strong match to your target career and skills ({', '.join(matched[:3])})."
        elif matched:
            reason = f"Matches '{family}' and uses {', '.join(matched[:3])}."
    elif relevance >= 40:
        reason = f"Strong match to your skills ({', '.join(matched[:3])})."
    elif relevance >= 20:
        reason = f"Uses skills you have ({', '.join(matched[:3])})."
    elif relevance > 0:
        reason = "Some skill overlap."
    else:
        reason = "Low overlap with your current skills."
    if country and geo >= 10:
        reason += " Located in your country."
    # Relevant = the job's title clearly matches the student's discipline, or it
    # carries at least a few of the student's actual skill keywords. A lone tag
    # hit is unreliable (noisy feeds), so a single hit alone is not enough.
    relevant = bool(title_family_hit) or hits >= 2
    return score, reason, relevant


def _merge(raw_jobs):
    """Normalise + dedupe raw listings from all feeds into one list."""
    merged = {}
    for j in raw_jobs:
        title = (j.get("title") or "").strip()
        company = (j.get("company") or j.get("company_name") or "Unknown company").strip()
        url = j.get("url") or j.get("link") or ""
        if not title or not url:
            continue
        tags = [t for t in (j.get("tags") or []) if isinstance(t, str) and t.strip()][:6]
        location = (j.get("location") or j.get("candidate_required_location") or "").strip()
        country = _normalise_country(j.get("country") or location)
        if not country:
            country = _normalise_country(" ".join(tags))
        date = j.get("date") or j.get("publication_date") or ""
        if isinstance(date, int):
            date = time.strftime("%Y-%m-%d", time.gmtime(date))
        key = (title + "|" + company).lower()
        if key not in merged:
            merged[key] = {"title": title, "company": company, "url": url,
                           "date": date, "location": location, "country": country,
                           "tags": tags, "source": j.get("source", "")}
    # newest first by date, best-effort
    return sorted(merged.values(),
                  key=lambda j: j["date"] or "", reverse=True)


def _fetch_remotive(n):
    jobs = []
    try:
        resp = httpx.get(REMOTIVE_URL, params={"limit": n},
                         headers=_HEADERS, timeout=12)
        resp.raise_for_status()
        for j in (resp.json().get("jobs") or [])[:n]:
            location = (j.get("candidate_required_location") or "").strip()
            tags = [t for t in (j.get("tags") or []) if isinstance(t, str) and t.strip()]
            jobs.append({"title": j.get("title"), "company": j.get("company_name"),
                         "url": j.get("url"), "date": j.get("publication_date"),
                         "location": location, "tags": tags, "source": "Remotive"})
    except Exception:
        pass
    return jobs


def _fetch_remoteok(n):
    jobs = []
    try:
        resp = httpx.get(REMOTEOK_URL, headers=_HEADERS, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            data = data.get("jobs", []) or []
        for j in (data or [])[:n]:
            tags = [t for t in (j.get("tags") or []) if isinstance(t, str) and t.strip()]
            jobs.append({"title": j.get("position"), "company": j.get("company"),
                         "url": j.get("url"), "date": j.get("date"),
                         "location": j.get("location"), "tags": tags,
                         "source": "RemoteOK"})
    except Exception:
        pass
    return jobs


def _fetch_all(limit_each):
    jobs = _fetch_remotive(max(limit_each, 40))
    jobs += _fetch_remoteok(max(limit_each, 40))
    return jobs


def _seniority_label(job):
    i = _job_seniority(job.get("title"))
    return ["Entry", "Junior", "Mid", "Senior"][min(3, i)]


def _apply(jobs, keywords, student_seniority, country, role_family=""):
    """Score + rank jobs most-fitting → least. Clearly-senior roles are
    de-ranked; a beginner student never has senior roles ranked ahead of
    fitting ones. Jobs with zero relevance to the student's profile are
    dropped so unrelated listings never fill the list."""
    scored = []
    for j in jobs:
        score, reason, relevant = _score_job(j, keywords, student_seniority, country, role_family)
        if not relevant:
            continue
        if student_seniority == 0 and _job_seniority(j.get("title")) > 1:
            score = min(score, 15)
        scored.append({**j, "match_pct": score, "match_reason": reason,
                       "seniority": _seniority_label(j)})
    scored.sort(key=lambda j: -j["match_pct"])
    return scored


def recent_jobs(skills=(), role="", country="", limit=10):
    """Return ``{source, jobs}`` ranked most → least fitting for the profile.

    ``skills`` is a list of ``(name, level)`` pairs (the student's own skills
    and their self-reported/verified level). ``role`` is the display title of
    their target career. ``country`` is their chosen country.
    """
    skill_levels = [s[1] for s in skills if isinstance(s, (tuple, list)) and len(s) == 2]
    skill_names = [s[0] if isinstance(s, (tuple, list)) else s for s in skills]
    key = ("|".join(sorted(n.lower() for n in skill_names))
           + "|" + (role or "").lower() + "|" + (country or "").lower())
    now = time.time()
    with _lock:
        cached = _cache["data"] if (_cache["key"] == key and now - _cache["at"] < TTL_SECONDS) else None
    if cached:
        return cached

    keywords = _term_keywords(skill_names, role)
    role_family = _role_family(role)
    student_seniority = _student_seniority(skill_levels)

    raw = _fetch_all(limit * 3)
    merged = _merge(raw)
    live = bool(merged)
    jobs = merged or FALLBACK_JOBS
    ranked = _apply(jobs, keywords, student_seniority, country, role_family)
    data = {"source": "live" if live else "fallback", "jobs": ranked[:limit]}

    with _lock:
        _cache.update({"at": now, "key": key, "data": data})
    return data
