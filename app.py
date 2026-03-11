import streamlit as st
import json
import io
import zipfile
import datetime
import base64

from csat_parser import CSATParser
from highschool_parser import HighSchoolParser

# ==========================================
# 페이지 설정
# ==========================================
st.set_page_config(
    page_title="Roy's TXT → JSON 변환기",
    page_icon="🔄",
    layout="wide"
)

st.markdown("""
<style>
    .main-title { font-size: 2.2rem; font-weight: 900; color: #003b6f; margin-bottom: 0; letter-spacing: -1px; }
    .sub-title { font-size: 1rem; color: #78909c; font-weight: 500; margin-top: -10px; margin-bottom: 30px; }
    .log-box { background: #263238; color: #b0bec5; font-family: 'Courier New', monospace; font-size: 13px;
               padding: 15px; border-radius: 8px; max-height: 300px; overflow-y: auto; line-height: 1.6; }
    .log-ok { color: #66bb6a; } .log-err { color: #ef5350; } .log-warn { color: #ffa726; } .log-info { color: #42a5f5; }
    .log-time { color: #78909c; }
    .stDownloadButton > button { width: 100%; font-weight: 700; font-size: 1rem; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">Roy\'s TXT → JSON 변환기</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Gemini에서 생성한 TXT 파일을 교재 엔진용 JSON으로 변환합니다.</div>', unsafe_allow_html=True)


# ==========================================
# 로그 시스템
# ==========================================
def init_log():
    if 'converter_log' not in st.session_state:
        st.session_state['converter_log'] = []


def log(msg, level="info"):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    icon = {"ok": "✅", "err": "❌", "warn": "⚠️", "info": "📋"}.get(level, "📋")
    css = {"ok": "log-ok", "err": "log-err", "warn": "log-warn", "info": "log-info"}.get(level, "log-info")
    st.session_state['converter_log'].append(
        f'<span class="log-time">[{now}]</span> {icon} <span class="{css}">{msg}</span>'
    )


def render_log():
    if st.session_state.get('converter_log'):
        lines = "<br>".join(st.session_state['converter_log'])
        st.markdown(f'<div class="log-box">{lines}</div>', unsafe_allow_html=True)


def auto_download(data_bytes, file_name, mime_type):
    b64 = base64.b64encode(data_bytes).decode()
    html = f'''
    <html><body>
    <script>
        var a = document.createElement("a");
        a.href = "data:{mime_type};base64,{b64}";
        a.download = "{file_name}";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    </script>
    </body></html>
    '''
    st.components.v1.html(html, height=0, width=0)


# ==========================================
# 변환 처리
# ==========================================
def convert_files(uploaded_files, parser_type):
    init_log()
    st.session_state['converter_log'] = []

    parser_name = "모의고사용 (CSATParser)" if parser_type == "csat" else "내신 교과서용 (HighSchoolParser)"
    log(f"변환 모드: {parser_name}", "info")
    log(f"{len(uploaded_files)}개 TXT 파일 변환을 시작합니다.", "info")

    results = {}
    errors = []

    # 파일명 순 정렬
    sorted_files = sorted(uploaded_files, key=lambda x: x.name)

    progress_bar = st.progress(0, text="변환 중...")

    for i, uf in enumerate(sorted_files):
        progress_bar.progress((i + 1) / len(uploaded_files), text=f"변환 중: {uf.name}")

        try:
            content = uf.getvalue().decode('utf-8')

            if parser_type == "csat":
                parser = CSATParser(content)
            else:
                parser = HighSchoolParser(content)

            json_dict = parser.to_dict()
            json_str = json.dumps(json_dict, ensure_ascii=False, indent=2)

            json_filename = uf.name.replace('.txt', '.json')
            results[json_filename] = json_str
            log(f"  {uf.name} → {json_filename}", "ok")

        except Exception as e:
            errors.append(f"{uf.name}: {str(e)}")
            log(f"  {uf.name} 변환 실패: {str(e)}", "err")

    progress_bar.progress(1.0, text="완료!")

    total_msg = f"총 {len(results)}개 변환 완료"
    if errors:
        total_msg += f" ({len(errors)}개 실패)"
        log(total_msg, "warn")
    else:
        log(total_msg, "ok")

    return results, errors


# ==========================================
# 메인 UI
# ==========================================
st.markdown("### 변환 유형 선택")

parser_type = st.radio(
    "TXT 파일의 유형을 선택하세요:",
    options=["csat", "highschool"],
    format_func=lambda x: "모의고사용 (수능/모의고사 분석 TXT)" if x == "csat" else "내신 교과서용 (교과서 본문 분석 TXT)",
    horizontal=True
)

st.markdown("---")

uploaded_files = st.file_uploader(
    "TXT 파일을 드래그하여 업로드하세요 (복수 선택 가능)",
    type=['txt'],
    accept_multiple_files=True,
    help="Gemini에서 생성한 분석 TXT 파일을 여기에 올리면 됩니다."
)

if uploaded_files:
    st.markdown(f"**{len(uploaded_files)}개 파일 업로드됨**")

    with st.expander("업로드된 파일 목록", expanded=False):
        for uf in sorted(uploaded_files, key=lambda x: x.name):
            size_kb = len(uf.getvalue()) / 1024
            st.markdown(f"- `{uf.name}` ({size_kb:.1f} KB)")

    if st.button("JSON으로 변환하기", type="primary", use_container_width=True):
        results, errors = convert_files(uploaded_files, parser_type)

        if results:
            st.session_state['json_results'] = results
            st.session_state['conversion_done'] = True

            # 자동 다운로드: 파일이 1개면 JSON, 여러개면 ZIP
            if len(results) == 1:
                fname = list(results.keys())[0]
                auto_download(list(results.values())[0].encode('utf-8'), fname, "application/json")
                log(f"자동 다운로드: {fname}", "ok")
            else:
                zip_buf = io.BytesIO()
                with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for name, data in results.items():
                        zf.writestr(name, data)
                zip_buf.seek(0)
                zip_name = sorted(results.keys())[0].replace('.json', '') + ".zip"
                auto_download(zip_buf.getvalue(), zip_name, "application/zip")
                log(f"자동 다운로드: {zip_name}", "ok")

    # JSON 다운로드 버튼
    if st.session_state.get('conversion_done') and st.session_state.get('json_results'):
        json_results = st.session_state['json_results']

        st.markdown("---")
        st.markdown("### JSON 다운로드")

        for fname, json_str in json_results.items():
            col1, col2 = st.columns([3, 1])
            with col1:
                st.download_button(
                    f"{fname}",
                    data=json_str.encode('utf-8'),
                    file_name=fname,
                    mime="application/json",
                    use_container_width=True,
                    key=f"dl_{fname}"
                )
            with col2:
                with st.expander("미리보기"):
                    st.json(json.loads(json_str))

        if len(json_results) > 1:
            st.markdown("---")
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for name, data in json_results.items():
                    zf.writestr(name, data)
            zip_buffer.seek(0)

            first_name = sorted(json_results.keys())[0].replace('.json', '')
            st.download_button(
                "전체 JSON ZIP 다운로드",
                data=zip_buffer.getvalue(),
                file_name=first_name + ".zip",
                mime="application/zip",
                use_container_width=True,
                key="dl_zip"
            )

    # 로그 표시 (항상 하단에 표시)
    init_log()
    if st.session_state.get('converter_log'):
        st.markdown("---")
        st.markdown("#### 처리 로그")
        render_log()

else:
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### 1. 유형 선택\n모의고사용 또는\n내신 교과서용을 선택하세요.")
    with col2:
        st.markdown("#### 2. 업로드\nGemini에서 생성한\nTXT 파일을 올리세요.")
    with col3:
        st.markdown("#### 3. 다운로드\n변환된 JSON 파일을\n다운로드하세요.")
