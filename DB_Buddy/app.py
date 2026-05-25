import os
import re
from pathlib import Path
from io import BytesIO
from math import ceil

import pandas as pd
import streamlit as st
from sqlalchemy.engine import URL
from streamlit_mermaid import st_mermaid

import db_utils
import docker_utils
import llm_chain


st.set_page_config(page_title="DB-Buddy", layout="wide", page_icon="🗄️")

st.markdown(
    """
    <style>
    button[aria-label="DB 파일 저장"],
    button[aria-label="DB 파일 불러오기"] {
        border: 3px solid #f97316 !important;
        box-shadow: 0 0 0 1px rgba(249, 115, 22, 0.20);
        white-space: nowrap !important;
    }
    button[aria-label="DB 파일 저장"] {
        min-width: 150px !important;
    }
    button[aria-label="DB 파일 불러오기"] {
        min-width: 180px !important;
    }
    button[aria-label="DB 파일 불러오기"]:hover {
        border-color: #ea580c !important;
        box-shadow: 0 0 0 2px rgba(249, 115, 22, 0.24);
    }
    button[aria-label="DB 파일 저장"]:hover {
        border-color: #ea580c !important;
        box-shadow: 0 0 0 2px rgba(249, 115, 22, 0.24);
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(div[data-testid="stFileUploader"]) {
        border: 2px solid #1f1f1f !important;
        box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.20), 0 8px 24px rgba(0, 0, 0, 0.12);
        border-radius: 14px;
        padding: 0.25rem 0.75rem 0.75rem 0.75rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _choose_save_path(default_name: str = "local_study_backup.db") -> Path | None:
    """Windows 파일 저장 대화상자를 열어 저장 경로를 고른다."""
    import ctypes
    from ctypes import wintypes

    class OPENFILENAMEW(ctypes.Structure):
        _fields_ = [
            ("lStructSize", wintypes.DWORD),
            ("hwndOwner", wintypes.HWND),
            ("hInstance", wintypes.HINSTANCE),
            ("lpstrFilter", wintypes.LPCWSTR),
            ("lpstrCustomFilter", wintypes.LPWSTR),
            ("nMaxCustFilter", wintypes.DWORD),
            ("nFilterIndex", wintypes.DWORD),
            ("lpstrFile", wintypes.LPWSTR),
            ("nMaxFile", wintypes.DWORD),
            ("lpstrFileTitle", wintypes.LPWSTR),
            ("nMaxFileTitle", wintypes.DWORD),
            ("lpstrInitialDir", wintypes.LPCWSTR),
            ("lpstrTitle", wintypes.LPCWSTR),
            ("Flags", wintypes.DWORD),
            ("nFileOffset", wintypes.WORD),
            ("nFileExtension", wintypes.WORD),
            ("lpstrDefExt", wintypes.LPCWSTR),
            ("lCustData", wintypes.LPARAM),
            ("lpfnHook", wintypes.LPVOID),
            ("lpTemplateName", wintypes.LPCWSTR),
            ("pvReserved", wintypes.LPVOID),
            ("dwReserved", wintypes.DWORD),
            ("FlagsEx", wintypes.DWORD),
        ]

    initial_dir = db_utils.BASE_DIR / "exports"
    initial_dir.mkdir(parents=True, exist_ok=True)
    initial_file = initial_dir / default_name
    buffer = ctypes.create_unicode_buffer(str(initial_file), 1024)
    file_title = ctypes.create_unicode_buffer(260)

    ofn = OPENFILENAMEW()
    ofn.lStructSize = ctypes.sizeof(OPENFILENAMEW)
    ofn.hwndOwner = ctypes.windll.user32.GetForegroundWindow()
    ofn.lpstrFilter = "SQLite DB (*.db;*.sqlite;*.sqlite3)\0*.db;*.sqlite;*.sqlite3\0All Files (*.*)\0*.*\0\0"
    ofn.lpstrFile = ctypes.cast(buffer, wintypes.LPWSTR)
    ofn.nMaxFile = len(buffer)
    ofn.lpstrFileTitle = ctypes.cast(file_title, wintypes.LPWSTR)
    ofn.nMaxFileTitle = len(file_title)
    ofn.lpstrInitialDir = str(initial_dir)
    ofn.lpstrTitle = "DB 파일 저장 위치를 선택하세요"
    ofn.Flags = 0x00000002 | 0x00000004 | 0x00000008 | 0x00080000
    ofn.lpstrDefExt = "db"

    if not ctypes.windll.comdlg32.GetSaveFileNameW(ctypes.byref(ofn)):
        return None

    chosen = Path(buffer.value)
    if not chosen.suffix:
        chosen = chosen.with_suffix(".db")
    return chosen


def _init_state():
    defaults = {
        "chat_history": [],
        "current_query": "",
        "erd_code": "",
        "mysql_erd_code": "",
        "mysql_query": "",
        "mysql_docs": "",
        "db_url": db_utils.DEFAULT_SQLITE_URL,
        "menu": "DB",
        "local_mysql_info": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _ensure_local_db():
    if not db_utils.LOCAL_DB_PATH.exists():
        db_utils.initialize_database()


def _render_local_mysql_panel():
    ready, message = docker_utils.docker_is_ready()

    if ready:
        st.sidebar.success("Docker가 준비되어 있습니다.")
        st.sidebar.caption("처음 실행할 때는 MySQL 이미지가 한 번 다운로드될 수 있습니다. 그 다음부터는 오프라인으로도 사용할 수 있습니다.")
        if st.sidebar.button("로컬 MySQL 시작", use_container_width=True):
            try:
                with st.spinner("Docker로 MySQL을 준비하는 중..."):
                    info = docker_utils.start_local_mysql()
                    engine = db_utils.get_engine(info.sqlalchemy_url)
                    with engine.connect() as conn:
                        conn.execute(db_utils.text("SELECT 1"))
                    st.session_state.db_url = info.sqlalchemy_url
                    st.session_state.local_mysql_info = {
                        "host": info.host,
                        "port": info.port,
                        "user": info.user,
                        "database": info.database,
                        "container_name": info.container_name,
                    }
                    st.sidebar.success(f"로컬 MySQL이 시작되었습니다. {info.host}:{info.port}")
                    st.rerun()
            except Exception as exc:
                st.sidebar.error(str(exc))

        local_info = st.session_state.get("local_mysql_info")
        if local_info and st.session_state.db_url.startswith("mysql"):
            st.sidebar.caption(
                f"현재 연결: {local_info['host']}:{local_info['port']} / {local_info['database']}"
            )
    else:
        st.sidebar.warning("Docker Desktop이 필요합니다.")
        st.sidebar.caption(message)
        st.sidebar.caption("처음 사용하는 경우에는 Docker를 먼저 설치해 주세요.")
        st.sidebar.caption("설치 후에는 이 앱이 MySQL 컨테이너를 자동으로 올릴 수 있습니다.")

        if st.sidebar.button("설치 방법 보기", use_container_width=True):
            docker_utils.open_docker_download_page()

        if st.sidebar.button("설치 파일 자동 다운로드", use_container_width=True):
            try:
                with st.spinner("Docker Desktop 설치 파일을 다운로드하는 중..."):
                    installer_path = docker_utils.download_docker_installer()
                st.sidebar.success(f"다운로드 완료: {installer_path}")
                st.sidebar.caption("설치 파일을 실행하면 Docker Desktop 설치가 시작됩니다.")
            except Exception as exc:
                st.sidebar.error(str(exc))

        if st.sidebar.button("다운로드 후 설치 실행", use_container_width=True):
            try:
                with st.spinner("설치 파일을 내려받고 실행하는 중..."):
                    installer_path = docker_utils.download_docker_installer()
                    docker_utils.launch_docker_installer(installer_path)
                st.sidebar.success("설치 파일을 실행했습니다. 설치를 마친 뒤 앱으로 돌아와 다시 시작해 주세요.")
            except Exception as exc:
                st.sidebar.error(str(exc))


def _render_remote_mysql_panel():
    st.sidebar.caption("기존 MySQL 서버에 직접 연결합니다.")
    host = st.sidebar.text_input("호스트", value="localhost")
    port = st.sidebar.text_input("포트", value="3306")
    user = st.sidebar.text_input("사용자", value="root")
    pwd = st.sidebar.text_input("비밀번호", type="password")
    db_name = st.sidebar.text_input("데이터베이스", value="test_db")

    if st.sidebar.button("연결 적용", use_container_width=True):
        try:
            if not re.fullmatch(r"[0-9A-Za-z$_]+", db_name):
                raise ValueError("데이터베이스 이름은 영문, 숫자, _, $만 사용할 수 있습니다.")
            port_i = int(port)
            server_url = URL.create(
                "mysql+pymysql",
                username=user,
                password=pwd,
                host=host,
                port=port_i,
                query={"charset": "utf8mb4"},
            )
            server_engine = db_utils.get_engine(server_url)
            with server_engine.begin() as conn:
                conn.execute(
                    db_utils.text(
                        f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                    )
                )

            db_url = URL.create(
                "mysql+pymysql",
                username=user,
                password=pwd,
                host=host,
                port=port_i,
                database=db_name,
                query={"charset": "utf8mb4"},
            ).render_as_string(hide_password=False)

            engine = db_utils.get_engine(db_url)
            with engine.connect() as conn:
                conn.execute(db_utils.text("SELECT 1"))
            st.session_state.db_url = db_url
            st.session_state.local_mysql_info = None
            st.sidebar.success("연결 완료")
        except Exception as exc:
            st.sidebar.error(str(exc))


def _sidebar():
    st.sidebar.title("DB-Buddy")
    st.sidebar.caption("가볍게 쓰는 DB 도우미")

    st.sidebar.subheader("연결")
    db_type = st.sidebar.radio(
        "유형",
        ["SQLite", "MySQL"],
        index=0 if not st.session_state.db_url.startswith("mysql") else 1,
        label_visibility="collapsed",
    )

    if db_type == "MySQL":
        st.sidebar.caption("MySQL을 로컬 Docker로 자동 실행할 수 있습니다. 처음 사용이라면 Docker Desktop이 필요합니다.")
        use_local_mysql = st.sidebar.checkbox("로컬 Docker MySQL 사용", value=True)
        if use_local_mysql:
            _render_local_mysql_panel()
        else:
            _render_remote_mysql_panel()
    else:
        st.session_state.db_url = db_utils.DEFAULT_SQLITE_URL
        st.sidebar.caption("SQLite는 인터넷 연결 없이 로컬에서 바로 쓸 수 있는 가벼운 데이터베이스입니다.")

    st.sidebar.divider()
    pages = ["DB", "SQL 작업실", "ERD", "설명"]
    if st.session_state.db_url.startswith("mysql"):
        pages = ["DB", "SQL 작업실", "ERD", "문서", "정규화", "설명"]

    if st.session_state.menu not in pages:
        st.session_state.menu = pages[0]

    st.session_state.menu = st.sidebar.radio("메뉴", pages, index=pages.index(st.session_state.menu))

    st.sidebar.divider()
    with st.sidebar.expander("스키마", expanded=False):
        try:
            st.code(db_utils.get_schema_info(st.session_state.db_url), language="sql")
        except Exception as exc:
            st.error(str(exc))

    with st.sidebar.expander("라이선스", expanded=False):
        st.caption("Streamlit - Apache 2.0")
        st.caption("LangChain - MIT")
        st.caption("Mermaid.js - MIT")
        st.caption("Faker - MIT")
        st.caption("PyMySQL - MIT")


def _render_db_page():
    st.header("DB")
    cols = st.columns(3)

    try:
        engine = db_utils.get_engine(st.session_state.db_url)
        from sqlalchemy import inspect

        inspector = inspect(engine)
        tables = inspector.get_table_names()
    except Exception as exc:
        st.error(str(exc))
        return

    cols[0].metric("테이블 수", len(tables))
    cols[1].metric("모드", "MySQL" if st.session_state.db_url.startswith("mysql") else "SQLite")
    cols[2].metric("준비 상태", "완료")

    title_col, action_col = st.columns([4, 2])
    with title_col:
        st.subheader("인스턴스 현황")
    with action_col:
        save_col, load_col = st.columns(2)
        with save_col:
            if st.button("DB 파일 저장", use_container_width=True):
                try:
                    save_path = _choose_save_path()
                    if save_path is None:
                        st.info("저장을 취소했습니다.")
                        save_path = None
                    else:
                        saved_path = db_utils.export_local_database_copy(save_path)
                        st.session_state.last_saved_db_path = str(saved_path)
                        st.success(f"저장 완료: {saved_path}")
                except Exception as exc:
                    st.error(str(exc))
        with load_col:
            if st.button("DB 파일 불러오기", use_container_width=True):
                st.session_state.show_db_upload = not st.session_state.get("show_db_upload", False)

    if st.session_state.get("last_saved_db_path"):
        st.caption(f"마지막 저장 위치: {st.session_state.last_saved_db_path}")

    if st.session_state.get("show_db_upload", False):
        with st.container(border=True):
            st.caption("SQLite DB 파일(.db, .sqlite, .sqlite3)을 업로드하면 현재 로컬 DB를 교체합니다.")
            uploaded_db = st.file_uploader(
                "DB 파일 선택",
                type=["db", "sqlite", "sqlite3"],
                key="local_db_upload",
                label_visibility="collapsed",
            )
            if uploaded_db is not None:
                with st.spinner("DB 파일을 불러오는 중..."):
                    try:
                        db_utils.replace_local_database_from_bytes(uploaded_db.getvalue())
                        st.session_state.db_url = db_utils.DEFAULT_SQLITE_URL
                        st.session_state.menu = "DB"
                        st.session_state.instance_table = ""
                        st.session_state.instance_search_open = False
                        st.session_state.instance_search_columns = []
                        st.session_state.instance_search_text = ""
                        st.session_state.show_db_upload = False
                        st.success("DB 파일을 불러왔습니다.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

    if not tables:
        st.info("아직 테이블이 없습니다.")
        return

    counts = []
    with engine.connect() as conn:
        for table in tables:
            try:
                count = conn.execute(db_utils.text(f"SELECT COUNT(*) FROM `{table}`")).scalar()
            except Exception:
                count = None
            counts.append({"table": table, "rows": count if count is not None else "n/a"})
    st.dataframe(pd.DataFrame(counts), use_container_width=True)

    if "instance_table" not in st.session_state or st.session_state.instance_table not in tables:
        st.session_state.instance_table = tables[0]
    if "instance_search_open" not in st.session_state:
        st.session_state.instance_search_open = False
    if "instance_search_columns" not in st.session_state:
        st.session_state.instance_search_columns = []
    if "instance_search_text" not in st.session_state:
        st.session_state.instance_search_text = ""

    instance_table = st.session_state.instance_table
    instance_df = pd.DataFrame()
    try:
        with engine.connect() as conn:
            instance_df = pd.read_sql_query(
                db_utils.text(f"SELECT * FROM `{instance_table}` LIMIT 200"),
                conn,
            )
    except Exception as exc:
        st.error(str(exc))

    with st.container(border=True):
        st.subheader("인스턴스")
        st.caption("선택한 테이블의 실제 행을 확인합니다.")

        if instance_df.empty:
            st.info("이 테이블에는 아직 표시할 인스턴스가 없습니다.")
        else:
            if st.session_state.instance_search_open:
                available_columns = list(instance_df.columns)
                if not st.session_state.instance_search_columns:
                    st.session_state.instance_search_columns = available_columns[:1]
                else:
                    current_columns = [
                        col for col in st.session_state.instance_search_columns if col in available_columns
                    ]
                    if current_columns != st.session_state.instance_search_columns:
                        st.session_state.instance_search_columns = current_columns or available_columns[:1]
                st.multiselect(
                    "검색할 속성",
                    available_columns,
                    key="instance_search_columns",
                    default=st.session_state.instance_search_columns,
                )
                st.text_input(
                    "검색어",
                    key="instance_search_text",
                    placeholder="예: 홍길동, 2026, 상태값",
                )
                st.caption("선택한 속성 안에서 입력한 검색어가 포함된 행만 보여줍니다.")

            filtered_df = instance_df
            search_cols = st.session_state.instance_search_columns
            search_text = st.session_state.instance_search_text.strip()
            if search_text and search_cols:
                mask = pd.Series(False, index=filtered_df.index)
                for col_name in search_cols:
                    if col_name in filtered_df.columns:
                        mask = mask | filtered_df[col_name].astype(str).str.contains(
                            re.escape(search_text),
                            case=False,
                            na=False,
                            regex=True,
                        )
                filtered_df = filtered_df[mask]

            st.dataframe(filtered_df, use_container_width=True, height=320)

        bottom_left, bottom_right = st.columns([4, 1])
        with bottom_left:
            st.selectbox(
                "테이블",
                tables,
                key="instance_table",
                label_visibility="collapsed",
            )
        with bottom_right:
            if st.button("검색 옵션 ▾", use_container_width=True):
                st.session_state.instance_search_open = not st.session_state.instance_search_open

    row_count = st.slider("테이블당 더미 행 수", 5, 50, 10, 5)
    c1, c2 = st.columns(2)
    if c1.button("더미 데이터 생성", use_container_width=True):
        with st.spinner("행을 생성하는 중..."):
            try:
                for table in db_utils.get_tables_in_topological_order(st.session_state.db_url):
                    db_utils.insert_dummy_data(st.session_state.db_url, table, row_count)
                st.success("완료")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    if c2.button("실습 DB 초기화", use_container_width=True):
        with st.spinner("초기화하는 중..."):
            try:
                db_utils.reset_database_to_default()
                st.session_state.erd_code = ""
                st.success("초기화 완료")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def _render_erd_page(db_url: str, cache_key: str = "erd_code", button_label: str = "ERD 생성"):
    st.header("ERD")
    st.caption("DB 구조를 바탕으로 다이어그램을 만듭니다.")
    if st.button(button_label, use_container_width=True):
        with st.spinner("생성 중..."):
            try:
                code = llm_chain.generate_erd_from_schema(db_url)
                st.session_state[cache_key] = code
                st.success("완료")
            except Exception as exc:
                st.error(str(exc))

    code = st.session_state.get(cache_key, "")
    if code:
        with st.container(border=True):
            st_mermaid(code, height=680)
        try:
            pdf_bytes = _build_erd_pdf_bytes(code)
            st.download_button(
                "PDF 다운로드",
                data=pdf_bytes,
                file_name="erd.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as exc:
            st.error(f"PDF를 만들지 못했습니다: {exc}")
        with st.expander("코드", expanded=False):
            st.code(code, language="mermaid")
    else:
        with st.container(border=True):
            st.info("ERD를 생성하면 여기에 크게 표시됩니다.")


def _parse_erd_mermaid(code: str):
    tables = []
    relations = []
    current = None

    for raw_line in code.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("%%"):
            continue
        if line.startswith("erDiagram"):
            continue

        table_match = re.match(r'^([A-Za-z0-9_`"]+)\s*\{$', line)
        if table_match:
            name = table_match.group(1).strip("`").strip('"')
            current = {"name": name, "columns": []}
            tables.append(current)
            continue

        if line == "}":
            current = None
            continue

        if current is not None:
            parts = line.split()
            if len(parts) >= 2:
                col_type = parts[0]
                col_name = parts[1]
                attrs = " ".join(parts[2:])
            else:
                col_type = ""
                col_name = line
                attrs = ""
            current["columns"].append(
                {"type": col_type, "name": col_name, "attrs": attrs}
            )
            continue

        rel_match = re.match(
            r'^([A-Za-z0-9_`"]+)\s+([|}{o\-]+)\s+([A-Za-z0-9_`"]+)\s*:\s*(.+)$',
            line,
        )
        if rel_match:
            relations.append(
                {
                    "left": rel_match.group(1).strip('`"'),
                    "kind": rel_match.group(2).strip(),
                    "right": rel_match.group(3).strip('`"'),
                    "label": rel_match.group(4).strip().strip('"').strip("'"),
                }
            )

    return tables, relations


def _fit_text(text: str, max_width: float, font_name: str, font_size: int, canvas) -> str:
    if canvas.stringWidth(text, font_name, font_size) <= max_width:
        return text

    ellipsis = "..."
    available = max(max_width - canvas.stringWidth(ellipsis, font_name, font_size), 0)
    if available <= 0:
        return ellipsis

    trimmed = text
    while trimmed and canvas.stringWidth(trimmed, font_name, font_size) > available:
        trimmed = trimmed[:-1]
    return trimmed + ellipsis


def _build_erd_pdf_bytes(code: str) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
    except Exception as exc:
        raise RuntimeError(f"PDF 생성용 라이브러리를 사용할 수 없습니다: {exc}") from exc

    tables, relations = _parse_erd_mermaid(code)
    buffer = BytesIO()
    page_w, page_h = landscape(A4)
    c = canvas.Canvas(buffer, pagesize=(page_w, page_h))

    font_regular = "Helvetica"
    font_bold = "Helvetica-Bold"
    try:
        if "Malgun" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("Malgun", r"C:\Windows\Fonts\malgun.ttf"))
        if "Malgun-Bold" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("Malgun-Bold", r"C:\Windows\Fonts\malgunbd.ttf"))
        font_regular = "Malgun"
        font_bold = "Malgun-Bold"
    except Exception:
        pass

    margin = 28
    title_y = page_h - margin
    c.setTitle("DB-Buddy ERD")
    c.setFont(font_bold, 18)
    c.drawString(margin, title_y, "DB-Buddy ERD")
    c.setFont(font_regular, 9)
    c.setFillColor(colors.HexColor("#666666"))
    c.drawString(margin, title_y - 14, "생성된 ERD를 PDF로 저장한 문서입니다.")
    c.setFillColor(colors.black)

    if not tables:
        c.setFont(font_regular, 11)
        c.drawString(margin, page_h / 2, "ERD 내용을 찾을 수 없습니다.")
        c.showPage()
        c.save()
        return buffer.getvalue()

    table_count = len(tables)
    cols = 2 if table_count <= 4 else 3 if table_count <= 9 else 4
    rows = ceil(table_count / cols)
    gap_x = 14
    gap_y = 18
    usable_w = page_w - margin * 2
    usable_h = page_h - margin * 2 - 42
    cell_w = (usable_w - gap_x * (cols - 1)) / cols
    cell_h = (usable_h - gap_y * (rows - 1)) / rows

    positions = {}
    for idx, table in enumerate(tables):
        row = idx // cols
        col = idx % cols
        x = margin + col * (cell_w + gap_x)
        y = page_h - margin - 42 - (row + 1) * cell_h - row * gap_y
        positions[table["name"]] = (x, y, cell_w, cell_h)

    for table in tables:
        x, y, w, h = positions[table["name"]]
        c.setStrokeColor(colors.HexColor("#444444"))
        c.setFillColor(colors.white)
        c.roundRect(x, y, w, h, 8, stroke=1, fill=1)

        header_h = 24
        c.setFillColor(colors.HexColor("#1f2937"))
        c.roundRect(x, y + h - header_h, w, header_h, 8, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont(font_bold, 11)
        title = _fit_text(table["name"], w - 16, font_bold, 11, c)
        c.drawString(x + 8, y + h - 16, title)

        c.setFillColor(colors.black)
        columns = table["columns"]
        font_size = 8
        line_h = 10
        available_h = h - header_h - 12
        if columns:
            scale = max(1, len(columns))
            if scale * line_h > available_h:
                font_size = max(6, int(available_h / scale) - 1)
                line_h = font_size + 2

        c.setFont(font_regular, font_size)
        text_y = y + h - header_h - 14
        max_text_w = w - 16
        for col_info in columns:
            col_name = col_info["name"]
            col_type = col_info["type"]
            attrs = col_info["attrs"]
            line = col_name
            if col_type:
                line = f"{line} ({col_type})"
            if attrs:
                line = f"{line} {attrs}"
            line = _fit_text(line, max_text_w, font_regular, font_size, c)
            c.drawString(x + 8, text_y, line)
            text_y -= line_h

    c.setStrokeColor(colors.HexColor("#9ca3af"))
    c.setFillColor(colors.HexColor("#374151"))
    c.setFont(font_regular, 8)
    for rel in relations:
        left = positions.get(rel["left"])
        right = positions.get(rel["right"])
        if not left or not right:
            continue

        lx = left[0] + left[2] / 2
        ly = left[1] + left[3] / 2
        rx = right[0] + right[2] / 2
        ry = right[1] + right[3] / 2
        mid_x = (lx + rx) / 2
        mid_y = (ly + ry) / 2

        c.line(lx, ly, rx, ry)
        c.circle(rx, ry, 2.2, stroke=1, fill=1)
        label = _fit_text(rel["label"], 120, font_regular, 8, c)
        c.drawString(mid_x + 4, mid_y + 4, label)

    c.showPage()
    c.save()
    return buffer.getvalue()


def _render_sql_lab(db_url: str, query_key: str = "current_query", gen_label: str = "SQL 생성", run_label: str = "쿼리 실행"):
    st.header("SQL 작업실")
    st.caption("자연어 요청을 먼저 SQL 문으로 바꾸고, 확인한 뒤 실제 데이터를 넣습니다.")

    prompt = st.text_area(
        "요청",
        value=st.session_state.get(query_key, ""),
        height=180,
        key=f"{query_key}_area",
        placeholder="예: 신규 고객 2명과 주문 1건 샘플을 넣어줘",
    )

    preview_key = f"{query_key}_preview_plan"
    preview_text_key = f"{query_key}_preview_text"
    preview_desc_key = f"{query_key}_preview_desc"
    executed_key = f"{query_key}_executed"

    if st.button("SQL문 생성", type="primary", use_container_width=True):
        request = prompt.strip()
        if not request:
            st.warning("먼저 요청 내용을 입력해 주세요.")
            return

        with st.spinner("어느 테이블에 넣을지 판단하는 중..."):
            try:
                plan = llm_chain.plan_data_insertion(request, db_url)
            except Exception as exc:
                st.error(str(exc))
                return

        target_table = plan.get("target_table")
        rows = plan.get("rows") or []
        reason = plan.get("reason", "")

        if not target_table or not isinstance(rows, list) or not rows:
            st.error("LLM이 유효한 삽입 계획을 만들지 못했습니다.")
            with st.expander("응답 내용", expanded=True):
                st.json(plan)
            return

        st.session_state[preview_key] = plan
        sql_preview = _build_insert_sql_preview(db_url, target_table, rows)
        st.session_state[preview_text_key] = sql_preview["preview_text"]
        st.session_state[preview_desc_key] = sql_preview["descriptions"]
        st.session_state[executed_key] = False

    plan = st.session_state.get(preview_key)
    preview_text = st.session_state.get(preview_text_key, "")
    preview_desc = st.session_state.get(preview_desc_key, [])

    with st.container(border=True):
        st.subheader("SQL문 전용 창")
        st.caption("이곳에 sql문이 생성됩니다.")

        if plan and preview_text:
            reason = plan.get("reason", "")
            if reason:
                st.markdown(f"**설명:** {reason}")
            st.text_area(
                "SQL 미리보기",
                value=preview_text,
                height=280,
                disabled=True,
                label_visibility="collapsed",
            )
            if preview_desc:
                st.caption("각 SQL문이 무엇을 하는지 아래에 설명합니다.")
                for item in preview_desc:
                    st.write(f"- {item}")
        else:
            st.text_area(
                "SQL 미리보기",
                value="이곳에 sql문이 생성됩니다.",
                height=280,
                disabled=True,
                label_visibility="collapsed",
            )

    execute_disabled = not bool(plan and preview_text)
    if st.button("SQL문 실행", type="primary", use_container_width=True, disabled=execute_disabled):
        if not plan:
            st.warning("먼저 SQL문을 생성해 주세요.")
            return

        target_table = plan.get("target_table", "")
        rows = plan.get("rows") or []
        with st.spinner("데이터를 넣는 중..."):
            try:
                inserted = db_utils.insert_rows(db_url, target_table, rows)
                st.success(f"{target_table}에 {inserted}행을 넣었습니다.")
                st.session_state[preview_key] = None
                st.session_state[preview_text_key] = ""
                st.session_state[preview_desc_key] = []
                st.session_state[executed_key] = True
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    if st.button("예고 지우기", use_container_width=True):
        st.session_state[preview_key] = None
        st.session_state[preview_text_key] = ""
        st.session_state[preview_desc_key] = []
        st.session_state[executed_key] = False
        st.rerun()


def _build_insert_sql_preview(db_url: str, table_name: str, rows: list) -> dict:
    """삽입 예정 SQL과 설명 문구를 생성"""
    if not table_name or not rows:
        return {"preview_text": "", "descriptions": []}

    engine = db_utils.get_engine(db_url)
    from sqlalchemy import inspect

    inspector = inspect(engine)
    column_info = {col["name"]: col for col in inspector.get_columns(table_name)}
    pk_columns = set(inspector.get_pk_constraint(table_name).get("constrained_columns", []) or [])

    preview_lines = []
    descriptions = []

    for idx, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue

        insert_row = {}
        for key, value in row.items():
            col_info = column_info.get(key)
            if not col_info or value is None:
                continue
            col_type = str(col_info["type"]).upper()
            if col_info.get("autoincrement") or (key in pk_columns and "INT" in col_type):
                continue
            insert_row[key] = value

        if not insert_row:
            continue

        columns = ", ".join(f"`{col}`" for col in insert_row.keys())
        values = ", ".join(_sql_literal(value) for value in insert_row.values())
        preview_lines.append(f"-- {idx}번째 문장: `{table_name}` 테이블에 한 행을 추가하는 INSERT 문입니다.")
        preview_lines.append(f"INSERT INTO `{table_name}` ({columns}) VALUES ({values});")
        descriptions.append(f"{idx}번째 문장: `{table_name}` 테이블에 한 행을 추가하는 INSERT 문입니다.")

    return {"preview_text": "\n".join(preview_lines), "descriptions": descriptions}


def _sql_literal(value):
    """SQL 미리보기용 값 포맷"""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    text = str(value).replace("\\", "\\\\").replace("'", "''")
    return f"'{text}'"


def _render_explain(db_url: str, query_key: str = "current_query"):
    st.header("실행 계획")
    st.caption("SQL이 어떻게 실행되는지 보고, 느린 이유와 개선 방향을 함께 살펴봅니다.")
    query = st.text_area("분석할 SQL", value=st.session_state.get(query_key, ""), height=140)
    if st.button("실행 계획 분석", use_container_width=True):
        if not query.strip():
            st.warning("먼저 SQL을 입력해 주세요.")
            return
        with st.spinner("EXPLAIN 실행 중..."):
            explain = db_utils.execute_explain_plan(query, db_url)
            if "error" in explain.lower():
                st.error(explain)
            else:
                st.code(explain, language="text")
                with st.spinner("AI에 분석을 요청하는 중..."):
                    try:
                        result = llm_chain.analyze_explain_plan(query, explain)
                        st.markdown(result)
                    except Exception as exc:
                        st.error(str(exc))


def _render_mysql_docs(db_url: str):
    st.header("문서")
    if st.button("문서 생성", type="primary", use_container_width=True):
        with st.spinner("문서를 만드는 중..."):
            try:
                st.session_state.mysql_docs = llm_chain.generate_db_documentation(db_url)
                st.success("완료")
            except Exception as exc:
                st.error(str(exc))

    docs = st.session_state.get("mysql_docs", "")
    if docs:
        st.markdown(docs)
        st.download_button("다운로드", docs, file_name="mysql_db_dictionary.md", mime="text/markdown")


def _render_normalize(db_url: str):
    st.header("정규화")
    req = st.text_area("요청 사항", height=160)
    if st.button("개선안 생성", type="primary", use_container_width=True):
        if not req.strip():
            st.warning("먼저 요청 사항을 입력해 주세요.")
            return
        with st.spinner("생각하는 중..."):
            try:
                st.markdown(llm_chain.assist_db_normalization(req, db_url))
            except Exception as exc:
                st.error(str(exc))


def main():
    _ensure_local_db()
    _init_state()
    _sidebar()

    st.title("DB-Buddy")
    st.caption("ERD, SQL, 스키마 작업을 돕는 간단한 도구입니다.")

    menu = st.session_state.menu
    db_url = st.session_state.db_url

    if menu == "DB":
        _render_db_page()
    elif menu == "SQL 작업실":
        _render_sql_lab(db_url)
    elif menu == "ERD":
        _render_erd_page(db_url)
    elif menu == "설명":
        _render_explain(db_url)
    elif menu == "문서":
        _render_mysql_docs(db_url)
    elif menu == "정규화":
        _render_normalize(db_url)


if __name__ == "__main__":
    main()
