// 전역 상태 관리 객체
const state = {
    metadata: null,
    viewMode: localStorage.getItem('view_mode') || (window.innerWidth < 768 ? 'mobile' : 'pc'),
    filters: {
        keyword: '',
        startYear: 2016,
        endYear: 2025,
        sido: '',
        sigungu: '',
        causeCategory: '',
        locationCategory: '',
        hasDeaths: false,
    },
    sort: {
        sortBy: 'fire_datetime',
        sortOrder: 'desc'
    },
    pagination: {
        page: 1,
        pageSize: 20,
        totalCount: 0,
        totalPages: 1
    },
    apiConfig: {
        apiKey: localStorage.getItem('fire_api_key') || '',
        mode: localStorage.getItem('fire_api_mode') || 'demo'
    },
    currentItems: [],
    charts: {
        yearly: null,
        cause: null,
        sido: null,
        location: null
    }
};

// DOM 로드 완료 후 초기화
document.addEventListener('DOMContentLoaded', async () => {
    try {
        initViewMode();
    } catch (e) {
        console.error('initViewMode error:', e);
    }

    try {
        initApiConfigUI();
    } catch (e) {
        console.error('initApiConfigUI error:', e);
    }

    try {
        initFilterEventListeners();
    } catch (e) {
        console.error('initFilterEventListeners error:', e);
    }

    try {
        await loadMetadata();
    } catch (e) {
        console.error('loadMetadata error:', e);
    }

    try {
        await refreshAllData();
    } catch (e) {
        console.error('refreshAllData error:', e);
    }
});

// [모드 전환] PC 모드 vs 스마트폰 모드
function initViewMode() {
    setViewMode(state.viewMode, false);
}

function setViewMode(mode, refresh = true) {
    state.viewMode = mode;
    localStorage.setItem('view_mode', mode);

    const btnMobile = document.getElementById('btnModeMobile');
    const btnPc = document.getElementById('btnModePc');
    const btnMobileShort = document.getElementById('btnModeMobileShort');
    const btnPcShort = document.getElementById('btnModePcShort');

    const tableView = document.getElementById('desktopTableView');
    const cardsView = document.getElementById('mobileCardsContainer');

    if (mode === 'mobile') {
        // 모바일 모드 활성화
        if (btnMobile) {
            btnMobile.className = 'flex items-center space-x-1.5 px-3 py-1 rounded-lg text-xs font-semibold bg-red-600 text-white shadow-sm transition';
        }
        if (btnPc) {
            btnPc.className = 'flex items-center space-x-1.5 px-3 py-1 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition';
        }
        if (btnMobileShort) {
            btnMobileShort.className = 'px-2 py-1 text-[11px] rounded-md font-semibold bg-red-600 text-white transition';
        }
        if (btnPcShort) {
            btnPcShort.className = 'px-2 py-1 text-[11px] rounded-md font-semibold text-slate-400 hover:text-white transition';
        }

        if (tableView) tableView.classList.add('hidden');
        if (cardsView) cardsView.classList.remove('hidden');
        document.body.classList.add('mobile-optimized');
    } else {
        // PC 모드 활성화
        if (btnMobile) {
            btnMobile.className = 'flex items-center space-x-1.5 px-3 py-1 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition';
        }
        if (btnPc) {
            btnPc.className = 'flex items-center space-x-1.5 px-3 py-1 rounded-lg text-xs font-semibold bg-red-600 text-white shadow-sm transition';
        }
        if (btnMobileShort) {
            btnMobileShort.className = 'px-2 py-1 text-[11px] rounded-md font-semibold text-slate-400 hover:text-white transition';
        }
        if (btnPcShort) {
            btnPcShort.className = 'px-2 py-1 text-[11px] rounded-md font-semibold bg-red-600 text-white transition';
        }

        if (tableView) tableView.classList.remove('hidden');
        if (cardsView) cardsView.classList.add('hidden');
        document.body.classList.remove('mobile-optimized');
    }

    if (refresh && state.currentItems.length > 0) {
        renderTable(state.currentItems);
    }
}

// 1. API 및 모드 설정 초기화
function initApiConfigUI() {
    const apiKeyInput = document.getElementById('apiKeyInput');
    const useRealApiCheckbox = document.getElementById('useRealApiCheckbox');
    if (apiKeyInput) apiKeyInput.value = state.apiConfig.apiKey;
    if (useRealApiCheckbox) useRealApiCheckbox.checked = (state.apiConfig.mode === 'live');
    updateModeBadge();
}

function updateModeBadge() {
    const badge = document.getElementById('modeBadge');
    const text = document.getElementById('modeText');
    if (state.apiConfig.mode === 'live' && state.apiConfig.apiKey) {
        badge.className = 'flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-medium bg-amber-950/70 text-amber-400 border border-amber-800/50';
        text.innerText = '공공데이터포털 실시간 API 모드';
    } else {
        badge.className = 'flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-950/70 text-emerald-400 border border-emerald-800/50';
        text.innerText = '10개년 통합 데이터셋 모드 (2017~2026)';
    }
}

// 2. 메타데이터 로드
async function loadMetadata() {
    try {
        const res = await fetch('/api/meta');
        const data = await res.json();
        state.metadata = data;

        // 연도 드롭다운 구성
        const startYearSel = document.getElementById('startYearSelect');
        const endYearSel = document.getElementById('endYearSelect');
        startYearSel.innerHTML = '';
        endYearSel.innerHTML = '';

        data.years.forEach(y => {
            const label = (y === 2026) ? `${y}년 (현재)` : `${y}년`;
            const opt1 = new Option(label, y);
            const opt2 = new Option(label, y);
            if (y === 2016) opt1.selected = true;
            if (y === 2026) opt2.selected = true;
            startYearSel.add(opt1);
            endYearSel.add(opt2);
        });

        // 시/도 드롭다운 구성
        const sidoSel = document.getElementById('sidoSelect');
        sidoSel.innerHTML = '<option value="">전체 시·도</option>';
        Object.keys(data.regions).forEach(sido => {
            sidoSel.add(new Option(sido, sido));
        });

        // 발화원인 드롭다운
        const causeSel = document.getElementById('causeSelect');
        causeSel.innerHTML = '<option value="">전체 발화원인</option>';
        data.causes.forEach(cause => {
            causeSel.add(new Option(cause, cause));
        });

        // 장소분류 드롭다운
        const locSel = document.getElementById('locationSelect');
        locSel.innerHTML = '<option value="">전체 발생장소</option>';
        data.locations.forEach(loc => {
            locSel.add(new Option(loc, loc));
        });

    } catch (err) {
        console.error('메타데이터 로드 실패:', err);
    }
}

// 3. 필터 이벤트 리스너 등록
function initFilterEventListeners() {
    // 키워드 엔터 검색
    const kwInput = document.getElementById('keywordInput');
    kwInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            applyFilters(1);
        }
    });

    // 시작/종료 연도 변경
    document.getElementById('startYearSelect').addEventListener('change', () => applyFilters(1));
    document.getElementById('endYearSelect').addEventListener('change', () => applyFilters(1));
    document.getElementById('sigunguSelect').addEventListener('change', () => applyFilters(1));
    document.getElementById('causeSelect').addEventListener('change', () => applyFilters(1));
    document.getElementById('locationSelect').addEventListener('change', () => applyFilters(1));
}

// 시도 변경 시 시군구 동적 갱신
function onSidoChange() {
    const sido = document.getElementById('sidoSelect').value;
    const sigunguSel = document.getElementById('sigunguSelect');
    sigunguSel.innerHTML = '<option value="">전체 시·군·구</option>';

    if (sido && state.metadata && state.metadata.regions[sido]) {
        state.metadata.regions[sido].forEach(sgg => {
            sigunguSel.add(new Option(sgg, sgg));
        });
    }
    applyFilters(1);
}

// 연도 프리셋 버튼
function setYearPreset(preset) {
    document.querySelectorAll('.year-preset-btn').forEach(btn => {
        if (btn.dataset.val === String(preset)) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    const startSel = document.getElementById('startYearSelect');
    const endSel = document.getElementById('endYearSelect');

    ensureYearOption(startSel, 2026);
    ensureYearOption(endSel, 2026);

    if (preset === 'all') {
        startSel.value = "2016";
        endSel.value = "2026";
    } else if (preset === 'recent3') {
        startSel.value = "2024";
        endSel.value = "2026";
    } else if (preset === 'recent5') {
        startSel.value = "2022";
        endSel.value = "2026";
    } else {
        startSel.value = String(preset);
        endSel.value = String(preset);
    }

    applyFilters(1);
}

function ensureYearOption(selectEl, year) {
    if (!selectEl) return;
    let found = false;
    for (let i = 0; i < selectEl.options.length; i++) {
        if (selectEl.options[i].value === String(year)) {
            found = true;
            break;
        }
    }
    if (!found) {
        const opt = document.createElement('option');
        opt.value = String(year);
        opt.text = `${year}년 (현재)`;
        selectEl.appendChild(opt);
    }
}

// 필터 파라미터 빌드
function buildQueryParams(page = 1) {
    const params = new URLSearchParams();
    
    const kw = document.getElementById('keywordInput').value.trim();
    if (kw) params.append('keyword', kw);

    const sYear = document.getElementById('startYearSelect').value;
    const eYear = document.getElementById('endYearSelect').value;
    if (sYear) params.append('start_year', sYear);
    if (eYear) params.append('end_year', eYear);

    const sido = document.getElementById('sidoSelect').value;
    if (sido) params.append('sido', sido);

    const sgg = document.getElementById('sigunguSelect').value;
    if (sgg) params.append('sigungu', sgg);

    const cause = document.getElementById('causeSelect').value;
    if (cause) params.append('cause_category', cause);

    const loc = document.getElementById('locationSelect').value;
    if (loc) params.append('location_category', loc);

    const hasDeaths = document.getElementById('hasDeathsCheckbox').checked;
    if (hasDeaths) params.append('has_deaths', 'true');

    params.append('sort_by', state.sort.sortBy);
    params.append('sort_order', state.sort.sortOrder);
    params.append('page', page);
    params.append('page_size', state.pagination.pageSize);

    if (state.apiConfig.mode === 'live' && state.apiConfig.apiKey) {
        params.append('mode', 'live');
        params.append('api_key', state.apiConfig.apiKey);
    } else {
        params.append('mode', 'demo');
    }

    return params;
}

// 4. 필터 적용 및 전체 데이터 갱신
async function applyFilters(page = 1) {
    state.pagination.page = page;
    showLoading(true);
    try {
        await Promise.all([
            fetchTableData(page),
            fetchStatsData()
        ]);
    } catch (e) {
        console.error('데이터 조회 오류:', e);
    } finally {
        showLoading(false);
    }
}

async function refreshAllData() {
    await applyFilters(1);
}

// 5. 화재 리스트 데이터 조회
async function fetchTableData(page = 1) {
    const params = buildQueryParams(page);
    const res = await fetch(`/api/fire-data?${params.toString()}`);
    const data = await res.json();

    state.currentItems = data.items;
    state.pagination.totalCount = data.total_count;
    state.pagination.totalPages = data.total_pages;
    state.pagination.page = data.page;

    document.getElementById('resultCountBadge').innerText = `검색결과: ${data.total_count.toLocaleString()}건`;

    // 필터 조건에 따른 상세 분석 배지 렌더링 (시·도, 시·군·구, 발화원인, 발생장소)
    const causeBadge = document.getElementById('causePercentageBadge');
    const causeText = document.getElementById('causePercentageText');
    const sidoVal = document.getElementById('sidoSelect').value;
    const sggVal = document.getElementById('sigunguSelect').value;
    const causeVal = document.getElementById('causeSelect').value;
    const locVal = document.getElementById('locationSelect').value;

    const hasFilter = sidoVal || sggVal || causeVal || locVal;

    if (hasFilter && data.national_total_fires) {
        causeBadge.classList.remove('hidden');
        causeBadge.classList.add('inline-flex');
        
        let label = '';
        if (sidoVal && !sggVal && !causeVal && !locVal) {
            // 시·도만 선택된 경우: 전국 대비 % 점유율
            label = `[${sidoVal}] ${data.total_count.toLocaleString()}건 (전국 ${data.national_total_fires.toLocaleString()}건 중 ${data.sido_percentage}%)`;
        } else if (sidoVal && sggVal && !causeVal && !locVal) {
            // 시·도 + 시·군·구 선택된 경우: 해당 시도 내 % 점유율
            label = `[${sidoVal} ${sggVal}] ${data.total_count.toLocaleString()}건 (${sidoVal} 전체 ${data.sido_total_fires.toLocaleString()}건 중 ${data.sigungu_percentage}%)`;
        } else if (causeVal && locVal) {
            label = `[${causeVal} & ${locVal}] ${data.total_count.toLocaleString()}건 (해당 지역 ${data.region_total_fires.toLocaleString()}건 중 ${data.combined_percentage}%)`;
        } else if (causeVal) {
            label = `[${causeVal}] ${data.total_count.toLocaleString()}건 (해당 지역 ${data.region_total_fires.toLocaleString()}건 중 ${data.cause_percentage}%)`;
        } else if (locVal) {
            label = `[${locVal}] ${data.total_count.toLocaleString()}건 (해당 지역 ${data.region_total_fires.toLocaleString()}건 중 ${data.location_percentage}%)`;
        }
        causeText.innerText = label;
    } else {
        causeBadge.classList.add('hidden');
        causeBadge.classList.remove('inline-flex');
    }

    renderTable(data.items);
    renderPagination();
    updateSortHeaderIcons();
}

// 6. 통계 데이터 조회 및 KPI & 차트 렌더링
async function fetchStatsData() {
    const params = buildQueryParams(1);
    const res = await fetch(`/api/stats?${params.toString()}`);
    const stats = await res.json();

    renderKPIs(stats);
    renderCharts(stats);
}

// 7. KPI 카드 렌더링
function renderKPIs(stats) {
    document.getElementById('kpiTotalFires').innerText = stats.total_fires.toLocaleString();
    document.getElementById('kpiCasualties').innerText = stats.total_casualties.toLocaleString();
    document.getElementById('kpiDeaths').innerText = stats.total_deaths.toLocaleString();
    document.getElementById('kpiInjuries').innerText = stats.total_injuries.toLocaleString();
    
    // 금액 포맷 (천원 단위 -> 억원/만원 환산)
    const cheonwon = stats.total_property_damage_cheonwon;
    const won = cheonwon * 1000;
    let damageText = '-';
    if (won >= 100000000) {
        const eok = Math.floor(won / 100000000);
        const man = Math.floor((won % 100000000) / 10000);
        damageText = man > 0 ? `${eok.toLocaleString()}억 ${man.toLocaleString()}만` : `${eok.toLocaleString()}억원`;
    } else {
        const man = Math.floor(won / 10000);
        damageText = `${man.toLocaleString()}만원`;
    }
    document.getElementById('kpiDamage').innerText = damageText;

    const sYear = document.getElementById('startYearSelect').value;
    const eYear = document.getElementById('endYearSelect').value;
    document.getElementById('kpiFiresSub').innerText = `${sYear}년 ~ ${eYear}년 집계`;
}

// 8. 테이블 렌더링
function renderTable(items) {
    const tbody = document.getElementById('fireDataTableBody');
    tbody.innerHTML = '';

    if (!items || items.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" class="py-12 text-center text-slate-500">
                    <div class="flex flex-col items-center space-y-2">
                        <i class="fa-regular fa-folder-open text-3xl text-slate-600"></i>
                        <span>해당 조건과 일치하는 화재 발생 기록이 없습니다.</span>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    items.forEach(item => {
        const tr = document.createElement('tr');
        tr.className = 'border-b border-slate-800/80 hover:bg-slate-800/50 transition';

        // 사상자 뱃지
        let casualtyBadge = '';
        if (item.deaths > 0) {
            casualtyBadge = `<span class="px-2 py-0.5 rounded text-[11px] font-bold badge-death">사망 ${item.deaths} / 부상 ${item.injuries}</span>`;
        } else if (item.injuries > 0) {
            casualtyBadge = `<span class="px-2 py-0.5 rounded text-[11px] font-semibold badge-injury">부상 ${item.injuries}명</span>`;
        } else {
            casualtyBadge = `<span class="px-2 py-0.5 rounded text-[11px] badge-safe">인명피해 없음</span>`;
        }

        // 재산피해액 포맷팅
        const damageWon = item.property_damage * 1000;
        let formattedDamage = '';
        if (damageWon >= 100000000) {
            formattedDamage = `${(damageWon / 100000000).toFixed(1)}억원`;
        } else {
            formattedDamage = `${Math.round(damageWon / 10000).toLocaleString()}만원`;
        }

        const isRt = item.is_realtime || item.year === 2026;
        const rtBadge = isRt ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-950/90 text-rose-300 border border-rose-600/80 mr-1 inline-flex items-center gap-0.5"><i class="fa-solid fa-bolt text-amber-400 text-[9px] animate-pulse"></i>실시간</span>` : '';

        tr.innerHTML = `
            <td class="py-3 px-4 font-mono text-slate-400 text-[11px]">${rtBadge}${item.id}</td>
            <td class="py-3 px-4 font-medium text-slate-200">
                <div class="flex flex-col">
                    <span>${item.fire_date}</span>
                    <span class="text-[10px] text-slate-400">${item.fire_time}</span>
                </div>
            </td>
            <td class="py-3 px-4 text-slate-300">
                <div class="font-medium">${item.sido} ${item.sigungu}</div>
                <div class="text-[10px] text-slate-500">${item.eupmyeondong || ''}</div>
            </td>
            <td class="py-3 px-4 text-slate-300">
                <span class="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[11px] border border-slate-700">${item.location_category}</span>
                <div class="text-[10px] text-slate-400 mt-0.5">${item.location_detail}</div>
            </td>
            <td class="py-3 px-4">
                <span class="text-red-400 font-medium">${item.cause_category}</span>
                <div class="text-[10px] text-slate-400">${item.cause_detail}</div>
            </td>
            <td class="py-3 px-4">${casualtyBadge}</td>
            <td class="py-3 px-4 font-semibold text-yellow-400">${formattedDamage}</td>
            <td class="py-3 px-4 text-slate-300 font-mono">${item.suppression_minutes}분</td>
            <td class="py-3 px-4 text-center">
                <button onclick="openDetailModal('${item.id}')" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 hover:border-slate-500 text-[11px] transition">
                    상세
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });

    renderMobileCards(items);
}

// 8-1. 스마트폰 모드 전용 카드 목록 렌더링
function renderMobileCards(items) {
    const container = document.getElementById('mobileCardsContainer');
    if (!container) return;
    container.innerHTML = '';

    if (!items || items.length === 0) {
        container.innerHTML = `
            <div class="py-8 text-center text-slate-500 text-xs">
                <i class="fa-regular fa-folder-open text-2xl mb-1 text-slate-600 block"></i>
                일치하는 화재 발생 기록이 없습니다.
            </div>
        `;
        return;
    }

    items.forEach(item => {
        const card = document.createElement('div');
        card.className = 'bg-slate-900/80 border border-slate-700/80 rounded-xl p-3.5 space-y-2.5 shadow-sm active:bg-slate-800/80 transition cursor-pointer';
        card.onclick = () => openDetailModal(item.id);

        let casualtyBadge = '';
        if (item.deaths > 0) {
            casualtyBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold badge-death">사망 ${item.deaths} / 부상 ${item.injuries}</span>`;
        } else if (item.injuries > 0) {
            casualtyBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-semibold badge-injury">부상 ${item.injuries}명</span>`;
        } else {
            casualtyBadge = `<span class="px-2 py-0.5 rounded text-[10px] badge-safe">인명피해 없음</span>`;
        }

        const damageWon = item.property_damage * 1000;
        let formattedDamage = '';
        if (damageWon >= 100000000) {
            formattedDamage = `${(damageWon / 100000000).toFixed(1)}억원`;
        } else {
            formattedDamage = `${Math.round(damageWon / 10000).toLocaleString()}만원`;
        }

        const isRt = item.is_realtime || item.year === 2026;
        const rtBadge = isRt ? `<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-rose-950/90 text-rose-300 border border-rose-600/80 mr-1 inline-flex items-center gap-0.5"><i class="fa-solid fa-bolt text-amber-400 text-[8px] animate-pulse"></i>실시간</span>` : '';

        card.innerHTML = `
            <div class="flex items-center justify-between text-xs">
                <div class="flex items-center space-x-1.5 font-bold text-white">
                    ${rtBadge}
                    <i class="fa-solid fa-calendar-day text-slate-400 text-[10px]"></i>
                    <span>${item.fire_datetime}</span>
                </div>
                <span class="font-mono text-[10px] text-slate-500">${item.id}</span>
            </div>

            <div class="flex items-center justify-between text-xs border-y border-slate-800 py-1.5">
                <div class="flex items-center space-x-1.5 text-slate-200">
                    <i class="fa-solid fa-location-dot text-red-400 text-xs"></i>
                    <span class="font-semibold">${item.sido} ${item.sigungu}</span>
                    <span class="text-slate-400 text-[11px]">${item.eupmyeondong || ''}</span>
                </div>
                <span class="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[10px] border border-slate-700">
                    ${item.location_category}
                </span>
            </div>

            <div class="flex items-center justify-between text-xs">
                <div class="flex items-center space-x-1">
                    <span class="text-red-400 font-bold">🔥 ${item.cause_category}</span>
                    <span class="text-slate-400 text-[11px]">(${item.cause_detail})</span>
                </div>
                <div>${casualtyBadge}</div>
            </div>

            <div class="flex items-center justify-between text-[11px] pt-1 text-slate-400">
                <div class="flex items-center space-x-3">
                    <span>피해: <strong class="text-yellow-400 font-semibold">${formattedDamage}</strong></span>
                    <span>진압: <strong class="text-slate-200">${item.suppression_minutes}분</strong></span>
                </div>
                <span class="text-xs text-red-400 font-semibold flex items-center gap-0.5">
                    상세보기 <i class="fa-solid fa-chevron-right text-[10px]"></i>
                </span>
            </div>
        `;
        container.appendChild(card);
    });
}

// 9. 페이지네이션 렌더링
function renderPagination() {
    const { page, totalPages, totalCount, pageSize } = state.pagination;
    document.getElementById('pageTotalCount').innerText = totalCount.toLocaleString();

    const startIdx = totalCount === 0 ? 0 : (page - 1) * pageSize + 1;
    const endIdx = Math.min(page * pageSize, totalCount);
    document.getElementById('pageCurrentRange').innerText = `${startIdx.toLocaleString()} - ${endIdx.toLocaleString()}`;

    const nav = document.getElementById('paginationNav');
    nav.innerHTML = '';

    if (totalPages <= 1) return;

    // 이전 버튼
    const prevBtn = document.createElement('button');
    prevBtn.className = `px-2.5 py-1 rounded-lg text-xs font-medium border border-slate-700 ${page === 1 ? 'text-slate-600 cursor-not-allowed bg-slate-900' : 'text-slate-300 hover:bg-slate-800 bg-slate-900'}`;
    prevBtn.innerHTML = '<i class="fa-solid fa-chevron-left"></i>';
    prevBtn.disabled = (page === 1);
    prevBtn.onclick = () => applyFilters(page - 1);
    nav.appendChild(prevBtn);

    // 페이지 번호 계산 (현재 페이지 주변 5개)
    let startPage = Math.max(1, page - 2);
    let endPage = Math.min(totalPages, startPage + 4);
    if (endPage - startPage < 4) {
        startPage = Math.max(1, endPage - 4);
    }

    for (let p = startPage; p <= endPage; p++) {
        const btn = document.createElement('button');
        const isActive = (p === page);
        btn.className = `px-3 py-1 rounded-lg text-xs font-medium border transition ${isActive ? 'bg-red-600 text-white border-red-500 shadow-sm' : 'bg-slate-900 text-slate-300 border-slate-700 hover:bg-slate-800'}`;
        btn.innerText = p;
        btn.onclick = () => applyFilters(p);
        nav.appendChild(btn);
    }

    // 다음 버튼
    const nextBtn = document.createElement('button');
    nextBtn.className = `px-2.5 py-1 rounded-lg text-xs font-medium border border-slate-700 ${page === totalPages ? 'text-slate-600 cursor-not-allowed bg-slate-900' : 'text-slate-300 hover:bg-slate-800 bg-slate-900'}`;
    nextBtn.innerHTML = '<i class="fa-solid fa-chevron-right"></i>';
    nextBtn.disabled = (page === totalPages);
    nextBtn.onclick = () => applyFilters(page + 1);
    nav.appendChild(nextBtn);
}

// 10. 정렬 및 테이블 헤더 정렬 클릭 이벤트
function clickSortHeader(field) {
    if (state.sort.sortBy === field) {
        // 이미 선택된 필드면 정렬 순서 토글
        state.sort.sortOrder = (state.sort.sortOrder === 'asc') ? 'desc' : 'asc';
    } else {
        state.sort.sortBy = field;
        state.sort.sortOrder = 'desc'; // 기본 내림차순
    }

    document.getElementById('sortBySelect').value = field;
    updateSortOrderButtonUI();
    applyFilters(1);
}

function toggleSortOrder() {
    state.sort.sortOrder = (state.sort.sortOrder === 'asc') ? 'desc' : 'asc';
    updateSortOrderButtonUI();
    applyFilters(1);
}

function updateSortOrderButtonUI() {
    const isDesc = (state.sort.sortOrder === 'desc');
    document.getElementById('sortOrderText').innerText = isDesc ? '내림차순 (DESC)' : '오름차순 (ASC)';
    document.getElementById('sortOrderIcon').className = isDesc ? 'fa-solid fa-arrow-down text-red-400' : 'fa-solid fa-arrow-up text-red-400';
    updateSortHeaderIcons();
}

function updateSortHeaderIcons() {
    const fields = ['fire_datetime', 'casualties', 'property_damage', 'suppression_minutes'];
    fields.forEach(f => {
        const icon = document.getElementById(`thIcon-${f}`);
        if (!icon) return;
        if (state.sort.sortBy === f) {
            icon.className = state.sort.sortOrder === 'desc' ? 'fa-solid fa-sort-down text-red-400 text-sm' : 'fa-solid fa-sort-up text-red-400 text-sm';
        } else {
            icon.className = 'fa-solid fa-sort text-slate-600 group-hover:text-red-400';
        }
    });
}

function changePageSize() {
    state.pagination.pageSize = parseInt(document.getElementById('pageSizeSelect').value, 10);
    applyFilters(1);
}

function resetFilters() {
    document.getElementById('keywordInput').value = '';
    document.getElementById('startYearSelect').value = 2016;
    document.getElementById('endYearSelect').value = 2025;
    document.getElementById('sidoSelect').value = '';
    document.getElementById('sigunguSelect').innerHTML = '<option value="">전체 시·군·구</option>';
    document.getElementById('causeSelect').value = '';
    document.getElementById('locationSelect').value = '';
    document.getElementById('hasDeathsCheckbox').checked = false;
    document.getElementById('sortBySelect').value = 'fire_datetime';
    
    state.sort.sortBy = 'fire_datetime';
    state.sort.sortOrder = 'desc';

    document.querySelectorAll('.year-preset-btn').forEach(btn => {
        if (btn.dataset.val === 'all') btn.classList.add('active');
        else btn.classList.remove('active');
    });

    updateSortOrderButtonUI();
    applyFilters(1);
}

// 11. Chart.js 시각화 렌더링
function renderCharts(stats) {
    if (typeof Chart === 'undefined') {
        console.warn('Chart.js 라이브러리가 아직 로드되지 않았습니다.');
        setTimeout(() => renderCharts(stats), 300);
        return;
    }
    if (!stats) return;

    try {
        if (stats.yearly_trend) renderYearlyTrendChart(stats.yearly_trend);
    } catch (e) {
        console.error('연도별 추이 차트 렌더링 실패:', e);
    }

    try {
        if (stats.cause_breakdown) renderCauseDonutChart(stats.cause_breakdown);
    } catch (e) {
        console.error('발화원인 차트 렌더링 실패:', e);
    }

    try {
        if (stats.sido_ranking) renderSidoBarChart(stats.sido_ranking);
    } catch (e) {
        console.error('시도별 차트 렌더링 실패:', e);
    }

    try {
        if (stats.location_breakdown) renderLocationDonutChart(stats.location_breakdown);
    } catch (e) {
        console.error('장소별 차트 렌더링 실패:', e);
    }
}

// (1) 10개년 연도별 발생 및 인명피해 추이 복합 차트
function renderYearlyTrendChart(trendData) {
    const canvas = document.getElementById('yearlyTrendChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const labels = trendData.map(d => `${d.year}년`);
    const fireCounts = trendData.map(d => d.count);
    const casualties = trendData.map(d => d.deaths + d.injuries);

    if (state.charts.yearly) {
        state.charts.yearly.destroy();
    }

    state.charts.yearly = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: '화재 발생 건수',
                    data: fireCounts,
                    backgroundColor: 'rgba(239, 68, 68, 0.7)',
                    borderColor: 'rgb(239, 68, 68)',
                    borderRadius: 6,
                    yAxisID: 'y'
                },
                {
                    label: '인명 피해(사상자수)',
                    data: casualties,
                    type: 'line',
                    borderColor: 'rgb(245, 158, 11)',
                    backgroundColor: 'rgba(245, 158, 11, 0.2)',
                    borderWidth: 2.5,
                    pointBackgroundColor: 'rgb(245, 158, 11)',
                    pointRadius: 4,
                    tension: 0.3,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { labels: { color: '#94a3b8', font: { size: 11 } } },
                tooltip: { backgroundColor: '#0f172a', titleColor: '#fff', bodyColor: '#cbd5e1' }
            },
            scales: {
                x: { grid: { color: 'rgba(51, 65, 85, 0.4)' }, ticks: { color: '#94a3b8', font: { size: 10 } } },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    grid: { color: 'rgba(51, 65, 85, 0.4)' },
                    ticks: { color: '#94a3b8', font: { size: 10 } },
                    title: { display: true, text: '건수', color: '#64748b', font: { size: 10 } }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    grid: { drawOnChartArea: false },
                    ticks: { color: '#f59e0b', font: { size: 10 } },
                    title: { display: true, text: '사상자(명)', color: '#f59e0b', font: { size: 10 } }
                }
            }
        }
    });
}

// (2) 발화원인 도넛 차트
function renderCauseDonutChart(causeData) {
    const canvas = document.getElementById('causeDonutChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const topCauses = causeData.slice(0, 6);
    const labels = topCauses.map(c => `${c.cause} (${c.percentage}%)`);
    const counts = topCauses.map(c => c.count);

    if (state.charts.cause) {
        state.charts.cause.destroy();
    }

    state.charts.cause = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: counts,
                backgroundColor: [
                    '#ef4444', '#f97316', '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6'
                ],
                borderWidth: 2,
                borderColor: '#0f172a'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { 
                    position: 'bottom', 
                    labels: { 
                        color: '#cbd5e1', 
                        font: { size: 11, weight: '500' }, 
                        boxWidth: 12,
                        padding: 8
                    } 
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const val = context.raw || 0;
                            const item = topCauses[context.dataIndex];
                            const pct = item?.percentage || 0;
                            const name = item?.cause || context.label;
                            return ` ${name}: ${val.toLocaleString()}건 (${pct}%)`;
                        }
                    }
                }
            },
            cutout: '65%'
        }
    });
}

// (3) 시도별 발생 건수 바 차트
function renderSidoBarChart(sidoData) {
    const canvas = document.getElementById('sidoBarChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const topSidos = sidoData.slice(0, 10);
    const labels = topSidos.map(s => s.sido);
    const counts = topSidos.map(s => s.count);

    if (state.charts.sido) {
        state.charts.sido.destroy();
    }

    state.charts.sido = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: '화재 건수',
                data: counts,
                backgroundColor: 'rgba(59, 130, 246, 0.7)',
                borderColor: 'rgb(59, 130, 246)',
                borderRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: { grid: { display: false }, ticks: { color: '#94a3b8', font: { size: 10 } } },
                y: { grid: { color: 'rgba(51, 65, 85, 0.4)' }, ticks: { color: '#94a3b8', font: { size: 10 } } }
            }
        }
    });
}

// (4) 장소별 도넛 차트
function renderLocationDonutChart(locData) {
    const canvas = document.getElementById('locationDonutChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const topLocs = locData.slice(0, 5);
    const labels = topLocs.map(l => `${l.location} (${l.percentage}%)`);
    const counts = topLocs.map(l => l.count);

    if (state.charts.location) {
        state.charts.location.destroy();
    }

    state.charts.location = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: labels,
            datasets: [{
                data: counts,
                backgroundColor: [
                    '#38bdf8', '#fbbf24', '#a855f7', '#ec4899', '#64748b'
                ],
                borderWidth: 2,
                borderColor: '#0f172a'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { 
                    position: 'bottom', 
                    labels: { 
                        color: '#cbd5e1', 
                        font: { size: 11, weight: '500' }, 
                        boxWidth: 12,
                        padding: 8
                    } 
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const val = context.raw || 0;
                            const item = topLocs[context.dataIndex];
                            const pct = item?.percentage || 0;
                            const name = item?.location || context.label;
                            return ` ${name}: ${val.toLocaleString()}건 (${pct}%)`;
                        }
                    }
                }
            }
        }
    });
}

// 12. 상세 모달 열기/닫기
function openDetailModal(id) {
    const item = state.currentItems.find(x => x.id === id);
    if (!item) return;

    document.getElementById('modalTitle').innerText = `[${item.sido} ${item.sigungu}] ${item.location_category} 화재 보고`;
    document.getElementById('modalSubTitle').innerText = `사건번호: ${item.id}`;
    document.getElementById('modalDatetime').innerText = item.fire_datetime;
    document.getElementById('modalLocation').innerText = `${item.sido} ${item.sigungu} ${item.eupmyeondong}`;
    document.getElementById('modalPlace').innerText = `${item.location_category} > ${item.location_detail}`;
    document.getElementById('modalCause').innerText = `${item.cause_category} (${item.cause_detail})`;
    document.getElementById('modalSuppression').innerText = `${item.suppression_minutes}분 소요`;
    document.getElementById('modalDispatch').innerText = `인력 ${item.dispatched_personnel}명 / 차량 ${item.dispatched_vehicles}대`;

    document.getElementById('modalDeaths').innerText = `${item.deaths}명`;
    document.getElementById('modalInjuries').innerText = `${item.injuries}명`;

    const won = item.property_damage * 1000;
    document.getElementById('modalDamage').innerText = `약 ${won.toLocaleString()}원`;
    document.getElementById('modalSummary').innerText = item.summary || '상세 개요가 등록되지 않았습니다.';

    document.getElementById('detailModal').classList.remove('hidden');
}

function closeDetailModal() {
    document.getElementById('detailModal').classList.add('hidden');
}

// 13. API 설정 모달 & 실시간 연결 진단
function openApiConfigModal() {
    const resBox = document.getElementById('apiTestResultBox');
    if (resBox) resBox.classList.add('hidden');
    document.getElementById('apiModal').classList.remove('hidden');
}

function closeApiConfigModal() {
    document.getElementById('apiModal').classList.add('hidden');
}

function onEndpointSelectChange() {
    const sel = document.getElementById('apiEndpointSelect').value;
    const customInput = document.getElementById('customUrlInput');
    if (sel === 'custom') {
        customInput.classList.remove('hidden');
    } else {
        customInput.classList.add('hidden');
    }
}

async function testApiConnection() {
    const key = document.getElementById('apiKeyInput').value.trim();
    const endpointSel = document.getElementById('apiEndpointSelect').value;
    const customUrl = (endpointSel === 'custom') ? document.getElementById('customUrlInput').value.trim() : endpointSel;
    const resBox = document.getElementById('apiTestResultBox');
    const spinner = document.getElementById('testApiSpinner');

    if (!key) {
        resBox.className = 'p-3 rounded-xl border border-rose-800/60 bg-rose-950/40 text-rose-300 text-xs block';
        resBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation mr-1"></i> 공공데이터포털 일반 인증키(Service Key)를 먼저 입력해주세요.';
        resBox.classList.remove('hidden');
        return;
    }

    spinner.classList.remove('hidden');
    resBox.classList.add('hidden');

    try {
        const response = await fetch('/api/test-connection', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                api_key: key,
                custom_url: customUrl || null
            })
        });

        const data = await response.json();

        if (data.success) {
            const count = data.total_count || data.items?.length || 0;
            resBox.className = 'p-3 rounded-xl border border-emerald-800/60 bg-emerald-950/40 text-emerald-300 text-xs block space-y-1.5';
            resBox.innerHTML = `
                <div class="font-bold flex items-center gap-1">
                    <i class="fa-solid fa-circle-check text-emerald-400"></i> 소방청 API 연결 성공!
                </div>
                <div>· 연결된 서비스: <strong class="text-white">${data.connected_service || '소방청 화재정보 API'}</strong></div>
                <div>· 소방청 제공 화재 건수: <strong class="text-white">${count.toLocaleString()}건</strong></div>
                <div>· 실시간 수신 샘플: <strong class="text-white">${(data.items?.length || 0)}건</strong></div>
                <div class="text-[11px] text-emerald-400/80 pt-1">아래 '공공데이터 실시간 API 모드 활성화'를 체크하고 저장하시면 실시간 데이터로 적용됩니다.</div>
            `;
        } else {
            let diagHtml = '';
            if (data.diagnostics && data.diagnostics.length > 0) {
                diagHtml = `<div class="mt-2 p-2 bg-slate-950/80 rounded border border-slate-800 font-mono text-[10px] text-slate-400 overflow-x-auto space-y-0.5">
                    <div class="text-slate-500 font-bold mb-1">[서버 응답 진단 로그]</div>
                    ${data.diagnostics.map(d => `<div>${d}</div>`).join('')}
                </div>`;
            }

            resBox.className = 'p-3 rounded-xl border border-rose-800/60 bg-rose-950/40 text-rose-300 text-xs block space-y-1';
            resBox.innerHTML = `
                <div class="font-bold flex items-center gap-1">
                    <i class="fa-solid fa-circle-xmark text-rose-400"></i> API 연동 확인 실패
                </div>
                <div class="text-rose-200">${data.error || '소방청 API 서버에서 응답을 수신하지 못했습니다.'}</div>
                <div class="text-[11px] text-slate-400">공공데이터포털(data.go.kr) 마이페이지에서 API 활용 승인 상태 및 [일반인증키(Decoding)]를 다시 확인해주세요.</div>
                ${diagHtml}
            `;
        }
    } catch (err) {
        resBox.className = 'p-3 rounded-xl border border-rose-800/60 bg-rose-950/40 text-rose-300 text-xs block';
        resBox.innerHTML = `<i class="fa-solid fa-circle-exmark mr-1"></i> 서버 통신 중 오류가 발생했습니다: ${err.message}`;
    } finally {
        spinner.classList.add('hidden');
        resBox.classList.remove('hidden');
    }
}

function saveApiConfig() {
    const key = document.getElementById('apiKeyInput').value.trim();
    const useReal = document.getElementById('useRealApiCheckbox').checked;

    state.apiConfig.apiKey = key;
    state.apiConfig.mode = useReal ? 'live' : 'demo';

    localStorage.setItem('fire_api_key', key);
    localStorage.setItem('fire_api_mode', state.apiConfig.mode);

    updateModeBadge();
    closeApiConfigModal();
    applyFilters(1);
}

// 14. CSV 내보내기 다운로드
function exportCSV() {
    const params = buildQueryParams(1);
    window.open(`/api/export-csv?${params.toString()}`, '_blank');
}

// 15. UI 유틸리티
function showLoading(show) {
    const loader = document.getElementById('tableLoading');
    if (show) {
        loader.classList.remove('hidden');
    } else {
        loader.classList.add('hidden');
    }
}

function toggleChartSection() {
    const container = document.getElementById('chartContainer');
    const icon = document.getElementById('chartToggleIcon');
    if (container.classList.contains('hidden')) {
        container.classList.remove('hidden');
        icon.className = 'fa-solid fa-chevron-up text-xs';
    } else {
        container.classList.add('hidden');
        icon.className = 'fa-solid fa-chevron-down text-xs';
    }
}
