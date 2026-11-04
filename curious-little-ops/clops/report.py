"""Weekly KPI collection + rule-based decision candidates + markdown brief.

The scheduled Claude run calls collect() (fills this week's KPI row from whatever
APIs have credentials), then rules() (mechanical checks), then writes the human
brief with brief_markdown(). Claude adds judgment on top; this file is the floor,
not the ceiling.
"""
from __future__ import annotations

from pathlib import Path

from .config import MissingSecret, Secrets
from .http import ApiError
from .state import State, iso_week


def _try(fn, errors: list[str], label: str):
    try:
        return fn()
    except MissingSecret as e:
        errors.append(f"{label}: credentials missing ({', '.join(e.keys)})")
    except (ApiError, RuntimeError, OSError) as e:
        errors.append(f"{label}: {str(e)[:160]}")
    return None


def collect(state: State, secrets: Secrets, kdp_report: str | Path | None = None, week: str | None = None) -> list[str]:
    """Fill KPI row for `week` from APIs. Returns list of problems (never raises)."""
    errors: list[str] = []
    week = week or iso_week()

    def pin():
        from .pinterest import Pinterest

        a = Pinterest(secrets).analytics(days=7)
        state.record_kpi("pin_impressions", a["impressions"], "api", week)
        state.record_kpi("pin_outbound_clicks", a["outbound_clicks"], "api", week)
        state.record_kpi("pin_saves", a["saves"], "api", week)

    def ig():
        from .instagram import Instagram

        a = Instagram(secrets).account()
        state.record_kpi("ig_followers", a.get("followers_count"), "api", week)
        state.record_kpi("ig_posts", a.get("media_count"), "api", week)

    def yt():
        from .youtube import YouTube

        s = YouTube(secrets).channel_stats()
        state.record_kpi("yt_subscribers", s.get("subscribers"), "api", week)
        state.record_kpi("yt_total_views", s.get("views"), "api", week)

    def etsy():
        from .etsy import Etsy

        e = Etsy(secrets)
        s = e.sales_summary(days=7)
        state.record_kpi("etsy_orders", s["orders"], "api", week)
        state.record_kpi("etsy_revenue", s["revenue"], "api", week)
        state.record_kpi("etsy_reviews_total", len(e.reviews()), "api", week)
        state.kpi_row(week)["etsy_by_listing"] = s["by_listing"]
        if e.new_refresh_token:
            errors.append("etsy: refresh token rotated - update secrets.json etsy_refresh_token to: " + e.new_refresh_token)

    def kdp():
        from .kdp import summarize

        if kdp_report and Path(kdp_report).exists():
            s = summarize(kdp_report)
            state.record_kpi("kdp_units", s["units"], "report", week)
            state.record_kpi("kdp_royalty", s["royalty"], "report", week)
            state.kpi_row(week)["kdp_by_title"] = s["by_title"]

    _try(pin, errors, "pinterest")
    _try(ig, errors, "instagram")
    _try(yt, errors, "youtube")
    _try(etsy, errors, "etsy")
    _try(kdp, errors, "kdp")
    return errors


def _delta(cur: dict | None, prev: dict | None, key: str):
    if not cur or key not in cur:
        return None, None
    c = cur[key]
    p = prev.get(key) if prev else None
    return c, (None if p is None else c - p)


def rules(state: State) -> list[dict]:
    """Mechanical decision candidates. Each: {type, proposal, needs_approval, why}."""
    cur, prev = state.last_two_weeks()
    out: list[dict] = []
    if not cur:
        return out
    visits = cur.get("etsy_visits")
    orders = cur.get("etsy_orders")
    if visits is not None and orders is not None and visits >= 300 and orders == 0:
        out.append(
            dict(
                type="listing_review",
                proposal="Etsy: 300+ ziyaret, 0 sipariş. Odak ürünlerin ilk fotoğrafı ve fiyatı bu hafta değişmeli; en zayıf 2 listing için yeni mockup + video.",
                needs_approval=False,
                why=f"visits={visits}, orders={orders}",
            )
        )
    if visits and orders and visits >= 100:
        conv = orders / visits
        if conv < 0.01:
            out.append(dict(type="listing_review", proposal=f"Etsy dönüşüm %{conv*100:.2f} (hedef %1+). Fiyat/fotoğraf testi öner.", needs_approval=False, why=f"conv={conv:.4f}"))
    reviews = cur.get("etsy_reviews_total")
    if reviews is not None and reviews < 5:
        out.append(dict(type="reviews", proposal="Etsy yorum sayısı 5'in altında. Bu hafta her alıcıya teşekkür + yorum mesajı; 10 tanıdık alıcı kampanyası devam.", needs_approval=False, why=f"reviews={reviews}"))
    kdp_units = cur.get("kdp_units")
    spend = cur.get("ads_spend")
    ad_sales = cur.get("ads_sales")
    if spend and ad_sales is not None and spend >= 25:
        acos = (spend / ad_sales) if ad_sales else None
        if acos is None or acos > 1.0:
            out.append(dict(type="ad_budget", proposal=f"Amazon Ads: ${spend:.0f} harcama, ${ad_sales or 0:.0f} satış. Kampanyayı $3/gün'e düşür veya dönüşmeyen terimleri negatife al.", needs_approval=True, why="ACOS>100%"))
        elif acos < 0.5:
            out.append(dict(type="ad_budget", proposal=f"Amazon Ads ACOS %{acos*100:.0f}. Bütçeyi $5 -> $8/gün yükselt.", needs_approval=True, why="ACOS<50%"))
    clicks, dclicks = _delta(cur, prev, "pin_outbound_clicks")
    if clicks is not None and dclicks is not None and dclicks < 0 and prev and prev.get("pin_outbound_clicks", 0) > 20:
        out.append(dict(type="content", proposal="Pinterest outbound click düştü. Bu hafta pin sayısını 10 -> 15'e çıkar, en çok tıklanan 3 pini yeni görselle tekrar yayınla.", needs_approval=False, why=f"delta={dclicks}"))
    if state.queued_count() < 7:
        out.append(dict(type="content", proposal=f"İçerik kuyruğunda {state.queued_count()} öğe kaldı. Bu hafta en az 10 pin + 2 Reel kuyruğa eklenecek.", needs_approval=False, why="queue low"))
    return out


def brief_markdown(state: State, problems: list[str], candidates: list[dict]) -> str:
    cur, prev = state.last_two_weeks()
    lines = [f"# Curious Little - haftalık CEO özeti ({cur['week'] if cur else iso_week()})", ""]
    strat = state.data["strategy"]
    lines += [f"Faz: {strat.get('phase','-')} (bitiş {strat.get('phase_until','-')})", ""]
    lines.append("## KPI (bu hafta / geçen hafta)")
    keys = [
        ("etsy_visits", "Etsy ziyaret"), ("etsy_orders", "Etsy sipariş"), ("etsy_revenue", "Etsy gelir $"),
        ("etsy_reviews_total", "Etsy yorum (toplam)"), ("kdp_units", "KDP adet"), ("kdp_royalty", "KDP royalty $"),
        ("ads_spend", "Amazon Ads harcama $"), ("ads_sales", "Amazon Ads satış $"),
        ("pin_impressions", "Pinterest gösterim"), ("pin_outbound_clicks", "Pinterest dış tık"),
        ("ig_followers", "Instagram takipçi"), ("yt_subscribers", "YouTube abone"), ("yt_total_views", "YouTube toplam izlenme"),
    ]
    for k, label in keys:
        c, d = _delta(cur, prev, k)
        if c is None:
            continue
        p = prev.get(k) if prev else None
        lines.append(f"- {label}: {c}" + (f" ({'+' if d >= 0 else ''}{d} vs {p})" if d is not None else ""))
    lines.append("")
    tg = strat.get("targets") or {}
    if tg:
        lines.append("## Hedefler")
        for k, v in tg.items():
            lines.append(f"- {k}: {v}")
        lines.append("")
    if candidates:
        lines.append("## Kural tabanlı öneriler")
        for c in candidates:
            flag = "ONAY GEREKİR" if c.get("needs_approval") else "otomatik"
            lines.append(f"- [{flag}] {c['proposal']}  (neden: {c.get('why','')})")
        lines.append("")
    pend = state.pending_decisions()
    if pend:
        lines.append("## Onayınızı bekleyen kararlar (cevap: 'approve D-xxxxxx' veya 'reject D-xxxxxx')")
        for d in pend:
            lines.append(f"- {d['id']} ({d['date']}): {d['proposal']}")
        lines.append("")
    lines.append(f"## İçerik kuyruğu: {state.queued_count('pinterest')} pin, {state.queued_count('instagram')+state.queued_count('instagram_reel')} IG, {state.queued_count('youtube_short')} Short")
    if problems:
        lines += ["", "## Sorunlar / eksik bağlantılar"] + [f"- {p}" for p in problems]
    return "\n".join(lines)
