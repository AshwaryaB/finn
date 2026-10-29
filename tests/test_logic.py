from datetime import datetime

from app.alerts import price_volume_alerts
from app.classify import classify
from app.nse import IST
from app.prices import drop_partial_bar, signals

# NOTE: these are synthetic sentences written to exercise the rules, not captured NSE data.
CASES = [
    # --- real pairs captured from NSE (survey, 2026-10-27) ---
    ("Change in Management", "HDFC Bank Limited has informed the Exchange about change in Management", "management_change"),
    ("Copy of Newspaper Publication", "Tata Consultancy Services Limited has informed the Exchange about Copy of Newspaper Publication", "unclassified"),
    ("Updates", "Infosys Limited has informed the Exchange regarding 'Infosys to Announce Second Quarter Results on October 23,", "results"),
    ("Updates", "Infosys Limited has informed the Exchange regarding 'Report of auditors on financial statements for the quarte", "results"),
    ("Action(s) taken or orders passed", "Disclosure under Regulation 30 of the Securities and Exchange Board of India (Listing Obligations and Disclosu", "litigation"),
    ("Trading Window", "Reliance Industries Limited has informed the Exchange regarding the Trading Window closure pursuant to SEBI (P", "unclassified"),
    ("ESOP/ESOS/ESPS", "HDFC Bank Limited has informed the Exchange regarding Allotment of 9138522  Shares.", "unclassified"),
    ("Credit Rating", "x", "credit_rating"),
    ("Bagging/Receiving of orders/contracts", "x", "press_release"),
    ("Outcome of Board Meeting", "Tata Consultancy Services Limited has submitted to the Exchange, the financial results for the perio", "results"),
    ("Updates", "ICICI Bank Limited has informed the Exchange about Call with media on financial results for the quar", "earnings_call"),
    # --- synthetic ---
    ("Updates", "Outcome of Board Meeting - Unaudited Financial Results for the quarter ended September 30, 2026", "results"),
    ("Updates", "Appointment of Mr. X as Chief Financial Officer", "management_change"),
    ("Updates", "Resignation of Independent Director", "management_change"),
    ("Updates", "Appointment of Statutory Auditors", "unclassified"),
    ("Credit Rating", "Credit rating reaffirmed by CRISIL", "credit_rating"),
    ("Updates", "Transcript of earnings call for Q2", "earnings_call"),
    ("Updates", "Record date for final dividend", "dividend"),
    ("Updates", "Allotment of equity shares under ESOP", "unclassified"),
    ("General Updates", "Initial Public Offer of Jio Platforms Limited", "fund_raise"),
    ("Updates", "Newspaper publication of financial results", "results"),
    ("Updates", "Notice of Postal Ballot", "postal_ballot"),
    ("Updates", "Bonus issue approved by board", "bonus_split"),
    ("Updates", "Please find attached a media statement issued by the Company.", "press_release"),
    ("Updates", "Disclosure of pledge of shares by promoter", "pledging"),
    ("Updates", "Acquisition of 100% stake in XYZ Ltd", "M&A"),
    ("Updates", "Order from NCLT received", "litigation"),
    ("Updates", "Schedule of analyst / institutional investor meet", "investor_meetings"),
]


def test_classify():
    for desc, text, want in CASES:
        assert classify(desc, text) == want, (desc, text, classify(desc, text), want)


def _series(n=25, last_vol=3000, last_close=103.0):
    dates = [f"2026-09-{d:02d}" for d in range(1, n)] + ["2026-10-27"]
    return {"dates": dates, "close": [100.0] * (n - 1) + [last_close], "volume": [1000] * (n - 1) + [last_vol]}


def test_signals():
    s = signals(_series())
    assert s["pct"] == 3.0 and s["vol_ratio"] == 3.0 and s["avg_volume"] == 1000


def test_signals_short_history():
    assert signals({"dates": ["a"], "close": [1.0], "volume": [1]}) is None


def test_partial_bar():
    s = _series()
    intraday = datetime(2026, 10, 27, 11, 0, tzinfo=IST)
    after_close = datetime(2026, 10, 27, 16, 0, tzinfo=IST)
    assert len(drop_partial_bar(s, intraday)["close"]) == len(s["close"]) - 1
    assert len(drop_partial_bar(s, after_close)["close"]) == len(s["close"])


def test_alert_thresholds():
    sig = {"AAA": signals(_series()), "BBB": signals(_series(last_vol=1100, last_close=100.5))}
    assert [a["symbol"] for a in price_volume_alerts(sig, vol_mult=2.0, pct=3.0)] == ["AAA"]
    assert price_volume_alerts(sig, vol_mult=5.0, pct=5.0) == []


def test_intimation():
    from app.classify import is_intimation
    assert is_intimation("The meeting of the Board of Directors of the Company is scheduled on October 30, 2026, inter alia, to consider and approve the unaudited financial results")
    assert is_intimation("Infosys to Announce Second Quarter Results on October 23, 2026")
    assert not is_intimation("Larsen & Toubro Limited has submitted to the Exchange, the consolidated and standalone un-audited financial results")
    assert not is_intimation('Maruti Suzuki has informed the Exchange regarding a press release dated October 27, 2026, titled "Financial Results Q2"')
