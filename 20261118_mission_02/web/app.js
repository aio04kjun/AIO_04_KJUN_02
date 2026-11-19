const $ = (selector) => document.querySelector(selector);
const form = $('#trip-form');
const icons = ['sun', 'partly', 'cloud', 'rain', 'storm', 'snow', 'unknown'];
const coasts = { 태안: '서해', 강릉: '동해', 여수: '남해' };
let selectedCity = new FormData(form).get('city');

const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
})[char]);
const money = new Intl.NumberFormat('ko-KR');
const koreanDate = new Intl.DateTimeFormat('ko-KR', { month: 'numeric', day: 'numeric', weekday: 'short', timeZone: 'Asia/Seoul' });
const formatDate = (date) => koreanDate.format(new Date(`${date}T00:00:00+09:00`));
const showValue = (value, unit = '') => value == null ? '—' : `${esc(value)}${unit}`;

function text(selector, value) {
  const element = $(selector);
  element.textContent = value ?? '';
  element.hidden = !value;
}

function showSection(section, show) {
  $(`#${section}`).hidden = !show;
  $(`nav a[href="#${section}"]`).hidden = !show;
}

function showForecast(forecast, routes) {
  showSection('forecast', Boolean(forecast));
  if (!forecast) return;
  const dates = new Set(routes.map((day) => day.date));
  text('#forecast-source', forecast.source === '예시 예보' ? '예시 예보 · 실시간 날씨와 다를 수 있어요.' : '해안 대표 좌표 기준 · Open-Meteo / CAMS');
  text('#forecast-warning', forecast.warnings.join(' '));
  $('#forecast-days').innerHTML = forecast.days.map((day) => {
    const icon = icons.includes(day.icon) ? day.icon : 'unknown';
    const travelled = dates.has(day.date);
    return `<article class="forecast-day${travelled ? ' on-trip' : ''}">
      <p class="forecast-date"><time datetime="${esc(day.date)}">${esc(formatDate(day.date))}</time>${travelled ? '<span class="sr-only"> · 여행 날짜</span>' : ''}</p>
      <div class="forecast-icon ${icon}" aria-hidden="true"><i class="sun"></i><i class="cloud"></i><span class="drops"><i></i><i></i><i></i></span></div>
      <p class="weather-label">${esc(day.label)}</p>
      <p class="temperatures"><span aria-label="최저">${showValue(day.low, '°')}</span> / <b aria-label="최고">${showValue(day.high, '°')}</b></p>
      <p class="forecast-meta">강수 ${showValue(day.rain, '%')}</p>
      <p class="forecast-meta">미세먼지 ${showValue(day.pm10)}</p>
      <p class="forecast-meta">초미세먼지 ${showValue(day.pm2_5)}</p>
    </article>`;
  }).join('');
}

function showStays(stays) {
  showSection('stays', Boolean(stays));
  if (!stays) return;
  text('#stays-source', stays.source);
  text('#stays-warning', stays.warning);
  $('#stay-cards').innerHTML = stays.items.map((stay, index) => {
    const featured = index === 0 && stay.match;
    let image = '<span>대표 이미지 없음</span>';
    if (stay.image_url) {
      image = `<span>대표 이미지 없음</span><img loading="lazy" src="${esc(stay.image_url)}" alt="${esc(stay.name)} 대표 사진" referrerpolicy="no-referrer">`;
    } else if (Number.isInteger(stay.image_index) && stay.image_index >= 0 && stay.image_index <= 5) {
      image = `<div class="stay-art image-${stay.image_index}" role="img" aria-label="${esc(stay.name)}의 예시 이미지"></div>`;
    }
    const price = stay.price == null ? '가격 확인 필요' : `${money.format(stay.price)}원 <span>/ 1박 예시</span>`;
    return `<article class="stay-card${featured ? ' featured' : ''}">
      <div class="stay-visual">${image}</div>
      <div class="stay-content"><p class="stay-meta">${esc(stay.area)}${featured ? ' · 날씨와 컨디션에 맞는 숙소' : ''}</p>
      <h3>${esc(stay.name)}</h3><p>${esc(stay.description)}</p><p class="stay-price">${price}</p></div>
    </article>`;
  }).join('') || '<p class="result-warning">조건에 맞는 숙소를 확인하지 못했어요.</p>';
  $('#stay-cards').querySelectorAll('img').forEach((image) => {
    image.addEventListener('error', () => { image.hidden = true; }, { once: true });
    if (image.complete && !image.naturalWidth) image.hidden = true;
  });
}

function showRoutes(routes) {
  showSection('routes', Boolean(routes.length));
  if (!routes.length) return;
  const buttons = $('#route-days');
  buttons.innerHTML = routes.map((day, index) => `<button type="button" class="pill" aria-pressed="${index === 0}" data-day="${index}">${index + 1}일차 · ${esc(formatDate(day.date))}</button>`).join('');

  function renderDay(index) {
    const day = routes[index];
    for (const button of buttons.children) button.setAttribute('aria-pressed', String(Number(button.dataset.day) === index));
    $('#route-panel').innerHTML = `<p class="route-note">${esc(day.note)}</p>
      <div class="route-grid">${day.stops.map((stop) => `<article class="route-card">
        <p class="step">${esc(stop.label)}</p><h3>${esc(stop.title)}</h3><p>${esc(stop.description)}</p>
      </article>`).join('')}</div>`;
  }

  buttons.onclick = (event) => {
    const button = event.target.closest('button[data-day]');
    if (button) renderDay(Number(button.dataset.day));
  };
  renderDay(0);
}

function render(result) {
  const { intent, city, sea, routes, stays, weather, provider } = result;
  const titles = { 일정: '바다 여행', 날씨: '날씨 예보', 숙소: '숙소 조회', '두 정보': '숙소와 날씨' };
  text('#result-region', `${sea}  ·  ${provider === 'Mock' ? 'Mock 수업 데모' : provider}`);
  text('#result-title', `${city} ${titles[intent.task]}`);
  text('#result-dates', routes.length ? `${formatDate(intent.start)} 출발 · ${intent.days}일 · ${intent.condition}` : intent.condition);
  text('#summary', result.summary);
  showForecast(weather, routes);
  showStays(stays);
  showRoutes(routes);

  const fields = [['여행지', city], ['요청 유형', intent.task], ['출발 날짜', intent.start], ['일수', intent.days],
    ['1박 예산', intent.budget == null ? '미지정' : `${money.format(intent.budget)}원`], ['컨디션', intent.condition]];
  $('#intent').innerHTML = fields.map(([key, value]) => `<dt>${esc(key)}</dt><dd>${esc(value)}</dd>`).join('');
  $('#events').innerHTML = result.events.map(({ stage, tool }) => `<li>${esc(stage)} · <code>${esc(tool)}</code></li>`).join('');
  for (const option of form.elements.city) option.checked = option.value === city;
  selectedCity = city;
  $('#results').hidden = false;
}

async function plan(shouldScroll) {
  const submit = $('#submit');
  const status = $('#status');
  const question = $('#question');
  status.dataset.error = 'false';
  if (!question.value.trim()) {
    status.textContent = '여행 질문을 입력해 주세요.';
    status.dataset.error = 'true';
    return;
  }
  const payload = Object.fromEntries(new FormData(form));
  submit.disabled = true;
  form.setAttribute('aria-busy', 'true');
  status.textContent = '여행 조건을 확인하고 있어요…';
  try {
    const response = await fetch('/api/plan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || '추천을 불러오지 못했어요.');
    render(result);
    status.textContent = shouldScroll ? `${result.city} 결과가 준비됐어요.` : '';
    if (shouldScroll) {
      const heading = $('#trip-heading');
      heading.focus({ preventScroll: true });
      heading.scrollIntoView();
    }
  } catch (error) {
    status.dataset.error = 'true';
    status.textContent = error instanceof TypeError || error instanceof SyntaxError
      ? '서버에 연결하지 못했어요. server.py가 실행 중인지 확인해 주세요.' : error.message;
  } finally {
    submit.disabled = false;
    form.removeAttribute('aria-busy');
  }
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  plan(true);
});
form.addEventListener('change', (event) => {
  if (event.target.name !== 'city') return;
  const next = event.target.value;
  const question = $('#question');
  question.value = question.value.replaceAll(selectedCity, next).replaceAll(coasts[selectedCity], coasts[next]);
  selectedCity = next;
});
plan(false);
