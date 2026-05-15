# sdm-scrap

ẞDM의 정부지원사업 공고 수집 워커 + 멀티 알림 허브 + 대시보드.

GitHub Actions runner를 한국 IP로 사용해 정부 API 차단 회피.

## 역할

```
sdm-scrap (이 레포, public)
├── 정부 API raw 수집  → opportunities_raw INSERT
├── 멀티 알림 허브      → email/sms/kakao/slack/desktop/webhook
└── 모니터 대시보드     → GitHub Pages

sdm-collector (별도 레포, public)
├── opportunities_raw → opportunities 정제
└── (sdm-scrap이 trigger)

sdm-backend (별도 레포, private)
└── 사용자 API 서빙
```

## 구조

```
sdm-scrap/
├── .github/workflows/
│   ├── bizinfo.yml              KST 05:00, 15:30 cron
│   ├── g2b.yml                  KST 05:00, 15:30 cron
│   ├── alert.yml                workflow_dispatch (수동 알림)
│   └── update-dashboard.yml     KST 06:00, 16:30 cron (scrap 1h 후)
├── scrapers/
│   ├── _common.py               Supabase + ConfigLoader + insert_raw + trigger
│   ├── bizinfo.py               기업마당 (di9H8z 키, bzk)
│   └── g2b.py                   나라장터 (gtd 키)
├── notifiers/
│   ├── _base.py                 BaseNotifier 추상 클래스
│   ├── email.py                 Gmail SMTP (구현 완료)
│   ├── sms.py                   stub
│   ├── kakao.py                 stub
│   ├── slack.py                 stub
│   ├── desktop.py               stub
│   └── webhook.py               stub
├── scripts/
│   ├── alert_runner.py          alert.yml 진입점
│   └── update_dashboard.py      scrap_monitor → docs/data.json
├── docs/                        GitHub Pages
│   ├── index.html               대시보드
│   ├── styles.css               다크/블루
│   ├── app.js                   Chart.js + data.json
│   ├── data.json                워크플로 자동 갱신
│   └── favicon.png              ← 박사님 fav_16.png 자리
├── requirements.txt
├── .gitignore
└── README.md
```

## GitHub Secrets

```
SUPABASE_URL                 https://kxjgzxyoupfqdrnwjnku.supabase.co
SUPABASE_SERVICE_KEY         (박사님 service_role)
SDM_COLLECTOR_PAT            sdm-collector 레포 dispatch 권한 PAT
                             (Fine-grained: sdm-collector contents:write)
```

## 동작 흐름

```
KST 05:00 / 15:30
  ├── Bizinfo 워크플로 → bizinfo API → opportunities_raw → trigger collector
  └── G2B 워크플로     → G2B API     → opportunities_raw → trigger collector

KST ~05:30 / 16:00 (collector가 처리)
  └── opportunities_raw pending → opportunities upsert → processed 마킹

KST 06:00 / 16:30
  └── Dashboard 워크플로 → scrap_monitor SELECT → docs/data.json → commit
                          → GitHub Pages 자동 배포
```

## 키 정책 — 모두 Supabase에서

`if_upgrade_pro_consumption` 테이블이 단일 진실 소스:

| 키 | 용도 |
|----|------|
| `bzk` | Bizinfo 자체 인증키 (6자, di9H8z) |
| `gtd` | G2B Decoding 키 (data.go.kr) |
| `gke` | G2B Encoding 키 (백업) |
| `shk`, `spk`, `suk`, `smp` | Gmail SMTP |
| `grk` | Groq LLM (예정) |

GitHub Secrets에는 Supabase 접근 키만 박음. 정부 API 키는 Supabase에서 SELECT.

## 새 source 추가 패턴

예: NTIS 추가 시

1. `scrapers/ntis.py` 작성 (`fetch_all()` + `main()` 구현)
2. `.github/workflows/ntis.yml` 추가 (bizinfo.yml 복사 후 module 이름 변경)
3. Supabase에 키 박기 (예: `ntd`, `nke`)
4. (sdm-collector 측) `parsers/ntis.py` 추가 + PARSER_REGISTRY 등록
5. 대시보드 자동으로 새 source 표시 (scrap_monitor 뷰 기반)

## 멀티 알림 허브 (alert.yml)

GitHub UI에서 [Run workflow] 누르면 dropdown:
- alert_type: deadline_imminent (마감 7일 이내)
- channels: email, sms, kakao, slack, desktop, webhook (콤마 구분)
- recipients: 받는 사람 (이메일 등, 콤마 구분)

향후 cron 추가 시 정기 알림 자동화. 신규 채널은 `notifiers/{채널}.py` 추가.

## 대시보드 접속

GitHub Pages 활성화 후:
```
https://luka-lloris.github.io/sdm-scrap/
```

다크/블루 톤. Chart.js로 7일 추이 그래프. 모바일 반응형.

## 운영 점검

- Supabase에서 `opportunities_raw` 테이블에 raw 들어가는지
- `scrap_monitor` 뷰 결과 확인
- GitHub Actions 로그에서 `[Bizinfo]` `[G2B]` 키워드 검색
- `scrap_monitor`의 `last_scrap_at`이 12시간 이상 안 갱신되면 워크플로 점검
