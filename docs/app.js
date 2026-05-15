// ẞDM Scrap Monitor — Frontend
// data.json 읽고 차트·표 렌더링

const SOURCE_LABELS = {
    bizinfo: "기업마당",
    g2b: "나라장터",
    ntis: "NTIS",
    kised: "창업진흥원",
    kosme: "중기벤처공단",
    nipa: "정보통신산업진흥원",
};

let trendChart = null;

// ------------------------------------------------------------
// 시간 포맷
// ------------------------------------------------------------
function formatTime(iso) {
    if (!iso) return "—";
    try {
        const d = new Date(iso);
        const now = new Date();
        const diff = (now - d) / 1000;  // 초
        
        if (diff < 60) return `${Math.floor(diff)}초 전`;
        if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
        return `${Math.floor(diff / 86400)}일 전`;
    } catch {
        return "—";
    }
}

function getTimestampClass(iso) {
    if (!iso) return "dead";
    const diff = (new Date() - new Date(iso)) / 1000 / 3600;  // 시간
    if (diff < 12) return "recent";
    if (diff < 36) return "stale";
    return "dead";
}

// ------------------------------------------------------------
// 데이터 fetch
// ------------------------------------------------------------
async function loadData() {
    try {
        const resp = await fetch(`data.json?t=${Date.now()}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (err) {
        console.error("[loadData] failed:", err);
        return null;
    }
}

// ------------------------------------------------------------
// 소스 테이블 렌더
// ------------------------------------------------------------
function renderSources(sources) {
    const tbody = document.getElementById("sources-tbody");
    if (!sources || sources.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="empty">아직 수집 데이터 없음</td></tr>`;
        return;
    }
    
    tbody.innerHTML = sources.map(s => {
        const label = SOURCE_LABELS[s.source_key] || s.source_key;
        const errClass = (s.error_count > 0) ? "error" : (s.error_count === 0 ? "zero" : "");
        const pendingClass = (s.pending_count > 0) ? "warning" : "zero";
        const scrapClass = getTimestampClass(s.last_scrap_at);
        const collectClass = getTimestampClass(s.last_collect_at);
        
        return `
            <tr>
                <td class="source-name">${label}<br><span style="color:var(--text-dim);font-size:11px;font-weight:400">${s.source_key}</span></td>
                <td class="num">${(s.last_24h_count ?? 0).toLocaleString()}</td>
                <td class="num ${pendingClass}">${(s.pending_count ?? 0).toLocaleString()}</td>
                <td class="num ${(s.processed_count > 0) ? '' : 'zero'}">${(s.processed_count ?? 0).toLocaleString()}</td>
                <td class="num ${errClass}">${(s.error_count ?? 0).toLocaleString()}</td>
                <td class="num">${(s.total_count ?? 0).toLocaleString()}</td>
                <td class="timestamp ${scrapClass}">${formatTime(s.last_scrap_at)}</td>
                <td class="timestamp ${collectClass}">${formatTime(s.last_collect_at)}</td>
            </tr>
        `;
    }).join("");
}

// ------------------------------------------------------------
// 7일 추이 차트
// ------------------------------------------------------------
function renderChart(trend) {
    const ctx = document.getElementById("trend-chart");
    if (!ctx) return;
    
    if (trendChart) {
        trendChart.destroy();
    }
    
    if (!trend || trend.length === 0) {
        ctx.getContext("2d").font = "14px sans-serif";
        ctx.getContext("2d").fillStyle = "#7a8aae";
        ctx.getContext("2d").fillText("데이터 없음", 20, 50);
        return;
    }
    
    // source_key별 그룹핑
    const sources = [...new Set(trend.map(t => t.source_key))];
    const dates = [...new Set(trend.map(t => t.date))].sort();
    
    const palette = {
        bizinfo: "#4a90e2",
        g2b: "#51cf66",
        ntis: "#ffd43b",
        kised: "#ff8787",
        kosme: "#a78bfa",
        nipa: "#fb923c",
    };
    
    const datasets = sources.map(src => {
        const data = dates.map(d => {
            const found = trend.find(t => t.source_key === src && t.date === d);
            return found ? found.count : 0;
        });
        return {
            label: SOURCE_LABELS[src] || src,
            data: data,
            borderColor: palette[src] || "#c5d4f5",
            backgroundColor: (palette[src] || "#c5d4f5") + "20",
            tension: 0.3,
            borderWidth: 2,
        };
    });
    
    trendChart = new Chart(ctx, {
        type: "line",
        data: { labels: dates, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: {
                        color: "#c5d4f5",
                        font: { size: 12 },
                    },
                },
                tooltip: {
                    backgroundColor: "#0a0e1a",
                    titleColor: "#e8efff",
                    bodyColor: "#c5d4f5",
                    borderColor: "#2a3450",
                    borderWidth: 1,
                },
            },
            scales: {
                x: {
                    ticks: { color: "#7a8aae" },
                    grid: { color: "#2a3450" },
                },
                y: {
                    ticks: { color: "#7a8aae" },
                    grid: { color: "#2a3450" },
                    beginAtZero: true,
                },
            },
        },
    });
}

// ------------------------------------------------------------
// 에러 렌더
// ------------------------------------------------------------
function renderErrors(errors) {
    const div = document.getElementById("errors-list");
    if (!errors || errors.length === 0) {
        div.innerHTML = `<p class="empty">에러 없음</p>`;
        return;
    }
    
    div.innerHTML = errors.map(e => {
        const label = SOURCE_LABELS[e.source_key] || e.source_key;
        const ts = formatTime(e.fetched_at);
        const msg = (e.error_message || "(no message)").slice(0, 200);
        return `
            <div class="error-item">
                <span class="src">[${label}]</span>
                <span class="ts">${ts}</span>
                <span class="msg">${escapeHtml(msg)}</span>
            </div>
        `;
    }).join("");
}

function escapeHtml(s) {
    return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

// ------------------------------------------------------------
// 메인 갱신
// ------------------------------------------------------------
async function refresh() {
    const btn = document.getElementById("refresh-btn");
    if (btn) btn.disabled = true;
    
    const data = await loadData();
    
    if (!data) {
        document.getElementById("generated-at").textContent = "데이터 로드 실패";
        if (btn) btn.disabled = false;
        return;
    }
    
    document.getElementById("generated-at").textContent = 
        `갱신: ${data.generated_at ? new Date(data.generated_at).toLocaleString('ko-KR') : '—'}`;
    
    renderSources(data.sources);
    renderChart(data.trend_7d);
    renderErrors(data.recent_errors);
    
    if (btn) btn.disabled = false;
}

// ------------------------------------------------------------
// 초기화
// ------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
    refresh();
    
    document.getElementById("refresh-btn")?.addEventListener("click", refresh);
});
