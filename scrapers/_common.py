"""
scrapers/_common.py

scrap 공통 유틸:
1. Supabase 클라이언트
2. ConfigLoader (if_upgrade_pro_consumption에서 키 SELECT)
3. opportunities_raw INSERT 헬퍼
4. ssdm-collector trigger (repository_dispatch)
5. get_with_fallback (직접 연결 실패 시 KR 무료 프록시 폴백)

모든 scraper(bizinfo, g2b, ...)가 이 모듈 import해서 공통 처리.
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import requests
from supabase import create_client, Client


_CONFIG_TABLE = "if_upgrade_pro_consumption"
_RAW_TABLE = "opportunities_raw"


# ============================================================
# Supabase 클라이언트 (싱글톤)
# ============================================================
_sb_client: Optional[Client] = None


def get_supabase() -> Client:
    """Supabase 클라이언트 (싱글톤)."""
    global _sb_client
    if _sb_client is not None:
        return _sb_client
    
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL / SUPABASE_SERVICE_KEY 환경변수 필요"
        )
    
    _sb_client = create_client(url, key)
    return _sb_client


# ============================================================
# ConfigLoader — Supabase에서 키 SELECT (단일 진실 소스)
# ============================================================
class ConfigLoader:
    """
    if_upgrade_pro_consumption에서 키 메모리 캐시.
    sdm-backend의 ConfigLoader와 동일한 패턴.
    """
    _cache: Dict[str, Any] = {}
    _loaded: bool = False
    
    @classmethod
    def load(cls) -> Dict[str, Any]:
        if cls._loaded:
            return cls._cache
        
        try:
            sb = get_supabase()
            res = (
                sb.table(_CONFIG_TABLE)
                .select("k,v")
                .is_("company_id", "null")
                .execute()
            )
            cls._cache = {row["k"]: row["v"] for row in (res.data or [])}
            cls._loaded = True
            print(f"[ConfigLoader] {len(cls._cache)}개 키 로드: {list(cls._cache.keys())}")
        except Exception as e:
            print(f"[ConfigLoader] 로드 실패: {e}")
            cls._cache = {}
            cls._loaded = False
        
        return cls._cache
    
    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """원본 값 (str, dict, list 등 그대로)."""
        if not cls._loaded:
            cls.load()
        return cls._cache.get(key, default)
    
    @classmethod
    def get_str(cls, key: str, default: str = "") -> str:
        """
        문자열 키 추출.
        JSONB가 다양한 형태로 들어올 수 있어 robust하게 처리.
        """
        raw = cls.get(key)
        if isinstance(raw, str):
            return raw.strip() or default
        if isinstance(raw, dict):
            for v in raw.values():
                if isinstance(v, str) and v.strip():
                    return v.strip()
        return default


# ============================================================
# opportunities_raw INSERT 헬퍼
# ============================================================
def insert_raw(
    source_key: str,
    items: List[Dict[str, Any]],
    ext_id_field: str = "ext_id",
) -> Dict[str, int]:
    """
    raw 데이터를 opportunities_raw에 batch INSERT.
    
    Args:
        source_key: 'bizinfo' | 'g2b' | ...
        items: 정부 API raw 응답 리스트
        ext_id_field: items 각 dict에서 ext_id로 사용할 필드명
    
    Returns:
        {"total": N, "inserted": M, "skipped": K}
    """
    if not items:
        return {"total": 0, "inserted": 0, "skipped": 0}
    
    sb = get_supabase()
    rows = []
    for item in items:
        ext_id = str(item.get(ext_id_field, "")).strip() or None
        rows.append({
            "source_key": source_key,
            "ext_id": ext_id,
            "raw_data": item,
            "process_status": "pending",
        })
    
    inserted = 0
    skipped = 0
    batch_size = 100
    
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        try:
            res = sb.table(_RAW_TABLE).insert(batch).execute()
            inserted += len(res.data) if res.data else len(batch)
        except Exception as e:
            # UNIQUE 제약 위반은 정상 (같은 ext_id가 같은 시각에 두 번 들어올 일은 거의 없음)
            err_str = str(e)
            if "duplicate" in err_str.lower() or "unique" in err_str.lower():
                skipped += len(batch)
                print(f"[insert_raw] batch {i // batch_size + 1}: dup, skipped {len(batch)}")
            else:
                print(f"[insert_raw] batch {i // batch_size + 1} failed: {e}")
                skipped += len(batch)
    
    return {
        "total": len(rows),
        "inserted": inserted,
        "skipped": skipped,
    }


# ============================================================
# ssdm-collector 트리거 (repository_dispatch)
# ============================================================
def trigger_collector(source_key: str) -> bool:
    """
    ssdm-collector 레포에 'scrap-finished' 이벤트 발송.
    PAT 없으면 skip (나중에 cron이 백업으로 처리하니까 OK).
    """
    pat = os.environ.get("SDM_COLLECTOR_PAT", "").strip()
    if not pat:
        print("[trigger] SDM_COLLECTOR_PAT 없음, dispatch skip")
        return False
    
    try:
        resp = requests.post(
            "https://api.github.com/repos/devluka/ssdm-collector/dispatches",
            headers={
                "Authorization": f"token {pat}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "ssdm-scraper",
            },
            json={
                "event_type": "scrap-finished",
                "client_payload": {
                    "source_key": source_key,
                    "triggered_at": int(time.time()),
                },
            },
            timeout=15,
        )
        if resp.status_code in (200, 204):
            print(f"[trigger] ssdm-collector dispatched (source={source_key})")
            return True
        print(f"[trigger] failed status={resp.status_code} body={resp.text[:200]}")
        return False
    except Exception as e:
        print(f"[trigger] error: {e}")
        return False


# ============================================================
# HTTP 헤더 (정부 API 호출 시 브라우저 위장)
# ============================================================
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/xml, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}


# ============================================================
# KR 무료 프록시 폴백
# ------------------------------------------------------------
# 정부 사이트가 GitHub Actions(해외) IP를 간헐 차단하면서
# connect timeout 발생. 직접 연결 실패 시에만 한국 무료 프록시로
# 재시도하는 임시 폴백. 평소 직접 연결 성공 시엔 호출 비용 0.
#
# 주의: 무료 프록시는 신뢰성이 낮음(잦은 사망, HTTPS 미지원 등).
# 안정적 복구가 필요하면 유료 프록시/한국 리전 서버리스로 교체할 것.
# ============================================================
_PROXY_LIST_URL = (
    "https://api.proxyscrape.com/v4/free-proxy-list/get"
    "?request=display_proxies&country=kr&protocol=http"
    "&proxy_format=protocolipport&format=text&timeout=5000"
)
_proxy_cache: List[str] = []
_proxy_loaded: bool = False


def _load_kr_proxies() -> List[str]:
    """무료 한국 프록시 목록 조회 (프로세스당 1회 캐시)."""
    global _proxy_cache, _proxy_loaded
    if _proxy_loaded:
        return _proxy_cache
    _proxy_loaded = True
    try:
        resp = requests.get(_PROXY_LIST_URL, timeout=10)
        resp.raise_for_status()
        proxies = [ln.strip() for ln in resp.text.splitlines() if ln.strip()]
        _proxy_cache = proxies[:10]  # 상위 10개만
        print(f"[Proxy] loaded {len(_proxy_cache)} KR proxies")
    except Exception as e:
        print(f"[Proxy] load failed: {e}")
        _proxy_cache = []
    return _proxy_cache


def get_with_fallback(url: str, **kwargs) -> requests.Response:
    """
    직접 연결 시도 → connect 실패 시 KR 프록시 폴백.

    - 평소엔 requests.get 직접 호출과 동일 (프록시 미사용, 추가 비용 0).
    - ConnectTimeout / ConnectionError 발생 시에만 한국 무료 프록시를
      차례로 시도. 프록시는 직접 연결보다 느릴 수 있어 timeout을 넉넉히 줌.
    - 모든 프록시 실패 시 원래 직접 연결 예외를 그대로 재발생.

    호출부는 requests.get과 동일한 시그니처로 사용 가능.
    """
    try:
        return requests.get(url, **kwargs)
    except (requests.exceptions.ConnectTimeout,
            requests.exceptions.ConnectionError) as direct_err:
        print(f"[Proxy] direct failed ({direct_err.__class__.__name__}), trying proxies")

        # 프록시는 직접 연결보다 느리므로 timeout을 늘려준다 (최소 30s).
        proxy_kwargs = dict(kwargs)
        base_timeout = proxy_kwargs.get("timeout", 20)
        try:
            proxy_kwargs["timeout"] = max(int(base_timeout), 30)
        except (TypeError, ValueError):
            proxy_kwargs["timeout"] = 30

        for proxy in _load_kr_proxies():
            try:
                resp = requests.get(
                    url,
                    proxies={"http": proxy, "https": proxy},
                    **proxy_kwargs,
                )
                resp.raise_for_status()
                print(f"[Proxy] success via {proxy}")
                return resp
            except Exception:
                continue

        print("[Proxy] all proxies failed")
        raise direct_err
