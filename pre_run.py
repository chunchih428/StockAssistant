#!/usr/bin/env python3
import csv
import datetime
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from portfolio import PortfolioService

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    class _YFStub:
        class Ticker:
            def __init__(self, *_args, **_kwargs):
                self.info = {}

    yf = _YFStub()


class StockPrerun:
    def __init__(
        self,
        portfolio_file,
        config_file,
        system_prompt_file,
        company_names_file,
        competitors_file=None,
    ):
        self.PORTFOLIO_FILE = Path(portfolio_file)
        self.CONFIG_FILE = Path(config_file)
        self.SYSTEM_PROMPT_FILE = Path(system_prompt_file)
        self.COMPANY_NAMES_FILE = Path(company_names_file)
        self.COMPETITORS_FILE = Path(competitors_file) if competitors_file else self.CONFIG_FILE.parent / "competitors.json"
        self.COMPETITOR_SKIP_FILE = self.CONFIG_FILE.parent / "competitor_skip.json"
        self.cache_mgr = None
        self.comp_cache_mgr = None

    @staticmethod
    def _today():
        return datetime.date.today().isoformat()

    @staticmethod
    def _is_us_peer_symbol(symbol):
        """Heuristic: keep common US tickers only (1-5 uppercase letters, no dot)."""
        if not isinstance(symbol, str):
            return False
        sym = symbol.strip().upper()
        if "." in sym:
            return False
        return re.fullmatch(r"[A-Z]{1,5}", sym) is not None

    @staticmethod
    def _normalize_peer_list(peers, self_symbol):
        out = []
        seen = set()
        self_sym = (self_symbol or "").strip().upper()
        for item in peers or []:
            if not isinstance(item, str):
                continue
            sym = item.strip().upper()
            if not sym or sym == self_sym or sym in seen:
                continue
            if not StockPrerun._is_us_peer_symbol(sym):
                continue
            seen.add(sym)
            out.append(sym)
        return out

    def _skip_path(self):
        return self.CONFIG_FILE.parent / "competitor_skip.json"

    def _candidate_paths(self):
        paths = []
        primary = self.CONFIG_FILE.parent / "candidates.txt"
        paths.append(primary)
        fallback = self.CONFIG_FILE.parent.parent / "candidates.txt"
        if fallback != primary:
            paths.append(fallback)
        return paths

    def _load_candidates(self):
        out = set()
        for p in self._candidate_paths():
            if not p.exists():
                continue
            try:
                for raw in p.read_text(encoding="utf-8").splitlines():
                    line = raw.split("#", 1)[0].strip().upper()
                    if self._is_us_peer_symbol(line):
                        out.add(line)
            except Exception:
                continue
        return out

    def _load_skip_registry(self):
        skip_path = self._skip_path()
        if not skip_path.exists():
            return {"_schema_version": "1.0", "symbols": {}}
        try:
            data = json.loads(skip_path.read_text(encoding="utf-8"))
            symbols = data.get("symbols", {}) if isinstance(data, dict) else {}
            return {"_schema_version": "1.0", "symbols": symbols}
        except Exception:
            return {"_schema_version": "1.0", "symbols": {}}

    def _save_skip_registry(self, data):
        skip_path = self._skip_path()
        skip_path.parent.mkdir(parents=True, exist_ok=True)
        skip_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _prune_skip_registry(self, data):
        changed = False
        symbols = data.get("symbols", {})
        today = datetime.date.today()
        remove_keys = []
        for sym, payload in symbols.items():
            added_at = payload.get("added_at")
            try:
                dt = datetime.date.fromisoformat(added_at)
            except Exception:
                dt = today
            if (today - dt).days > 90:
                remove_keys.append(sym)
        for sym in remove_keys:
            symbols.pop(sym, None)
            changed = True
        return changed

    def check_setup(self):
        missing = []
        if not self.PORTFOLIO_FILE.exists():
            missing.append(str(self.PORTFOLIO_FILE))
        if missing:
            print("[錯誤] 缺少必要檔案:")
            for p in missing:
                print(f"  - {p}")
            sys.exit(1)

        has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
        if not has_api_key:
            print("[提醒] 找不到 ANTHROPIC_API_KEY，將以純數據模式執行。")
        return has_api_key

    def load_config(self):
        default_config = {
            "model": "claude-sonnet-4-6",
            "max_tokens": 2000,
            "news_count": 20,
            "only_tickers": [],
            "skip_tickers": [],
            "cache_ttl": {
                "fundamental_days": 90,
                "technical_hours": 4,
                "news_hours": 30,
                "company_info_days": 365,
            },
        }

        if self.CONFIG_FILE.exists():
            try:
                raw = json.loads(self.CONFIG_FILE.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    merged = dict(default_config)
                    merged.update(raw)
                    print(f"  [Config] 已載入: {self.CONFIG_FILE}")
                    return merged
            except Exception:
                print(f"  [WARN] 設定檔讀取失敗，將改用預設值: {self.CONFIG_FILE}")
                pass

        self.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.CONFIG_FILE.write_text(
            json.dumps(default_config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  [Config] 已建立預設設定檔: {self.CONFIG_FILE}")
        return default_config

    def load_company_names(self):
        if not self.COMPANY_NAMES_FILE.exists():
            return {}
        try:
            data = json.loads(self.COMPANY_NAMES_FILE.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {}
            if "holdings" in data or "competitors" in data:
                merged = {}
                merged.update(data.get("holdings", {}))
                merged.update(data.get("competitors", {}))
                return merged
            return data
        except Exception:
            return {}

    def save_company_names(self, names, portfolio_symbols=None):
        existing_holdings = {}
        existing_competitors = {}
        if self.COMPANY_NAMES_FILE.exists():
            try:
                existing = json.loads(self.COMPANY_NAMES_FILE.read_text(encoding="utf-8"))
                if isinstance(existing, dict):
                    if "holdings" in existing or "competitors" in existing:
                        existing_holdings = dict(existing.get("holdings", {}))
                        existing_competitors = dict(existing.get("competitors", {}))
                    else:
                        existing_holdings = dict(existing)
            except Exception:
                existing_holdings = {}
                existing_competitors = {}

        holdings = {}
        competitors = {}

        if portfolio_symbols is not None:
            pset = set(portfolio_symbols)
            for sym, name in names.items():
                if sym in pset:
                    holdings[sym] = name
                else:
                    competitors[sym] = name
        elif existing_holdings:
            holdings = {sym: names[sym] for sym in existing_holdings.keys() if sym in names}
            for sym, name in names.items():
                if sym not in holdings:
                    competitors[sym] = name
        else:
            holdings = dict(names)

        for sym, name in existing_competitors.items():
            if sym not in holdings and sym not in competitors:
                competitors[sym] = name

        self.COMPANY_NAMES_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {"holdings": holdings, "competitors": competitors}
        self.COMPANY_NAMES_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _parse_option(symbol):
        return PortfolioService.parse_option(symbol)

    def load_portfolio(self):
        return PortfolioService(self.PORTFOLIO_FILE).load_portfolio(
            csv_reader_cls=csv.DictReader,
            open_fn=open,
        )

    def auto_populate_competitors(self, portfolio_symbols):
        comp_path = self.CONFIG_FILE.parent / "competitors.json"
        print(f"\n  [競品] 檢查競品設定: {comp_path}")
        skip_data = self._load_skip_registry()
        skip_changed = self._prune_skip_registry(skip_data)
        if skip_changed:
            self._save_skip_registry(skip_data)
            print("    [競品] 已清理超過 90 天的 skip 紀錄")

        changed = False
        try:
            if comp_path.exists():
                raw = json.loads(comp_path.read_text(encoding="utf-8"))
            else:
                raw = {"holdings": {}, "competitors": {}}
        except Exception:
            print(f"  [WARN] 競品設定讀取失敗: {comp_path}")
            return

        if "holdings" in raw or "competitors" in raw or "candidates" in raw:
            holdings_map = dict(raw.get("holdings", {}))
            competitors_map = dict(raw.get("competitors", {}))
            candidates_map = dict(raw.get("candidates", {}))
        else:
            holdings_map = dict(raw)
            competitors_map = {}
            candidates_map = {}
            changed = True

        portfolio_set = {
            str(sym).strip().upper()
            for sym in portfolio_symbols
            if self._is_us_peer_symbol(str(sym).strip().upper())
        }
        candidate_set = self._load_candidates() - portfolio_set
        fetch_root_set = portfolio_set | candidate_set

        normalized_holdings = {}
        for sym, peers in holdings_map.items():
            sym_u = str(sym).strip().upper()
            if not self._is_us_peer_symbol(sym_u):
                continue
            if peers is None:
                changed = True
            normalized_holdings[sym_u] = self._normalize_peer_list(peers, sym_u)
        holdings_map = normalized_holdings

        normalized_competitors = {}
        for sym, peers in competitors_map.items():
            sym_u = str(sym).strip().upper()
            if not self._is_us_peer_symbol(sym_u):
                continue
            if peers is None:
                changed = True
            normalized_competitors[sym_u] = self._normalize_peer_list(peers, sym_u)
        competitors_map = normalized_competitors

        normalized_candidates = {}
        for sym, peers in candidates_map.items():
            sym_u = str(sym).strip().upper()
            if not self._is_us_peer_symbol(sym_u):
                continue
            if peers is None:
                changed = True
            normalized_candidates[sym_u] = self._normalize_peer_list(peers, sym_u)
        candidates_map = normalized_candidates

        def _map_for(symbol):
            if symbol in portfolio_set:
                return holdings_map
            if symbol in candidate_set:
                return candidates_map
            return competitors_map

        api_key = os.environ.get("FINNHUB_API_KEY")
        pending = list(sorted(fetch_root_set))
        seen = set(pending)

        for sym in list(holdings_map.keys()) + list(candidates_map.keys()) + list(competitors_map.keys()):
            if sym not in seen:
                pending.append(sym)
                seen.add(sym)
        for peers in list(holdings_map.values()) + list(candidates_map.values()) + list(competitors_map.values()):
            for p in peers:
                if p not in seen:
                    pending.append(p)
                    seen.add(p)

        idx = 0
        while idx < len(pending):
            sym = pending[idx]
            idx += 1
            target_map = _map_for(sym)
            peers = target_map.get(sym)

            if peers:
                continue

            skip_payload = skip_data.get("symbols", {}).get(sym)
            if skip_payload:
                print(f"    [競品] 跳過 {sym}（skip registry）")
                continue

            if not api_key:
                continue

            try:
                print(f"    [競品] 取得 {sym} 同業清單...(剩下 {len(pending) - idx} 檔)")
                resp = requests.get(
                    "https://finnhub.io/api/v1/stock/peers",
                    params={"symbol": sym, "token": api_key},
                    timeout=15,
                )
                if resp.status_code != 200:
                    continue
                fetched = self._normalize_peer_list(resp.json() or [], sym)
            except Exception:
                print(f"      ❌ {sym} 同業清單取得失敗")
                continue

            if fetched:
                target_map[sym] = fetched
                changed = True
                print(f"      ✅ {sym}: 新增 {len(fetched)} 檔競品")
                for peer in fetched:
                    peer_map = _map_for(peer)
                    if peer not in peer_map:
                        peer_map[peer] = None
                        changed = True
            else:
                target_map[sym] = []
                changed = True
                skip_data.setdefault("symbols", {})[sym] = {
                    "added_at": self._today(),
                    "reason": "no_peers_or_non_us",
                }
                self._save_skip_registry(skip_data)
                print(f"      ⚠️ {sym}: 無可用競品，加入 skip registry")
            time.sleep(0.2)

        for sym in list(holdings_map.keys()):
            if sym not in portfolio_set:
                holdings_map.pop(sym, None)
                changed = True

        for sym in list(candidates_map.keys()):
            if sym not in candidate_set:
                candidates_map.pop(sym, None)
                changed = True
        for sym in list(candidate_set):
            if sym not in candidates_map:
                candidates_map[sym] = []
                changed = True

        for sym in list(competitors_map.keys()):
            if sym in portfolio_set or sym in candidate_set:
                competitors_map.pop(sym, None)
                changed = True

        direct_holdings_peers = set()
        for hs in portfolio_set:
            direct_holdings_peers.update(holdings_map.get(hs) or [])
        direct_candidate_peers = set()
        for cs in candidate_set:
            direct_candidate_peers.update(candidates_map.get(cs) or [])
        allowed_competitors = (
            (direct_holdings_peers - portfolio_set)
            | (direct_candidate_peers - portfolio_set - candidate_set)
        )
        for sym in list(competitors_map.keys()):
            if sym not in allowed_competitors:
                competitors_map.pop(sym, None)
                changed = True

        for m in (holdings_map, candidates_map, competitors_map):
            for k, v in list(m.items()):
                if v is None:
                    m[k] = []  # pragma: no cover
                    changed = True

        payload = {"holdings": holdings_map, "competitors": competitors_map, "candidates": candidates_map}
        if changed:
            comp_path.parent.mkdir(parents=True, exist_ok=True)
            comp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"  [競品] 已更新: {comp_path}")

    def ensure_competitor_names(self, company_names, portfolio_symbols=None):
        comp_path = self.CONFIG_FILE.parent / "competitors.json"
        if not comp_path.exists():
            return
        try:
            raw = json.loads(comp_path.read_text(encoding="utf-8"))
        except Exception:
            return

        if "holdings" in raw or "competitors" in raw or "candidates" in raw:
            holdings_map = raw.get("holdings", {})
            competitors_map = raw.get("competitors", {})
            candidates_map = raw.get("candidates", {})
        else:
            holdings_map = raw
            competitors_map = {}
            candidates_map = {}

        if portfolio_symbols is not None:
            targets = set(portfolio_symbols) | self._load_candidates()
        else:
            targets = set(holdings_map.keys()) | self._load_candidates()
        merged_map = {}
        merged_map.update(holdings_map)
        merged_map.update(candidates_map)
        merged_map.update(competitors_map)
        missing = []
        for sym in targets:
            for comp in (merged_map.get(sym) or []):
                if comp and comp not in company_names:
                    missing.append(comp)

        if not missing:
            return

        print(f"  [Company Names] 補齊競品名稱: {len(set(missing))} 檔")
        changed = False
        for comp in sorted(set(missing)):
            try:
                info = yf.Ticker(comp).info or {}
                name = info.get("shortName") or info.get("longName")
                if name:
                    company_names[comp] = name
                    changed = True
                    print(f"    [Company Names] {comp} -> {name}")
            except Exception:
                pass
            time.sleep(0.2)

        if changed:
            self.save_company_names(company_names, portfolio_symbols)
            print("  [Company Names] 已寫回 company_names.json")

    def process_cache(self):
        if not self.cache_mgr or not self.comp_cache_mgr:
            return

        if "--fresh" in sys.argv:
            if self.cache_mgr.has_fresh_today():
                print("  [Cache] 今日已 fresh，跳過清除")
                return

            print("  [Cache] fresh 模式：清除 news/technical")
            self.cache_mgr.clear(category="news")
            self.cache_mgr.clear(category="technical")
            self.comp_cache_mgr.clear(category="news")
            self.comp_cache_mgr.clear(category="technical")

            if self.cache_mgr.is_earnings_season():
                print("  [Cache] 財報季：額外清除 fundamental")
                self.cache_mgr.clear(category="fundamental")
                self.comp_cache_mgr.clear(category="fundamental")
            return

        print("  [Cache] 一般模式：清理過期快取")
        self.cache_mgr.clear_expired()
        self.comp_cache_mgr.clear_expired()
