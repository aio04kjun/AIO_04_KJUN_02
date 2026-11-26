"use strict";

const $ = (id) => document.getElementById(id);
const canvas = $("map");
const ctx = canvas.getContext("2d");
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
const maxZoom = 16;
const camera = { zoom: 1, x: 0, y: 0 };
const centralStations = new Set(["서울", "서울역", "독산", "김포공항", "인천공항2터미널", "인천", "부평", "고양", "대곡", "의정부", "춘천", "구리", "상봉", "청량리", "성수", "왕십리", "잠실", "강남", "사당", "금정", "수원", "동탄", "천안", "구로", "오이도", "여의도", "광명", "합정"]);
const formatClock = new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
});
let lines = [];
let line;
let demo = false;
let selected = "";
let trains = [];
let positionRows = [];
let motionPaused = false;
let previous = new Map();
let positionRequest;
let stationRequest = 0;
let animation = 0;
let drag;
let bounds;

function stationKey(name) {
    if (typeof name !== "string") return "";
    const key = name.trim().split("(")[0].replace(/[\s·]/g, "");
    return key === "서울역" ? "서울" : key;
}

function stationFor(route, name) {
    const key = stationKey(name);
    return route.names.get(key) || route.names.get(key.replace(/역$/, ""));
}

async function api(url, options) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => {
        throw new Error("서버 응답을 읽을 수 없습니다. 잠시 후 다시 시도해 주세요.");
    });
    if (!response.ok) throw new Error(data.error || "정보를 불러오지 못했습니다.");
    return data;
}

function clock() {
    $("clock").textContent = formatClock.format(new Date());
}

function initNetwork(data) {
    lines = data.map((route) => {
        const stations = new Map();
        const names = new Map();
        for (const [id, [name, longitude, latitude]] of Object.entries(route.stations)) {
            const station = { id, name, x: longitude * .793, y: -latitude };
            stations.set(id, station);
            names.set(stationKey(name), station);
        }
        const neighbors = new Map([...stations.keys()].map((id) => [id, []]));
        for (const [a, b] of route.edges) {
            neighbors.get(a).push(b);
            neighbors.get(b).push(a);
        }
        return { ...route, stations, names, neighbors };
    });
    const all = lines.flatMap((route) => [...route.stations.values()]);
    bounds = {
        left: Math.min(...all.map((point) => point.x)),
        right: Math.max(...all.map((point) => point.x)),
        top: Math.min(...all.map((point) => point.y)),
        bottom: Math.max(...all.map((point) => point.y)),
    };
    const names = [...new Set(all.map((station) => stationKey(station.name) === "서울" ? "서울역" : station.name))].sort((a, b) => a.localeCompare(b, "ko"));
    for (const name of names) $("station-list").append(new Option(name, name));
    for (const route of lines) $("line").append(new Option(route.name === "GTXA" ? "GTX-A" : route.name, route.name));
    $("network-count").textContent = lines.length + "개 노선 · " + names.length + "개 역";
    line = lines[0];
    fit();
}

function dimensions() {
    return { width: canvas.clientWidth, height: canvas.clientHeight };
}

function transform() {
    const { width, height } = dimensions();
    const sx = (bounds.right - bounds.left);
    const sy = (bounds.bottom - bounds.top);
    const scale = Math.min((width - 72) / sx, (height - 80) / sy) * camera.zoom;
    return {
        scale,
        x: width / 2 + camera.x - (bounds.left + bounds.right) * scale / 2,
        y: height / 2 + camera.y - (bounds.top + bounds.bottom) * scale / 2,
    };
}

function project(point, t) {
    return [point.x * t.scale + t.x, point.y * t.scale + t.y];
}

function fit() {
    camera.zoom = 1;
    camera.x = 0;
    camera.y = 0;
    $("map-title").textContent = "전체 노선도";
    draw();
}

function zoom(factor, x = canvas.clientWidth / 2, y = canvas.clientHeight / 2) {
    const old = camera.zoom;
    camera.zoom = Math.max(1, Math.min(maxZoom, old * factor));
    const ratio = camera.zoom / old;
    const dx = x - canvas.clientWidth / 2;
    const dy = y - canvas.clientHeight / 2;
    camera.x = dx - (dx - camera.x) * ratio;
    camera.y = dy - (dy - camera.y) * ratio;
    draw();
}

function centerOn(station) {
    camera.zoom = maxZoom;
    camera.x = 0;
    camera.y = 0;
    const [x, y] = project(station, transform());
    camera.x = canvas.clientWidth / 2 - x;
    camera.y = canvas.clientHeight / 2 - y;
    $("map-title").textContent = (stationKey(station.name) === "서울" ? "서울역" : station.name) + " 주변 노선도";
    draw();
}

function routePath(from, to) {
    if (!from || !to || from.id === to.id) return null;
    const visited = new Map([[from.id, null]]);
    const queue = [from.id];
    for (const id of queue) {
        if (id === to.id) {
            const path = [];
            for (let step = id; step !== null; step = visited.get(step)) path.push(line.stations.get(step));
            return path.reverse();
        }
        for (const next of line.neighbors.get(id)) {
            if (visited.has(next)) continue;
            visited.set(next, id);
            queue.push(next);
        }
    }
    return null;
}

function vector(a, b) {
    return Math.atan2(b.y - a.y, b.x - a.x);
}

function iconPosition(train, now) {
    if (!train.path || motionPaused || reduceMotion.matches) return [train.station, train.heading];
    const progress = (now - train.started) / train.duration;
    if (progress >= 1) return [train.station, train.heading];
    const edge = Math.max(0, progress) * (train.path.length - 1);
    const index = Math.floor(edge);
    const from = train.path[index];
    const to = train.path[index + 1];
    const mix = edge - index;
    return [{ x: from.x + (to.x - from.x) * mix, y: from.y + (to.y - from.y) * mix }, vector(from, to)];
}

function drawTrain(x, y, angle, color) {
    ctx.save();
    ctx.translate(x, y);
    ctx.save();
    ctx.rotate(angle);
    ctx.beginPath();
    ctx.moveTo(19, 0);
    ctx.lineTo(10, -5);
    ctx.lineTo(10, 5);
    ctx.closePath();
    ctx.fillStyle = "#142c38";
    ctx.fill();
    ctx.restore();

    ctx.beginPath();
    ctx.arc(0, 0, 13, 0, Math.PI * 2);
    ctx.fillStyle = "#fff";
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#142c38";
    ctx.stroke();

    ctx.beginPath();
    ctx.roundRect(-7, -8, 14, 14, 4);
    ctx.fillStyle = "#142c38";
    ctx.fill();
    ctx.fillStyle = "#fff";
    ctx.beginPath();
    ctx.roundRect(-4.5, -5.5, 9, 5, 1.5);
    ctx.fill();
    ctx.fillStyle = color;
    ctx.fillRect(-5, 1, 10, 2);
    ctx.fillStyle = "#142c38";
    ctx.fillRect(-5, 7, 2, 2);
    ctx.fillRect(3, 7, 2, 2);
    ctx.restore();
}

function draw(now = performance.now()) {
    if (!bounds) return;
    cancelAnimationFrame(animation);
    const { width, height } = dimensions();
    const dpr = Math.min(devicePixelRatio || 1, 2);
    if (canvas.width !== Math.round(width * dpr) || canvas.height !== Math.round(height * dpr)) {
        canvas.width = Math.round(width * dpr);
        canvas.height = Math.round(height * dpr);
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    const t = transform();
    const showFocus = $("focus").checked;
    const sorted = [...lines.filter((route) => route !== line), line];
    for (const route of sorted) {
        ctx.globalAlpha = showFocus && route !== line ? .21 : .93;
        ctx.strokeStyle = route.color;
        ctx.lineWidth = route === line ? 3.15 : 2.25;
        ctx.lineCap = "round";
        ctx.beginPath();
        for (const [a, b] of route.edges) {
            ctx.moveTo(...project(route.stations.get(a), t));
            ctx.lineTo(...project(route.stations.get(b), t));
        }
        ctx.stroke();
        ctx.fillStyle = route.color;
        for (const station of route.stations.values()) {
            const [x, y] = project(station, t);
            ctx.beginPath();
            ctx.arc(x, y, camera.zoom > 2 ? 2.2 : 1.35, 0, Math.PI * 2);
            ctx.fill();
        }
    }
    ctx.globalAlpha = 1;
    ctx.font = '700 12px "Malgun Gothic", "Apple SD Gothic Neo", system-ui, sans-serif';
    ctx.textBaseline = "middle";
    const occupied = [];
    for (const route of [...sorted].reverse()) {
        for (const station of route.stations.values()) {
            const isSelected = selected === stationKey(station.name);
            if (!isSelected && !centralStations.has(station.name) && !(camera.zoom > 3 && route === line)) continue;
            const [x, y] = project(station, t);
            const label = stationKey(station.name) === "서울" ? "서울역" : station.name;
            const w = ctx.measureText(label).width + 10;
            if (x < 0 || x + w > width || y < 8 || y > height - 17) continue;
            if (!isSelected && occupied.some(([left, top, right]) => Math.abs(top - y) < 13 && x < right && x + w > left)) continue;
            occupied.push([x, y, x + w]);
            ctx.beginPath();
            ctx.arc(x, y, isSelected ? 5.5 : 2.6, 0, Math.PI * 2);
            ctx.fillStyle = isSelected ? "#087063" : "#0f172a";
            ctx.fill();
            if (isSelected) {
                ctx.lineWidth = 2;
                ctx.strokeStyle = "#fff";
                ctx.stroke();
            }
            ctx.lineWidth = 3.7;
            ctx.strokeStyle = "#f7fafc";
            const labelY = isSelected ? y - 23 : y - 6;
            const labelX = isSelected ? x - (w - 10) / 2 : x + 7;
            ctx.strokeText(label, labelX, labelY);
            ctx.fillText(label, labelX, labelY);
        }
    }
    let active = false;
    for (const train of trains) {
        if (!train.station) continue;
        const [point, angle] = iconPosition(train, now);
        drawTrain(...project(point, t), angle, line.color);
        active ||= !motionPaused && !reduceMotion.matches && train.path && now < train.started + train.duration;
    }
    if (active) animation = requestAnimationFrame(draw);
}

function resultRow(parent, title, detail, action) {
    const row = document.createElement(action ? "button" : "div");
    row.className = "result-row";
    if (action) {
        row.type = "button";
        row.addEventListener("click", action);
    }
    const heading = document.createElement("strong");
    const description = document.createElement("span");
    heading.textContent = title;
    description.className = "result-description";
    description.textContent = detail;
    row.append(heading, description);
    parent.append(row);
    return row;
}

function arrivalRow(parent, title, report, seconds, location = "") {
    const duration = Number(seconds);
    const reportedTime = report.match(/^\d+\s*분(?:\s*\d+\s*초)?\s*(?:후)?|^\d+\s*초\s*(?:후)?/)?.[0].trim();
    let eta = reportedTime ? reportedTime.replace(/\s*후$/, "") + " 후" : "";
    if (Number.isFinite(duration) && duration > 0) {
        const rounded = Math.ceil(duration);
        const minutes = Math.floor(rounded / 60);
        const remainder = rounded % 60;
        eta = [minutes ? minutes + "분" : "", remainder ? remainder + "초" : ""].filter(Boolean).join(" ") + " 후";
    }
    const status = reportedTime ? report.slice(reportedTime.length).trim() : report;
    const row = resultRow(parent, title, [...new Set([status, location].filter(Boolean))].join(" · "));
    const badge = document.createElement("span");
    badge.className = "arrival-eta";
    badge.textContent = eta || (/도착|진입/.test(status) && !/전역|번째/.test(status) ? status : "시간 정보 없음");
    if (badge.textContent === status) row.querySelector(".result-description").textContent = location;
    if (!eta) badge.classList.add("arrival-eta-muted");
    row.classList.add("arrival-row");
    row.append(badge);
}

function circularPath(from, to, direction) {
    const onLoop = (station) => station && /^02(?:0[1-9]|[1-3][0-9]|4[0-3])$/.test(station.id);
    if (line.name !== "2호선" || !onLoop(from) || !onLoop(to) || !["0", "1"].includes(direction)) return null;
    const step = direction === "0" ? 1 : -1;
    const path = [from];
    let number = Number(from.id);
    while (path.at(-1) !== to) {
        number = 201 + (number - 201 + step + 43) % 43;
        const next = line.stations.get(String(number).padStart(4, "0"));
        if (!next || !line.neighbors.get(path.at(-1).id).includes(next.id)) return null;
        path.push(next);
    }
    return path;
}

function confirmedPassedPath(station, target, onward) {
    if (!onward) return false;
    // At a junction, the forward leg alone cannot identify the incoming branch.
    let current = station.id;
    let forward = onward[1].id;
    for (let step = 0; step < 2; step++) {
        const incoming = line.neighbors.get(current).filter((id) => id !== forward);
        if (incoming.length !== 1) return false;
        if (incoming[0] === target.id) return true;
        forward = current;
        current = incoming[0];
    }
    return false;
}

function nearbyPositions(rows) {
    const target = stationFor(line, selected);
    if (!target) return [];
    const slots = new Map();
    for (const row of rows) {
        const station = line.stations.get(String(row.statnId)) || stationFor(line, row.statnNm);
        if (!station) continue;
        const distance = station === target ? 0 : (routePath(station, target)?.length ?? Infinity) - 1;
        if (distance > 2) continue;
        const terminal = line.stations.get(String(row.statnTid)) || stationFor(line, row.statnTnm);
        // Without an express stop pattern, only show express trains reported at the searched station.
        if (distance > 0 && ["1", "7"].includes(String(row.directAt))) continue;
        const departsTarget = distance === 0 && String(row.trainSttus) === "2";
        const direction = String(row.updnLine);
        const onward = circularPath(station, terminal, direction) ?? routePath(station, terminal);
        const approachIndex = onward?.indexOf(target);
        const loopPast = circularPath(target, station, direction);
        const approaching = distance === 0 || (approachIndex > 0 && approachIndex <= 2);
        const passed = loopPast ? loopPast.length <= 3 : confirmedPassedPath(station, target, onward);
        const category = departsTarget ? "최근 통과" : approaching
            ? (approachIndex === 2 ? "두 정거장 전" : "도착 직전")
            : passed ? "최근 통과" : null;
        const existing = slots.get(category);
        if (!category || (existing && (existing.distance < distance ||
            (existing.distance === distance && (existing.row.recptnDt ?? "") >= (row.recptnDt ?? ""))))) continue;
        slots.set(category, { row, station, onward, distance, category });
    }
    return ["도착 직전", "두 정거장 전", "최근 통과"].map((category) => slots.get(category)).filter(Boolean);
}

function showPositions(rows) {
    positionRows = rows;
    const now = performance.now();
    const result = $("trains");
    trains = nearbyPositions(rows).map(({ row, station, onward, category }) => {
        const before = previous.get(String(row.trainNo));
        const loopPath = circularPath(before?.station, station, String(row.updnLine));
        const path = loopPath ? (loopPath.length > 1 && loopPath.length <= 4 ? loopPath : null) : routePath(before?.station, station);
        const heading = onward?.length > 1 ? vector(onward[0], onward[1]) : path ? vector(path.at(-2), station) : before?.heading ?? 0;
        if (!path && before?.station && before.station === station && before.path && now < before.started + before.duration) {
            return { ...before, row, category };
        }
        return { row, station, path, heading, category, started: now, duration: path ? Math.min(4000, path.length * 750) : 0 };
    });
    previous = new Map(trains.filter((item) => item.row.trainNo != null).map((item) => [String(item.row.trainNo), item]));
    result.replaceChildren();
    const visible = trains.length;
    $("train-count").textContent = selected ? visible + "대 표시" : "";
    if (!selected) result.textContent = "역을 조회하면 주변 열차를 최대 3대 표시합니다.";
    else if (!stationFor(line, selected)) result.textContent = "선택한 노선이 이 역에 정차하지 않습니다. 역이 속한 노선을 선택해 주세요.";
    else if (!visible) result.textContent = "이 역 주변에 표시할 열차가 없습니다.";
    for (const { row, station, category } of trains) {
        const direction = row.statnTnm ? row.statnTnm + " 방면" : ({ 0: "상행", 1: "하행", 2: "내선", 3: "외선" }[row.updnLine] || "방향 미제공");
        const status = ({ 0: "진입", 1: "도착", 2: "출발", 3: "전역 출발" })[row.trainSttus];
        resultRow(result, category, [station.name, status, direction, "지도에서 보기"].filter(Boolean).join(" · "), () => {
            centerOn(station);
            canvas.scrollIntoView({ block: "nearest" });
        });
    }
    draw();
    return visible;
}

let demoStep = 0;
function demoPositions() {
    const target = stationFor(line, selected);
    if (!target) {
        showPositions([]);
        $("position-note").textContent = "예시 모드입니다. 역을 조회해 주변 열차를 확인해 보세요.";
        return;
    }
    const extend = (start, excluded, length) => {
        const path = [];
        const visited = new Set([target.id, excluded]);
        for (let id = start; id && path.length < length;) {
            path.push(id);
            visited.add(id);
            id = line.neighbors.get(id).find((neighbor) => !visited.has(neighbor));
        }
        return path;
    };
    const [first, second] = line.neighbors.get(target.id);
    const before = extend(first, second, 3).reverse();
    const after = extend(second, first, 3);
    const path = [...before, target.id, ...after];
    const sample = [];
    const offset = demoStep % 2;
    const terminal = path.at(-1);
    for (const [index, relative] of [-3, -2, -1, 0, 1].entries()) {
        const stationId = path[before.length + relative + offset];
        if (!stationId) continue;
        sample.push({ trainNo: "예시 " + index, statnId: stationId, statnTid: terminal, statnTnm: line.stations.get(terminal).name, trainSttus: stationId === target.id ? 1 : 2 });
    }
    if (!offset) previous.clear();
    demoStep += 1;
    showPositions(sample);
    $("position-note").textContent = "예시 운행 · 실제 열차 위치와 무관합니다.";
}

async function refreshPositions() {
    if (!line) return;
    if (demo) {
        demoPositions();
        return;
    }
    positionRequest?.abort();
    const controller = new AbortController();
    positionRequest = controller;
    const requestedLine = line;
    $("position-note").textContent = line.name + " 열차 위치를 조회하는 중…";
    try {
        const data = await api("/api/positions?line=" + encodeURIComponent(requestedLine.name), { signal: controller.signal });
        if (controller.signal.aborted) return;
        const visible = showPositions(data.trains);
        $("position-note").textContent = data.trains.length
            ? "위치 갱신 " + formatClock.format(new Date()) + (selected ? " · 주변 열차 " + visible + "대 표시" : " · 역을 조회해 주변 열차를 확인하세요.")
            : requestedLine.name + " 위치 정보가 없습니다. 노선별 제공 범위와 운행 시간에 따라 달라집니다.";
    } catch (error) {
        if (controller.signal.aborted) return;
        $("position-note").textContent = error.message + (trains.length ? " · 이전 조회 위치 표시 중" : "");
        if (!positionRows.length) $("trains").textContent = "위치를 불러오지 못했습니다. 예시 모드에서 주변 열차를 확인할 수 있습니다.";
    }
}

async function findArrivals(value, pan = true, normalizeInput = true) {
    const name = value.trim();
    if (!name) return;
    const ticket = ++stationRequest;
    const route = stationFor(line, name) ? line : lines.find((candidate) => stationFor(candidate, name));
    const station = route && stationFor(route, name);
    const input = $("station");
    const output = $("arrivals");
    if (!station) {
        input.setAttribute("aria-invalid", "true");
        $("station-error").textContent = "지도에서 역을 찾을 수 없습니다. 자동완성 목록에서 역을 선택해 주세요.";
        output.textContent = "";
        input.focus();
        return;
    }
    input.removeAttribute("aria-invalid");
    $("station-error").textContent = "";
    const canonicalName = stationKey(station.name) === "서울" ? "서울역" : station.name;
    if (normalizeInput) input.value = canonicalName;
    selected = stationKey(station.name);
    if (pan) centerOn(station);
    if (route !== line) {
        line = route;
        $("line").value = line.name;
        resetPositions();
    } else if (demo) {
        demoStep = 0;
        demoPositions();
    } else {
        showPositions(positionRows);
    }
    if (demo) {
        output.textContent = "";
        arrivalRow(output, canonicalName + " · 예시 도착 정보", "", 90);
        return;
    }
    output.textContent = canonicalName + " 도착 정보를 조회하는 중…";
    try {
        const data = await api("/api/arrivals?station=" + encodeURIComponent(canonicalName));
        if (ticket !== stationRequest) return;
        output.replaceChildren();
        if (!data.arrivals.length) output.textContent = data.station + " 도착 정보가 없습니다.";
        for (const row of data.arrivals) {
            arrivalRow(output, row.trainLineNm || data.station, row.arvlMsg2 || "", row.barvlDt, row.arvlMsg3);
        }
    } catch (error) {
        if (ticket === stationRequest) output.textContent = error.message;
    }
}

function resetPositions() {
    positionRequest?.abort();
    previous.clear();
    positionRows = [];
    demoStep = 0;
    trains = [];
    $("train-count").textContent = "";
    $("trains").replaceChildren();
    draw();
    refreshPositions();
}

function nearestStation(x, y) {
    const t = transform();
    let closest;
    let distance = 12;
    const routes = $("focus").checked ? [line] : lines;
    for (const route of routes) {
        for (const station of route.stations.values()) {
            const [sx, sy] = project(station, t);
            const gap = Math.hypot(x - sx, y - sy);
            if (gap < distance) {
                distance = gap;
                closest = station;
            }
        }
    }
    return closest;
}

function bind() {
    let stationTimer;
    new ResizeObserver(() => draw()).observe(canvas);
    const agentPanel = $("agent-panel");
    const agentDetails = agentPanel.closest("details");
    let panelEntrance;
    agentDetails.querySelector("summary").addEventListener("click", (event) => {
        panelEntrance?.cancel();
        // Native details toggling also handles keyboard and assistive technology clicks.
        if (agentDetails.open || !event.detail || reduceMotion.matches) return;
        panelEntrance = agentPanel.animate(
            [{ opacity: .65, transform: "translateY(-4px)" }, { opacity: 1, transform: "translateY(0)" }],
            { duration: 150, easing: "cubic-bezier(0.23, 1, 0.32, 1)" },
        );
    });
    $("zoom-in").onclick = () => zoom(1.35);
    $("zoom-out").onclick = () => zoom(1 / 1.35);
    $("reset").onclick = fit;
    $("refresh").onclick = refreshPositions;
    $("motion").onclick = (event) => {
        motionPaused = !motionPaused;
        event.currentTarget.setAttribute("aria-pressed", String(motionPaused));
        draw();
    };
    reduceMotion.addEventListener("change", () => draw());
    $("focus").onchange = () => draw();
    $("mode").onclick = () => {
        demo = !demo;
        demoStep = 0;
        stationRequest += 1;
        $("mode").setAttribute("aria-pressed", String(demo));
        resetPositions();
        if (selected) findArrivals(selected, false, false);
        else $("arrivals").textContent = "역을 검색하거나 지도에서 선택하세요.";
    };
    $("line").onchange = (event) => {
        line = lines.find((route) => route.name === event.target.value);
        demoStep = 0;
        resetPositions();
    };
    canvas.addEventListener("wheel", (event) => {
        if (document.activeElement !== canvas || event.ctrlKey || event.metaKey) return;
        event.preventDefault();
        zoom(event.deltaY < 0 ? 1.18 : 1 / 1.18, event.offsetX, event.offsetY);
    }, { passive: false });
    canvas.addEventListener("keydown", (event) => {
        const offset = { ArrowLeft: [48, 0], ArrowRight: [-48, 0], ArrowUp: [0, 48], ArrowDown: [0, -48] }[event.key];
        if (!offset) return;
        event.preventDefault();
        const limit = Math.max(canvas.clientWidth, canvas.clientHeight) * camera.zoom / 2;
        camera.x = Math.max(-limit, Math.min(limit, camera.x + offset[0]));
        camera.y = Math.max(-limit, Math.min(limit, camera.y + offset[1]));
        draw();
    });
    canvas.addEventListener("pointerdown", (event) => {
        if (event.button !== 0 || drag) return;
        canvas.setPointerCapture(event.pointerId);
        drag = { id: event.pointerId, x: event.clientX, y: event.clientY, startX: camera.x, startY: camera.y, moved: false };
    });
    canvas.addEventListener("pointermove", (event) => {
        if (drag?.id !== event.pointerId) return;
        const dx = event.clientX - drag.x;
        const dy = event.clientY - drag.y;
        drag.moved ||= Math.hypot(dx, dy) > 4;
        if (!drag.moved) return;
        const limit = Math.max(canvas.clientWidth, canvas.clientHeight) * camera.zoom / 2;
        camera.x = Math.max(-limit, Math.min(limit, drag.startX + dx));
        camera.y = Math.max(-limit, Math.min(limit, drag.startY + dy));
        draw();
    });
    canvas.addEventListener("pointerup", (event) => {
        if (drag?.id !== event.pointerId) return;
        if (!drag.moved) {
            const rect = canvas.getBoundingClientRect();
            const station = nearestStation(event.clientX - rect.left, event.clientY - rect.top);
            if (station) {
                clearTimeout(stationTimer);
                findArrivals(station.name);
            }
        }
        drag = null;
    });
    canvas.addEventListener("lostpointercapture", () => { drag = null; });
    const stationInput = $("station");
    function previewStation(event) {
        clearTimeout(stationTimer);
        stationInput.removeAttribute("aria-invalid");
        $("station-error").textContent = "";
        if (event.isComposing) return;
        const value = stationInput.value;
        if (lines.some((route) => stationFor(route, value))) {
            stationTimer = setTimeout(() => findArrivals(value, true, false), 350);
        }
    }
    stationInput.addEventListener("input", previewStation);
    stationInput.addEventListener("compositionend", previewStation);
    $("station-form").onsubmit = (event) => {
        event.preventDefault();
        clearTimeout(stationTimer);
        findArrivals(stationInput.value);
    };
    $("agent-form").onsubmit = async (event) => {
        event.preventDefault();
        const button = event.currentTarget.querySelector("button");
        const output = $("answer");
        output.textContent = "에이전트가 답변을 준비하는 중…";
        button.disabled = true;
        try {
            const data = await api("/api/agent", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query: $("question").value }),
            });
            output.textContent = typeof data.answer === "string" ? data.answer : JSON.stringify(data.answer);
        } catch (error) {
            output.textContent = error.message;
        } finally {
            button.disabled = false;
        }
    };
    setInterval(() => {
        if (!demo && !document.hidden) refreshPositions();
    }, 30_000);
    setInterval(() => {
        if (demo && !document.hidden) demoPositions();
    }, 4_500);
}

clock();
setInterval(clock, 1000);
api("/network.json").then((data) => {
    initNetwork(data);
    bind();
    refreshPositions();
}).catch((error) => { $("position-note").textContent = "노선도를 불러오지 못했습니다. " + error.message; });
