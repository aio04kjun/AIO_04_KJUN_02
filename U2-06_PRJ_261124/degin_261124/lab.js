"use strict";

const $ = (id) => document.getElementById(id);
const examples = {
  shrimp: {
    query: "버터와 마늘로 구운 왕새우에 크리미한 레몬 소스를 곁들였어요. 어울리는 와인을 추천해 주세요.",
    flavor: "레몬의 산미, 버터의 지방감, 구운 마늘의 향이 두드러집니다.",
    wines: ["샤블리", "브뤼 스파클링"],
    comparison: "샤블리의 산도와 감귤 향은 레몬 소스와 연결됩니다. 브뤼의 기포와 산도는 버터의 여운을 가볍게 정리합니다.",
    reason: "소스의 레몬 향과 어우러지면서 버터의 무게감을 덜어 줍니다.",
  },
  risotto: {
    query: "트러플 오일과 파르미지아노를 넣은 버섯 리조또에 어울리는 와인을 추천해 주세요.",
    flavor: "버섯의 감칠맛과 흙내음, 치즈의 짭짤함, 쌀의 크리미한 질감이 특징입니다.",
    wines: ["피노 누아", "오크 숙성 샤르도네"],
    comparison: "피노 누아의 낮은 타닌과 흙내음이 버섯에 어울립니다. 샤르도네의 부드러운 질감은 리조또의 크리미함을 이어 줍니다.",
    reason: "가벼운 타닌과 신선한 산도가 치즈의 무게감을 균형 있게 잡아 줍니다.",
  },
  photo: {
    query: "첨부한 버거 사진을 바탕으로 요리의 풍미를 분석하고 어울리는 와인을 추천해 주세요.",
    flavor: "예제 사진의 구운 패티, 바질, 토마토와 치즈를 바탕으로 감칠맛과 허브 향을 가정했습니다.",
    wines: ["키안티", "가메"],
    comparison: "키안티의 산도가 토마토와 조화를 이루고 타닌이 패티에 어울립니다. 가메의 붉은 과일 향과 가벼운 바디도 잘 맞습니다.",
    reason: "토마토의 산미와 패티의 풍미를 함께 받쳐 줍니다.",
  },
};

const styleLabels = { all: "전체", red: "레드", white: "화이트", sparkling: "스파클링", other: "기타" };
const demoReviews = [
  ["샤르도네", "white", .91, "레몬 제스트와 미네랄 풍미, 또렷한 산도."],
  ["피노 누아", "red", .88, "붉은 체리와 마른 허브, 가벼운 타닌."],
  ["브뤼", "sparkling", .85, "상쾌한 기포와 풋사과, 구운 빵의 향."],
  ["산지오베제", "red", .82, "잘 익은 체리와 허브, 선명한 산도."],
  ["소비뇽 블랑", "white", .80, "감귤과 신선한 허브 향, 가벼운 바디."],
].map(([variety, style, similarity_score, review]) => ({ metadata: { variety, style }, similarity_score, review }));

const samplePath = location.protocol === "file:" ? "../dish.jpg" : "/dish.jpg";
let attachment = null;
let previewUrl = null;

function setAttachment(next) {
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = null;
  attachment = next;
  $("photo").value = "";
  $("attachment").hidden = !next;
  if (!next) {
    $("preview").removeAttribute("src");
    return;
  }
  if (next !== "sample") previewUrl = URL.createObjectURL(next);
  $("preview").src = next === "sample" ? samplePath : previewUrl;
  $("photo-name").textContent = next === "sample" ? "dish.jpg · 프로젝트 예제" : next.name;
}

function updateTestType() {
  const search = $("test").value === "search";
  $("photo-fields").hidden = search;
  $("search-fields").hidden = !search;
}

function showError(message) {
  $("error").textContent = message;
  $("error").hidden = !message;
}

function node(tag, content, className) {
  const element = document.createElement(tag);
  if (content) element.textContent = content;
  if (className) element.className = className;
  return element;
}

function inlineText(element, text) {
  for (const [index, part] of text.split(/\*\*(.*?)\*\*/g).entries()) {
    element.append(index % 2 ? node("strong", part) : document.createTextNode(part));
  }
}

function renderReport(text) {
  const report = node("article", "", "report");
  let list;
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) { list = null; continue; }
    const item = line.match(/^[-*]\s+(.+)/);
    const heading = line.match(/^#{1,6}\s+(.+)|^\[(.+)\]$/);
    if (item) {
      if (!list) { list = node("ul"); report.append(list); }
      const li = node("li");
      inlineText(li, item[1]);
      list.append(li);
      continue;
    }
    list = null;
    const element = node(heading ? "h3" : "p");
    inlineText(element, heading ? heading[1] || heading[2] : line);
    report.append(element);
  }
  return report;
}

function renderReviews(data) {
  const report = node("article", "", "report");
  report.append(node("p", `요청 스타일 ${styleLabels[data.applied_filter] ?? "전체"} · 반환 ${data.retrieved_count}건`, "meta"));
  if (!data.wine_reviews.length) report.append(node("p", "검색된 리뷰가 없습니다."));
  for (const wine of data.wine_reviews) {
    const metadata = wine.metadata ?? {};
    const item = node("section", "", "review");
    const score = Number.isFinite(wine.similarity_score) ? wine.similarity_score.toFixed(4) : "—";
    const details = [styleLabels[metadata.style], metadata.country, metadata.province].filter(Boolean);
    item.append(node("h3", metadata.variety || "품종 정보 없음"));
    item.append(node("p", [...details, `유사도 ${score}`].join(" · "), "meta"));
    item.append(node("p", wine.review || "리뷰 내용 없음"));
    report.append(item);
  }
  return report;
}

function demoResult(type, payload) {
  if (type === "search") {
    const filtered = demoReviews.filter((item) => payload.style === "all" || item.metadata.style === payload.style).slice(0, payload.count);
    const reviews = payload.style !== "all" && filtered.length < 2 ? demoReviews.slice(0, Math.max(3, payload.count)) : filtered;
    return renderReviews({ applied_filter: payload.style, retrieved_count: reviews.length, wine_reviews: reviews });
  }
  const sample = Object.values(examples).find((value) => value.query === payload.query);
  if (!sample || (sample === examples.photo && attachment !== "sample") || (sample !== examples.photo && attachment)) {
    return renderReport("## 입력 확인\n요리 설명을 받았습니다.\n## 예제 결과 보기\n미리 작성된 추천을 보려면 위의 예제 버튼을 선택하세요. 직접 작성한 설명이나 첨부 사진을 분석하려면 실제 연동을 사용하세요.");
  }
  return renderReport([
    "## 요리 풍미", sample.flavor, "## 후보 와인 2종", ...sample.wines.map((wine) => `- ${wine}`),
    "## 페어링 적합성", sample.comparison, "## 최종 추천", `**${sample.wines[0]}** · ${sample.reason}`,
  ].join("\n"));
}

function readImage(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(",")[1]);
    reader.onerror = () => reject(new Error("사진을 읽을 수 없습니다. 파일을 다시 선택해 주세요."));
    reader.readAsDataURL(file);
  });
}

async function runLive(type, payload, photo) {
  if (location.protocol === "file:") {
    throw new Error("실제 연동은 로컬 서버에서 실행할 수 있습니다. 실행 안내의 명령을 확인해 주세요.");
  }
  if (type === "pairing" && photo) payload.image = photo === "sample" ? photo : await readImage(photo);
  let response;
  try {
    response = await fetch(`/api/${type}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
  } catch {
    throw new Error("로컬 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해 주세요.");
  }
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "요청을 처리할 수 없습니다.");
  if (type === "search") return renderReviews(data);
  if (typeof data.report !== "string" || !data.report.trim()) throw new Error("에이전트가 빈 결과를 반환했습니다.");
  return renderReport(data.report);
}

document.querySelectorAll("[data-sample]").forEach((button) => {
  button.addEventListener("click", () => {
    const sample = button.dataset.sample;
    $("query").value = examples[sample].query;
    if (sample === "photo") $("test").value = "pairing";
    setAttachment(sample === "photo" ? "sample" : null);
    updateTestType();
    showError("");
  });
});
$("test").addEventListener("change", updateTestType);
document.querySelectorAll("[name=mode]").forEach((input) => {
  input.addEventListener("change", () => {
    $("mode-hint").textContent = input.value === "live"
      ? "OpenAI와 Pinecone에 요청합니다. API 사용료가 발생할 수 있습니다."
      : "예제 데이터로 화면과 결과 형식을 확인합니다.";
    showError("");
  });
});
$("photo").addEventListener("change", () => {
  const file = $("photo").files[0];
  if (!file) return;
  if (!/\.jpe?g$/i.test(file.name) || file.size === 0 || file.size > 5 * 1024 * 1024) {
    $("photo").value = "";
    showError("5MB 이하의 JPG 파일을 선택해 주세요.");
    return;
  }
  showError("");
  setAttachment(file);
});
$("remove").addEventListener("click", () => {
  setAttachment(null);
  $("photo").focus();
});
document.querySelector(".nav-link").addEventListener("click", () => { $("guide").open = true; });

$("lab").addEventListener("submit", async (event) => {
  event.preventDefault();
  if ($("run").disabled) return;
  const query = $("query").value.trim();
  if (!query) { showError("요리 설명을 입력해 주세요."); $("query").focus(); return; }
  const type = $("test").value;
  const mode = new FormData($("lab")).get("mode");
  const payload = { query, style: $("style").value, count: Number($("count").value) };
  const result = $("result");
  const started = performance.now();
  showError("");
  result.replaceChildren();
  result.setAttribute("aria-busy", "true");
  $("copy").disabled = true;
  $("copy").textContent = "결과 복사";
  $("run").disabled = true;
  $("status").textContent = "테스트 실행 중…";
  try {
    const report = mode === "live" ? await runLive(type, payload, attachment) : demoResult(type, payload);
    result.append(report);
    const elapsed = Math.round(performance.now() - started);
    $("status").textContent = `${mode === "live" ? "실제 연동" : "예제 데이터"} · 완료 · ${elapsed.toLocaleString("ko-KR")} ms`;
  } catch (error) {
    $("status").textContent = "실행 실패";
    showError(error instanceof SyntaxError ? "로컬 서버의 응답 형식이 올바르지 않습니다." : error.message);
  } finally {
    result.setAttribute("aria-busy", "false");
    $("copy").disabled = !result.firstChild;
    $("run").disabled = false;
  }
});

$("copy").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText($("result").innerText);
    $("copy").textContent = "복사 완료";
  } catch {
    const range = document.createRange();
    range.selectNodeContents($("result"));
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    $("copy").textContent = "선택됨 · Ctrl+C";
  }
});
