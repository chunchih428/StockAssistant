"""monitor/config.py — 讀取並合併 monitor_config.json 設定。"""
import json
from pathlib import Path

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "monitor_config.json"

_CACHE: dict | None = None


def load_monitor_config(path: Path | str | None = None) -> dict:
    """
    讀取 monitor_config.json，回傳完整 config dict。
    會 cache 第一次讀取結果；若要強制重讀請呼叫 reload_monitor_config()。
    """
    global _CACHE
    if _CACHE is not None and path is None:
        return _CACHE

    target = Path(path) if path else _DEFAULT_CONFIG_PATH
    if not target.exists():
        _CACHE = _empty_config()
        return _CACHE

    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [MonitorConfig] 讀取失敗：{e}，使用預設值")
        _CACHE = _empty_config()
        return _CACHE

    # 移除說明用的 _note / _example_disabled key
    config = _strip_meta(raw)
    _CACHE = config
    return _CACHE


def reload_monitor_config(path: Path | str | None = None) -> dict:
    """強制重新讀取設定檔（清除 cache）。"""
    global _CACHE
    _CACHE = None
    return load_monitor_config(path)


def get_thresholds(config: dict | None = None, symbol: str | None = None) -> dict:
    """
    取得生效閾值：先讀全域 thresholds，再套用 symbol 的 overrides。
    """
    cfg = config or load_monitor_config()
    base = dict(cfg.get("thresholds", {}))
    if symbol:
        override = cfg.get("overrides", {}).get(symbol, {})
        base.update(override)
    return base


def get_scoring_weights(config: dict | None = None) -> dict:
    """取得評分權重設定（scoring_weights 區塊）。"""
    cfg = config or load_monitor_config()
    return cfg.get("scoring_weights", {})


def _strip_meta(obj):
    """遞迴移除所有以 _ 開頭的說明 key。"""
    if isinstance(obj, dict):
        return {k: _strip_meta(v) for k, v in obj.items() if not k.startswith("_")}
    return obj


def _empty_config() -> dict:
    return {"thresholds": {}, "scoring_weights": {}, "overrides": {}}
