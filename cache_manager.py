#!/usr/bin/env python3
import datetime
import json
from pathlib import Path


def find_latest_cache_file(cache_dir, scope, category, symbol):
    """Return latest cache path under cache/{YYYY-MM-DD}/{scope}/{category}/{symbol}.json."""
    base = Path(cache_dir)
    if not base.exists():
        return None

    date_dirs = sorted(
        [d for d in base.iterdir() if d.is_dir() and len(d.name) == 10],
        key=lambda d: d.name,
        reverse=True,
    )
    for d in date_dirs:
        path = d / scope / category / f"{symbol}.json"
        if path.exists():
            return path
    return None


def load_latest_cache_json(cache_dir, scope, category, symbol):
    """Load latest cache JSON (without TTL validation)."""
    path = find_latest_cache_file(cache_dir, scope, category, symbol)
    if path and path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def find_latest_news_analysis_file(cache_dir, scope, symbol):
    """Return latest cache path for {symbol}_analysis.json under news category."""
    base = Path(cache_dir)
    if not base.exists():
        return None

    date_dirs = sorted(
        [d for d in base.iterdir() if d.is_dir() and len(d.name) == 10],
        key=lambda d: d.name,
        reverse=True,
    )
    for d in date_dirs:
        path = d / scope / "news" / f"{symbol}_analysis.json"
        if path.exists():
            return path
    return None


class CacheManager:
    """Three-layer cache manager with type-specific TTL policy."""

    DEFAULT_TTL = {
        "fundamental": 0,
        "technical": 4 * 3600,
        "news": 30 * 3600,
        "company_info": 30 * 24 * 3600,
    }

    def __init__(self, config=None, scope="holdings", base_cache_dir="cache"):
        self.scope = scope
        self.base_cache_dir = Path(base_cache_dir)
        self.stats = {"hits": 0, "misses": 0}
        self.fresh_active = False

        self.ttl = dict(self.DEFAULT_TTL)
        if config and "cache_ttl" in config:
            ct = config["cache_ttl"]
            if "fundamental_days" in ct:
                self.ttl["fundamental"] = ct["fundamental_days"] * 24 * 3600
            if "technical_hours" in ct:
                self.ttl["technical"] = ct["technical_hours"] * 3600
            if "news_hours" in ct:
                self.ttl["news"] = ct["news_hours"] * 3600
            if "company_info_days" in ct:
                self.ttl["company_info"] = ct["company_info_days"] * 24 * 3600

    @property
    def _today(self):
        return datetime.date.today().isoformat()

    def _cache_path(self, category, symbol):
        day_dir = self.base_cache_dir / self._today / self.scope / category
        day_dir.mkdir(parents=True, exist_ok=True)
        return day_dir / f"{symbol}.json"

    def _find_latest_cache(self, category, symbol):
        return find_latest_cache_file(self.base_cache_dir, self.scope, category, symbol)

    def _get_ttl(self, category):
        return self.ttl.get(category, 3600)

    def is_valid(self, category, symbol):
        path = self._find_latest_cache(category, symbol)
        if not path:
            return False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if category == "fundamental":
                return not self.should_refresh_fundamental(data)

            cached_time = datetime.datetime.fromisoformat(data["_cached_at"])
            age = (datetime.datetime.now() - cached_time).total_seconds()
            return age < self._get_ttl(category)
        except (json.JSONDecodeError, KeyError, ValueError):
            return False

    def get(self, category, symbol):
        path = self._find_latest_cache(category, symbol)
        if not path:
            self.stats["misses"] += 1
            return None
        try:
            raw_text = path.read_text(encoding="utf-8")
            data = json.loads(raw_text)

            if category == "fundamental":
                if self.should_refresh_fundamental(data):
                    self.stats["misses"] += 1
                    return None
            else:
                cached_time = datetime.datetime.fromisoformat(data["_cached_at"])
                age = (datetime.datetime.now() - cached_time).total_seconds()
                if age >= self._get_ttl(category):
                    self.stats["misses"] += 1
                    return None
            self.stats["hits"] += 1

            today_path = self._cache_path(category, symbol)
            if path != today_path and not today_path.exists():
                print(
                    f"    [Cache/copy] 複製有效快取 {category}/{symbol}: "
                    f"{path.parent.name} -> {today_path.parent.name}"
                )
                today_path.write_text(raw_text, encoding="utf-8")

                if category == "news":
                    analysis_src = path.parent / f"{symbol}_analysis.json"
                    if analysis_src.exists():
                        analysis_dst = today_path.parent / f"{symbol}_analysis.json"
                        if not analysis_dst.exists():
                            print(f"    [Cache/copy] 一併複製分析結果 {symbol}_analysis.json")
                            analysis_dst.write_text(
                                analysis_src.read_text(encoding="utf-8"),
                                encoding="utf-8",
                            )
            return {k: v for k, v in data.items() if not k.startswith("_")}
        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            self.stats["misses"] += 1
            return None

    def set(self, category, symbol, data):
        path = self._cache_path(category, symbol)
        cache_data = dict(data)
        cache_data["_cached_at"] = datetime.datetime.now().isoformat()
        path.write_text(
            json.dumps(cache_data, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    def clear(self, category=None, symbol=None):
        if category and symbol:
            path = self._cache_path(category, symbol)
            if path.exists():
                print(f"  [Cache/clear] 刪除 {category}/{symbol}: {path}")
                path.unlink()
        elif category:
            today_dir = self.base_cache_dir / self._today / self.scope / category
            if today_dir.exists():
                count = 0
                for f in today_dir.glob("*.json"):
                    print(f"  [Cache/clear] 刪除 {category}/{f.stem}: {f}")
                    f.unlink()
                    count += 1
                print(f"  [Cache/clear] {category} 類別共刪除 {count} 個檔案")
        else:
            total = 0
            for cat in ["fundamental", "technical", "news"]:
                today_dir = self.base_cache_dir / self._today / self.scope / cat
                if today_dir.exists():
                    for f in today_dir.glob("*.json"):
                        print(f"  [Cache/clear] 刪除 {cat}/{f.stem}: {f}")
                        f.unlink()
                        total += 1
            print(f"  [Cache/clear] 總共刪除 {total} 個檔案")

    def has_fresh_today(self):
        today_dir = self.base_cache_dir / self._today / self.scope / "news"
        if not today_dir.exists():
            return False
        return any(today_dir.glob("*.json"))

    def should_refresh_fundamental(self, cached_data):
        if cached_data is None:
            return True

        ed = cached_data.get("next_earnings_date")
        if not ed:
            return False

        try:
            earnings_dt = datetime.date.fromisoformat(ed)
            today = datetime.date.today()
            if today < earnings_dt:
                return False

            # After earnings date passes, only refresh if the last fetch is at least 2 days old.
            cached_at = cached_data.get("_cached_at")
            if not cached_at:
                return True
            try:
                cached_dt = datetime.datetime.fromisoformat(cached_at)
            except (ValueError, TypeError):
                return True
            age_days = (datetime.datetime.now() - cached_dt).total_seconds() / 86400
            return age_days >= 2
        except (ValueError, TypeError):
            return False

    def is_earnings_season(self):
        today = datetime.datetime.now()
        return today.month in (1, 4, 7, 10) and today.day <= 45

    def clear_expired(self):
        removed = 0
        if not self.base_cache_dir.exists():
            return 0

        for date_dir in sorted(self.base_cache_dir.iterdir()):
            if not date_dir.is_dir() or len(date_dir.name) != 10:
                continue

            for category in ["fundamental", "technical", "news"]:
                cat_dir = date_dir / self.scope / category
                if not cat_dir.exists():
                    continue
                for f in cat_dir.glob("*.json"):
                    symbol = f.stem
                    if symbol.endswith("_analysis"):
                        continue
                    try:
                        data = json.loads(f.read_text(encoding="utf-8"))
                        if category == "news":
                            # news 保留完整歷史，不依 TTL 刪除
                            pass
                        elif category == "fundamental":
                            if self.should_refresh_fundamental(data):
                                print(f"  [Cache/expired] 刪除過期檔案 {category}/{symbol}: {f}")
                                f.unlink()
                                removed += 1
                        else:
                            cached_time = datetime.datetime.fromisoformat(data["_cached_at"])
                            age = (datetime.datetime.now() - cached_time).total_seconds()
                            if age >= self._get_ttl(category):
                                print(f"  [Cache/expired] 刪除過期檔案 {category}/{symbol}: {f}")
                                f.unlink()
                                removed += 1
                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        print(f"  [Cache/expired] 刪除損壞檔案 {category}/{symbol}: {f}")
                        print(f"    └─ 錯誤: {type(e).__name__}: {e}")
                        f.unlink()
                        removed += 1

                if not any(cat_dir.iterdir()):
                    print(f"  [Cache/expired] 移除空目錄: {cat_dir}")
                    cat_dir.rmdir()

            scope_dir = date_dir / self.scope
            if scope_dir.exists() and not any(scope_dir.iterdir()):
                scope_dir.rmdir()

            if date_dir.exists() and not any(date_dir.iterdir()):
                print(f"  [Cache/expired] 移除空日期目錄: {date_dir}")
                date_dir.rmdir()
        return removed

    def print_stats(self):
        total = self.stats["hits"] + self.stats["misses"]
        if total == 0:
            return
        rate = self.stats["hits"] / total * 100
        print(f"\n  [Cache] 命中: {self.stats['hits']} / {total} ({rate:.0f}%)")
