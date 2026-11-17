# 간식 가게로 배우는 랭체인

이 예제는 **질문을 받고 → 메뉴를 붙이고 → AI에게 보내고 → 답변 글자를 꺼내는 과정**을 배우는 프로그램입니다. 기존 상품 상담 예제를 더 익숙한 간식 가게 이야기로 바꾸었습니다. 실행 코드는 `snack_helper.py` 하나에 들어 있습니다.

## 1. 파일 안내

| 파일 | 하는 일 |
|---|---|
| `image_notes.txt` | 첨부 이미지의 글을 옮긴 UTF-8 텍스트 파일 |
| `snack_helper.py` | 간식 가게 안내 도우미 코드 |
| `README.md` | 지금 읽는 사용 설명서 |

이미지의 `pipline` 표기는 그대로 옮겼습니다. 보통은 `pipeline`이라고 쓰며, 여러 작업을 순서대로 연결한 흐름이라는 뜻입니다. 이미지의 목록은 학습 메모로 옮겼으며 명령으로 실행하지 않았습니다.

## 2. 기존 폴더를 살펴보니

기존 프로그램은 상품 20개가 담긴 자료를 이용해 고객 문의 답변 초안을 만드는 수업입니다.

| 기존 파일 | 배우는 내용 | 새 예제에서는 |
|---|---|---|
| `sessions/s01.py` | 상품 자료 읽기 | 코드 안의 가상 메뉴 `MENU` 사용 |
| `sessions/s02.py` | 역할과 질문을 메시지에 넣기 | `ChatPromptTemplate` 사용 |
| `sessions/s03.py` | 프롬프트 3종 준비 | 이해하기 쉬운 규칙 1종 사용 |
| `sessions/s04.py` | 프롬프트 → 모델 → 파서 연결 | 같은 연결 방식 사용 |
| `sessions/s05.py` | 질문 검사까지 연결 | 빈 질문과 500자 초과 질문 검사 |
| `sessions/s06.py` | 여러 질문 처리와 스트리밍 | 처음 배우기 쉽도록 질문 하나만 처리 |
| `sessions/s07.py` | 프롬프트에 따른 답변 비교 기록 | 비교 실험은 포함하지 않음 |
| `sessions/s08.py` | CSV 읽기와 결과 저장 | 파일 저장 대신 화면에 답변 표시 |

기존 `app/pipeline.py`는 입력 준비, 프롬프트, 모델, 파서를 연결합니다. 새 예제도 그 구조를 사용하지만 상품 조회, 보고서, 여러 공급자 설정을 덜어 내어 한 파일로 읽을 수 있게 했습니다. 기존 수업 파일은 수정하지 않았습니다.

## 3. 먼저 실행해 보기: 실제 AI 없이 연습

PowerShell을 열고 작업 공간 `C:\AIO_04_kjun_02`에서 실행하세요. 아래 명령은 이미 준비된 가상환경을 사용합니다.

```powershell
.\.venv\Scripts\python.exe .\LangChain_20261117_DataEdition\easy_example\snack_helper.py --question "2,000원으로 사과를 몇 개 살 수 있나요?" --show-prompt
```

이 명령은 **API 키와 인터넷 없이 모의 모델로 실행**합니다. 단, 파이썬과 필요한 라이브러리는 설치되어 있어야 합니다. 라이브러리가 없다는 오류가 나오면 다음 명령으로 기존 프로젝트의 의존성을 설치하세요.

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\LangChain_20261117_DataEdition\requirements.txt
```

예상 답변:

```text
[연습 모드: 질문과 무관한 고정 답변]
[모의 응답] 사과는 1개 1,000원입니다. 2,000원으로 사과 2개를 살 수 있습니다. 재고는 가게에 확인해 주세요.
```

**중요: 연습 모드는 모든 질문에 위의 같은 답변을 돌려줍니다.** 질문을 이해하거나 계산한 결과가 아닙니다. 실제 랭체인 연결이 작동하는지만 확인합니다. `--show-prompt`를 붙이면 질문을 바꿀 때 AI에게 보낼 메시지가 달라지는 것을 볼 수 있어요.

직접 질문을 입력하려면 `--question`을 빼세요.

```powershell
.\.venv\Scripts\python.exe .\LangChain_20261117_DataEdition\easy_example\snack_helper.py
```

## 4. 코드가 움직이는 순서

**질문 → 질문 검사와 메뉴 준비 → 메시지 만들기 → 모델 → 답변 글자 꺼내기**

예를 들어 “2,000원으로 사과를 몇 개 살 수 있나요?”라는 질문이 들어옵니다.

1. `prepare_input()`이 빈 질문인지 검사하고 질문과 메뉴를 묶습니다.
2. `ChatPromptTemplate`이 메뉴와 질문을 질문지의 빈칸에 넣습니다.
3. `model`이 메시지를 받아 응답합니다. 기본은 모의 모델입니다.
4. `StrOutputParser()`가 모델 응답에서 화면에 보여 줄 글자를 꺼냅니다.
5. `print()`가 결과를 화면에 보여 줍니다.

핵심 코드는 두 줄이에요.

```python
chain = prepare | prompt | model | StrOutputParser()
answer = chain.invoke(question)
```

첫 줄은 기차 칸을 연결하는 일이고, 둘째 줄은 기차를 출발시키는 일이에요. 이처럼 랭체인 부품을 `|`로 연결하는 표현을 **LCEL**이라고 불러요.

이미지의 “모델 호출”은 이 코드에서 모델을 준비하고 사용하는 부분에 해당합니다. 실제 원격 요청은 `ChatOpenAI` 객체를 만들 때가 아니라, 실제 모드에서 `chain.invoke()`가 모델 단계에 도달할 때 발생합니다.

## 5. 어려운 말을 쉬운 말로

| 용어 | 쉬운 뜻 | 이 예제 |
|---|---|---|
| role | 누구처럼 일할지 | 친절한 간식 가게 도우미 |
| instruction | 지켜야 할 규칙 | 메뉴에 없는 정보는 추측하지 않기 |
| context | 답할 때 참고할 자료 | 사과·바나나·주스 메뉴 |
| prompt | AI에게 전달하는 메시지 | 규칙 + 메뉴 + 손님 질문 |
| model | 응답을 만드는 부품 | 모의 모델 또는 실제 OpenAI 모델 |
| parser | 응답에서 필요한 모양을 꺼내는 부품 | 답변을 문자열로 꺼내기 |
| Runnable | 랭체인에서 연결해 실행할 수 있는 부품 | 메시지 템플릿, 모델 등 |
| RunnableLambda | 일반 함수를 연결 부품으로 감싸는 도구 | 질문 준비 함수를 체인에 넣기 |
| invoke | 입력 하나로 실행하기 | `chain.invoke(question)` |

`StrOutputParser`는 정답 검사기가 아니에요. 틀린 답변도 글자로 꺼낼 수 있으므로 실제 AI의 계산과 답변은 사람이 확인해야 해요. 프롬프트에 규칙을 적어도 항상 지킨다고 보장되지는 않아요.

## 6. 람다는 어디에 쓰이나요?

```python
prepare = RunnableLambda(lambda question: prepare_input(question))
```

`lambda question: prepare_input(question)`은 “질문을 받으면 준비 함수에 전달해 줘”라는 작은 함수입니다. 다음 함수와 같은 일을 해요.

```python
def pass_question(question):
    return prepare_input(question)
```

바깥의 `RunnableLambda`는 이 작은 함수를 랭체인 부품으로 감싸요. 덕분에 `prepare | prompt`처럼 다른 부품과 연결할 수 있어요.

## 7. 실제 AI로 실행하기: 선택 사항

실제 답변을 받으려면 사용 가능한 OpenAI API 키와 모델 ID가 필요합니다. API 비용이 발생할 수 있어요. 프로젝트 또는 작업 공간의 `.env`에 다음 이름으로 설정합니다. 이미 설정되어 있다면 다시 적지 않아도 됩니다.

```text
OPENAI_API_KEY=본인의_API_키
OPENAI_MODEL=계정에서_사용할_수_있는_모델_ID
```

키는 다른 사람에게 보여 주거나 저장소에 올리지 마세요. 코드는 프로젝트 `.env`를 먼저 읽고 작업 공간 `.env`에서 없는 설정만 보충합니다. 이미 설정된 환경변수가 가장 먼저 적용됩니다.

```powershell
.\.venv\Scripts\python.exe .\LangChain_20261117_DataEdition\easy_example\snack_helper.py --real --question "3,000원으로 바나나를 몇 개 살 수 있나요?"
```

정상 완료 시 질문 하나당 실제 모델 요청 1회를 합니다. 자동 재시도는 하지 않습니다. 이 예제의 실제 모드는 OpenAI를 사용하며, 기존 프로젝트의 `LLM_PROVIDER` 설정은 사용하지 않습니다.

## 8. 바꿔 보며 배우기

1. `--show-prompt`를 붙이고 질문을 바꿔 보세요. 메시지 속 질문이 바뀝니다.
2. `MENU`에서 사과 가격을 바꿔 보세요. 전달할 메뉴가 바뀝니다. 모의 답변은 그대로입니다.
3. `--question " "`으로 실행해 보세요. 빈 질문이라 모델 호출 전에 멈춥니다.
4. 실제 모드에서는 “주스 배달이 되나요?”라고 물어보세요. 정보가 없을 때 확인이 필요하다고 답하는지 살펴보세요.

이 코드는 AI를 새로 학습시키는 코드가 아닙니다. 실행할 때마다 메뉴와 규칙을 메시지로 전달하는 코드입니다.
