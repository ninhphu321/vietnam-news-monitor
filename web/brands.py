"""Brand dictionary + watchlist: which banks/companies a headline mentions.

Pure rule-based (no AI): every brand has a canonical name and a list of
aliases; a headline "mentions" a brand when one of its aliases appears as
a whole word. Matching rules that matter for Vietnamese finance headlines:

  * Short all-caps aliases (tickers such as "MB", "ACB", "VIB", "CTG") are
    matched CASE-SENSITIVELY — otherwise "mb" (megabyte) or "vib" would
    match ordinary text. Longer / mixed-case names ("Vietcombank",
    "Ngân hàng Ngoại thương") match case-insensitively.
  * Aliases match on word boundaries, so "ABB" never matches inside
    "ABBank" (that is its own alias) or "SHB" inside another token.

No personal names (chairmen, spokespeople) are bundled: they change and
would be guesswork. Add them per deployment via watchlist.json
("extra_aliases"), which is also where the own-brand / competitor
lists live.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class Brand:
    name: str
    kind: str                       # "bank" | "regulator" | "custom"
    aliases: Tuple[str, ...]


def _b(name, kind, *aliases):
    return Brand(name, kind, tuple(aliases) or (name,))


# Canonical name first in each alias list is implied by _b().
DEFAULT_BRANDS: List[Brand] = [
    _b("Vietcombank", "bank", "Vietcombank", "VCB", "Ngân hàng Ngoại thương"),
    _b("VietinBank", "bank", "VietinBank", "CTG", "Ngân hàng Công thương"),
    _b("BIDV", "bank", "BIDV", "BID"),
    _b("Agribank", "bank", "Agribank"),
    _b("Techcombank", "bank", "Techcombank", "TCB"),
    _b("MB", "bank", "MBBank", "MB Bank", "MB", "Ngân hàng Quân đội"),
    _b("ACB", "bank", "ACB", "Ngân hàng Á Châu"),
    _b("VPBank", "bank", "VPBank", "VPB"),
    _b("Sacombank", "bank", "Sacombank", "STB"),
    _b("HDBank", "bank", "HDBank", "HDB"),
    _b("TPBank", "bank", "TPBank", "TPB"),
    _b("VIB", "bank", "VIB"),
    _b("SHB", "bank", "SHB"),
    _b("OCB", "bank", "OCB"),
    _b("MSB", "bank", "MSB"),
    _b("LPBank", "bank", "LPBank", "LPB", "LienVietPostBank"),
    _b("SeABank", "bank", "SeABank", "SSB"),
    _b("Eximbank", "bank", "Eximbank", "EIB"),
    _b("ABBank", "bank", "ABBank", "ABB"),
    _b("Nam A Bank", "bank", "Nam A Bank", "NAB"),
    _b("Bac A Bank", "bank", "Bac A Bank", "BAB"),
    _b("BaoViet Bank", "bank", "BaoViet Bank", "BVBank"),
    _b("Kienlongbank", "bank", "Kienlongbank", "KLB"),
    _b("PVcomBank", "bank", "PVcomBank"),
    _b("Vietbank", "bank", "Vietbank"),
    _b("NCB", "bank", "NCB"),
    _b("SCB", "bank", "SCB"),
    _b("Ngân hàng Nhà nước", "regulator", "Ngân hàng Nhà nước", "NHNN", "SBV"),
]


def _alias_pattern(alias: str) -> re.Pattern:
    body = re.escape(alias)
    case_sensitive = len(alias) <= 4 and alias.isupper()
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(rf"(?<!\w){body}(?!\w)", flags)


class BrandIndex:
    """Compiled matcher: `detect(title)` -> brand names mentioned."""

    def __init__(self, brands: Iterable[Brand]):
        self.brands: Dict[str, Brand] = {b.name: b for b in brands}
        self._patterns: List[Tuple[str, List[re.Pattern]]] = [
            (b.name, [_alias_pattern(a) for a in b.aliases]) for b in self.brands.values()
        ]

    def detect(self, title: str) -> List[str]:
        return [name for name, pats in self._patterns if any(p.search(title) for p in pats)]

    def kind_of(self, name: str) -> str:
        return self.brands[name].kind


@dataclass
class Watchlist:
    own: List[str]
    competitors: List[str]
    negative_extra: List[str]

    @property
    def tracked(self) -> List[str]:
        return list(dict.fromkeys(self.own + self.competitors))


def load_watchlist(path: Optional[Path]) -> Tuple[BrandIndex, Watchlist]:
    """Reads watchlist.json (optional) and returns (index, watchlist).

    {
      "own": ["Techcombank"],
      "competitors": ["VPBank", "MB"],
      "extra_aliases": {"Techcombank": ["Techcom"]},
      "extra_brands": [{"name": "Vingroup", "aliases": ["Vingroup", "VIC"]}],
      "extra_negative_keywords": ["thanh tra"]
    }

    A name in own/competitors that is not in the built-in dictionary is
    added automatically as a custom brand whose only alias is the name
    itself. A missing or unreadable file yields the default dictionary
    and an empty watchlist (= track every known brand)."""
    data: dict = {}
    if path and Path(path).exists():
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}

    brands: Dict[str, Brand] = {b.name: b for b in DEFAULT_BRANDS}
    for name, extra in (data.get("extra_aliases") or {}).items():
        base = brands.get(name)
        if base is not None:
            brands[name] = Brand(base.name, base.kind, base.aliases + tuple(extra))
        else:
            brands[name] = Brand(name, "custom", (name, *extra))
    for item in data.get("extra_brands") or []:
        name = item.get("name")
        if name:
            brands[name] = Brand(name, "custom", tuple(item.get("aliases") or [name]))

    own = [n for n in (data.get("own") or []) if isinstance(n, str)]
    competitors = [n for n in (data.get("competitors") or []) if isinstance(n, str)]
    for name in own + competitors:
        brands.setdefault(name, Brand(name, "custom", (name,)))

    watch = Watchlist(own=own, competitors=competitors,
                      negative_extra=[k for k in (data.get("extra_negative_keywords") or []) if isinstance(k, str)])
    return BrandIndex(brands.values()), watch
