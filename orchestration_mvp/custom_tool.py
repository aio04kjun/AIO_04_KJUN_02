"""파일 기반 가상 직원 DB와 ERP 카드 거래 조회 도구."""

import argparse
import json
import random
import sqlite3
import sys
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


DATABASE = Path(__file__).with_name("demo.sqlite3")
EMPLOYEE_COUNT = 100
TRANSACTIONS_PER_EMPLOYEE = 10
DEPARTMENTS = ("개발팀", "영업팀", "운영팀", "인사팀", "재무팀")
JOB_GRADES = ("사원", "대리", "과장", "차장", "부장")
PERFORMANCE_RATINGS = ("S", "A", "B", "C", "D", "E", "F")
FAMILY_NAMES = ("김", "이", "박", "최", "정", "강", "조", "윤", "장", "임")
GIVEN_NAMES = ("지우", "민준", "서연", "도윤", "하은", "지호", "유진", "수현", "현우", "예린")
MERCHANTS = (
    ("가상 모빌리티", "교통비"),
    ("가상 문구몰", "사무용품비"),
    ("가상 비즈니스 식당", "업무 식비"),
    ("가상 컨퍼런스 센터", "교육비"),
)
EMPLOYEE_COLUMNS = f"""(
    employee_id TEXT PRIMARY KEY,
    employee_name TEXT NOT NULL CHECK (length(trim(employee_name)) > 0),
    hire_date TEXT NOT NULL,
    department TEXT NOT NULL,
    job_grade TEXT NOT NULL,
    annual_salary_krw INTEGER NOT NULL CHECK (annual_salary_krw > 0),
    performance_rating TEXT NOT NULL CHECK (performance_rating IN {PERFORMANCE_RATINGS}),
    corporate_card_id TEXT NOT NULL UNIQUE
)"""
SCHEMA = f"""
CREATE TABLE IF NOT EXISTS employees {EMPLOYEE_COLUMNS};
CREATE TABLE IF NOT EXISTS erp_card_transactions (
    transaction_id TEXT PRIMARY KEY,
    corporate_card_id TEXT NOT NULL REFERENCES employees(corporate_card_id),
    transaction_date TEXT NOT NULL,
    merchant TEXT NOT NULL,
    amount_krw INTEGER NOT NULL CHECK (amount_krw > 0),
    category TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS card_transactions_by_card_and_date
    ON erp_card_transactions(corporate_card_id, transaction_date);
"""


def business_date() -> date:
    return datetime.now(timezone(timedelta(hours=9))).date()


def initialize_database(db_path: Path = DATABASE) -> dict:
    """기존 직원 스키마를 갱신하거나 새 DB에 합성 데이터를 적재한다."""
    with closing(sqlite3.connect(db_path)) as db, db:
        # 직원 테이블을 교체하는 동안 카드 거래의 외래 키를 보존한다.
        db.execute("PRAGMA foreign_keys = OFF")
        db.executescript("BEGIN IMMEDIATE;\n" + SCHEMA)
        columns = {column[1] for column in db.execute("PRAGMA table_info(employees)")}
        if "employee_name" not in columns:
            _upgrade_employee_table(db)

        employee_count = db.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
        transaction_count = db.execute("SELECT COUNT(*) FROM erp_card_transactions").fetchone()[0]
        if employee_count == 0 and transaction_count == 0:
            _seed_database(db)
            employee_count = db.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
            transaction_count = db.execute("SELECT COUNT(*) FROM erp_card_transactions").fetchone()[0]
        if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise sqlite3.IntegrityError("직원과 카드 거래의 외래 키가 일치하지 않습니다.")

    return {"employees": employee_count, "erp_card_transactions": transaction_count}


def _employee_profiles(count: int) -> list[tuple[str, str]]:
    ratings = [PERFORMANCE_RATINGS[index % len(PERFORMANCE_RATINGS)] for index in range(count)]
    random.Random(2026).shuffle(ratings)
    profiles = []
    for index, rating in enumerate(ratings):
        family_index, given_index = divmod(index, len(GIVEN_NAMES))
        cycle, family_index = divmod(family_index, len(FAMILY_NAMES))
        name = FAMILY_NAMES[family_index] + GIVEN_NAMES[given_index]
        if cycle:
            name += f"{cycle + 1}"
        profiles.append((name, rating))
    return profiles


def _upgrade_employee_table(db: sqlite3.Connection) -> None:
    rows = db.execute(
        """SELECT employee_id, hire_date, department, job_grade, annual_salary_krw, corporate_card_id
           FROM employees ORDER BY employee_id"""
    ).fetchall()
    db.execute(f"CREATE TABLE employees_upgrade {EMPLOYEE_COLUMNS}")
    db.executemany(
        "INSERT INTO employees_upgrade VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (employee_id, name, hire_date, department, job_grade, salary, rating, card_id)
            for (employee_id, hire_date, department, job_grade, salary, card_id), (name, rating)
            in zip(rows, _employee_profiles(len(rows)), strict=True)
        ],
    )
    db.execute("DROP TABLE employees")
    db.execute("ALTER TABLE employees_upgrade RENAME TO employees")


def _seed_database(db: sqlite3.Connection) -> None:
    rng = random.Random(42)
    today = business_date()
    previous_month_end = today.replace(day=1) - timedelta(days=1)
    transaction_number = 1
    for number, (employee_name, rating) in enumerate(_employee_profiles(EMPLOYEE_COUNT), start=1):
        card_id = f"CARD-{1000 + number}"
        grade = rng.randrange(len(JOB_GRADES))
        hire_date = today - timedelta(days=365 * (grade + 1) + rng.randrange(365))
        db.execute(
            "INSERT INTO employees VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (f"EMP-{number:03d}", employee_name, hire_date.isoformat(), rng.choice(DEPARTMENTS),
             JOB_GRADES[grade], (36 + grade * 11 + rng.randrange(10)) * 1_000_000,
             rating, card_id),
        )
        transactions = []
        for index in range(TRANSACTIONS_PER_EMPLOYEE):
            if index < 2:
                day = previous_month_end.replace(day=rng.randint(1, previous_month_end.day))
            else:
                day = today - timedelta(days=rng.randrange(365))
            merchant, category = rng.choice(MERCHANTS)
            transactions.append((f"TX-{transaction_number:04d}", card_id, day.isoformat(),
                                 merchant, rng.randint(35, 4200) * 100, category))
            transaction_number += 1
        db.executemany("INSERT INTO erp_card_transactions VALUES (?, ?, ?, ?, ?, ?)", transactions)


def _connect_read_only(db_path: Path) -> sqlite3.Connection:
    if not db_path.is_file():
        raise ValueError("SQLite 파일이 없습니다. custom_tool.py init 명령으로 먼저 생성하세요.")
    db = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def date_bounds(start_date: str | None, end_date: str | None) -> tuple[date | None, date | None]:
    def parse(value: str | None) -> date | None:
        if value is None:
            return None
        try:
            day = date.fromisoformat(value)
        except ValueError:
            raise ValueError("조회 날짜를 YYYY-MM-DD 형식으로 입력해 주세요.") from None
        if day.isoformat() != value:
            raise ValueError("조회 날짜를 YYYY-MM-DD 형식으로 입력해 주세요.")
        return day

    start, end = parse(start_date), parse(end_date)
    if start is not None and end is not None and start > end:
        raise ValueError("조회 시작일이 종료일보다 늦습니다.")
    return start, end


def _date_filter(start_date: str | None, end_date: str | None) -> tuple[str, list[str]]:
    start, end = date_bounds(start_date, end_date)
    filters, params = [], []
    if start is not None:
        filters.append("AND t.transaction_date >= ?")
        params.append(start.isoformat())
    if end is not None:
        filters.append("AND t.transaction_date <= ?")
        params.append(end.isoformat())
    return " ".join(filters), params


def get_employee(employee_id: str, *, db_path: Path = DATABASE) -> dict:
    """직원 ID로 직원 정보와 등록된 법인카드 ID를 조회한다."""
    with closing(_connect_read_only(db_path)) as db:
        row = db.execute(
            """SELECT employee_id, employee_name, hire_date, department, job_grade,
                      annual_salary_krw, performance_rating, corporate_card_id
               FROM employees WHERE employee_id = ?""",
            (employee_id,),
        ).fetchone()
    if row is None:
        raise LookupError(f"등록된 직원 ID가 아닙니다: {employee_id}")
    return dict(row)


def get_corporate_card_transactions(
    corporate_card_id: str, *, start_date: str | None = None, end_date: str | None = None,
    db_path: Path = DATABASE,
) -> dict:
    """카드 거래 목록과 합계를 조회한다. 시작일과 종료일을 모두 포함한다."""
    date_filter, params = _date_filter(start_date, end_date)
    with closing(_connect_read_only(db_path)) as db:
        owner = db.execute(
            "SELECT 1 FROM employees WHERE corporate_card_id = ?", (corporate_card_id,)
        ).fetchone()
        if owner is None:
            raise LookupError(f"등록된 법인카드 ID가 아닙니다: {corporate_card_id}")
        rows = db.execute(
            f"""SELECT transaction_id, transaction_date, merchant, amount_krw, category
                FROM erp_card_transactions AS t
                WHERE t.corporate_card_id = ? {date_filter}
                ORDER BY transaction_date, transaction_id""",
            (corporate_card_id, *params),
        ).fetchall()
    return {
        "corporate_card_id": corporate_card_id,
        "start_date": start_date,
        "end_date": end_date,
        "transaction_count": len(rows),
        "total_krw": sum(row["amount_krw"] for row in rows),
        "transactions": [dict(row) for row in rows],
    }


def get_spending_by_employee(
    *, start_date: str | None = None, end_date: str | None = None,
    limit: int = EMPLOYEE_COUNT, db_path: Path = DATABASE,
) -> dict:
    """두 테이블을 조인해 직원별 거래 건수와 합계를 집계한다."""
    if not 1 <= limit <= EMPLOYEE_COUNT:
        raise ValueError(f"집계 행 수는 1~{EMPLOYEE_COUNT} 사이여야 합니다.")
    date_filter, params = _date_filter(start_date, end_date)
    with closing(_connect_read_only(db_path)) as db:
        rows = db.execute(
            f"""WITH spending AS (
                    SELECT e.employee_id, e.employee_name, e.department,
                           COUNT(t.transaction_id) AS transaction_count,
                           COALESCE(SUM(t.amount_krw), 0) AS total_krw
                    FROM employees AS e LEFT JOIN erp_card_transactions AS t
                        ON e.corporate_card_id = t.corporate_card_id {date_filter}
                    GROUP BY e.employee_id, e.employee_name, e.department
                )
                SELECT *, COUNT(*) OVER () AS employee_count,
                          SUM(transaction_count) OVER () AS company_transaction_count,
                          SUM(total_krw) OVER () AS company_total_krw
                FROM spending ORDER BY total_krw DESC, employee_id LIMIT ?""",
            (*params, limit),
        ).fetchall()
    return {
        "start_date": start_date,
        "end_date": end_date,
        "employee_count": rows[0]["employee_count"] if rows else 0,
        "company_transaction_count": rows[0]["company_transaction_count"] if rows else 0,
        "company_total_krw": rows[0]["company_total_krw"] if rows else 0,
        "employees": [
            {key: row[key] for key in (
                "employee_id", "employee_name", "department", "transaction_count", "total_krw"
            )}
            for row in rows
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="가상 직원 DB와 ERP 카드 거래를 관리하고 조회합니다.")
    parser.add_argument("--db", type=Path, default=DATABASE, help="SQLite 파일 경로")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="SQLite 파일 생성 또는 기존 직원 테이블 갱신")
    employee_parser = commands.add_parser("employee", help="직원 정보 조회")
    employee_parser.add_argument("employee_id", help="예: EMP-001")
    card_parser = commands.add_parser("card", help="법인카드 사용 내역 조회")
    card_parser.add_argument("corporate_card_id", help="예: CARD-1001")
    summary_parser = commands.add_parser("summary", help="전 직원 카드 합계와 직원별 지출 순위")
    summary_parser.add_argument("--limit", type=int, default=EMPLOYEE_COUNT)
    for command in (card_parser, summary_parser):
        command.add_argument("--start-date", help="조회 시작일 (YYYY-MM-DD)")
        command.add_argument("--end-date", help="조회 종료일 (YYYY-MM-DD)")
    args = parser.parse_args()

    try:
        if args.command == "init":
            result = initialize_database(args.db)
        elif args.command == "employee":
            result = get_employee(args.employee_id, db_path=args.db)
        else:
            filters = {"start_date": args.start_date, "end_date": args.end_date, "db_path": args.db}
            if args.command == "card":
                result = get_corporate_card_transactions(args.corporate_card_id, **filters)
            else:
                result = get_spending_by_employee(limit=args.limit, **filters)
    except (LookupError, ValueError, sqlite3.Error) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
