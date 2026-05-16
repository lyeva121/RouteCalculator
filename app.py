import streamlit as st
import math
import json
import io
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Настройка страницы Streamlit (адаптивный дизайн под iPad)
st.set_page_config(page_title="Расчёт маршрута", layout="wide", initial_sidebar_state="collapsed")

# --- РАЗРАБОТЧИК ---
st.markdown(
    "<div style='text-align: right; color: gray; font-style: italic; font-size: 14px;'>"
    "Разработчик Лёвочкин Виктор</div>", 
    unsafe_allow_html=True
)

# --- ИНИЦИАЛИЗАЦИЯ И ОБРАБОТКА ИЗМЕНЕНИЙ СОСТОЯНИЯ ---
if "speed" not in st.session_state:
    st.session_state.speed = 200.0
if "wind_dir" not in st.session_state:
    st.session_state.wind_dir = 0.0
if "wind_speed" not in st.session_state:
    st.session_state.wind_speed = 0.0
if "num_rows" not in st.session_state:
    st.session_state.num_rows = 10
if "route_data" not in st.session_state:
    st.session_state.route_data = [{"point": "", "zmpu": "", "distance": ""} for _ in range(10)]
if "calculated" not in st.session_state:
    st.session_state.calculated = False
if "results" not in st.session_state:
    st.session_state.results = {}

# Математические функции из вашего исходного кода
def calculate_mk(zmpu, wind_dir, wind_speed, speed):
    angle = math.radians(wind_dir + 180 - zmpu)
    correction = ((57.3 * wind_speed) / speed) * math.sin(angle)
    res = round(zmpu - correction)
    return res % 360

def calculate_time(distance, zmpu, wind_dir, wind_speed, speed):
    angle = math.radians(wind_dir + 180 - zmpu)
    ground_speed = speed + wind_speed * math.cos(angle)
    return distance / ground_speed if ground_speed > 0 else 0

def do_calculation():
    try:
        sp = float(st.session_state.speed)
        wd = float(st.session_state.wind_dir)
        ws = float(st.session_state.wind_speed)
    except ValueError:
        st.error("Проверьте параметры скорости и ветра. Они должны быть числами.")
        return

    total_min, total_dist = 0, 0
    calculated_rows = []

    for i in range(st.session_state.num_rows):
        p = st.session_state.get(f"p_{i}", "").strip()
        
        if i == 0:
            calculated_rows.append({"point": p, "distance": "—", "mk": "—", "time": "—"})
            continue
            
        if not p:
            calculated_rows.append({"point": "", "distance": "", "mk": "", "time": ""})
            continue

        try:
            z_val = st.session_state.get(f"z_{i}", "")
            d_val = st.session_state.get(f"d_{i}", "")
            zmpu = float(z_val) if z_val else 0.0
            dist = float(d_val) if d_val else 0.0
        except ValueError:
            continue

        if zmpu < 0 or zmpu > 359:
            st.error(f"Строка {i+1}: ЗМПУ должен быть в диапазоне 0–359")
            return

        mk = calculate_mk(zmpu, wind_dir, wind_speed, speed)
        f_time = calculate_time(dist, zmpu, wind_dir, wind_speed, speed)
        minutes = round(f_time * 60)
        total_min += minutes
        total_dist += dist

        time_str = f"{minutes//60}:{minutes%60:02d} / {total_min//60}:{total_min%60:02d}"
        calculated_rows.append({
            "point": p,
            "distance": str(dist),
            "mk": str(mk),
            "time": time_str
        })

    st.session_state.results = {
        "rows": calculated_rows,
        "total_distance": round(total_dist),
        "total_time": f"{total_min//60}:{total_min%60:02d}"
    }
    st.session_state.calculated = True

# Функция реверса маршрута
def reverse_route():
    valid_data = []
    for i in range(st.session_state.num_rows):
        p = st.session_state.get(f"p_{i}", "").strip()
        z = st.session_state.get(f"z_{i}", "")
        d = st.session_state.get(f"d_{i}", "")
        if p:
            valid_data.append({"point": p, "zmpu": z, "distance": d})
    
    if len(valid_data) < 2:
        st.error("Недостаточно ППМ для реверса")
        return

    rev_points = list(reversed(valid_data))
    new_zmpu, new_dist = [], []
    for item in reversed(valid_data[1:]):
        try:
            nc = (float(item["zmpu"]) + 180) % 360
            new_zmpu.append(str(round(nc)))
            new_dist.append(item["distance"])
        except ValueError:
            new_zmpu.append("")
            new_dist.append("")

    # Обновляем session_state данными реверса
    st.session_state.num_rows = max(10, len(rev_points))
    st.session_state.route_data = [{"point": "", "zmpu": "", "distance": ""} for _ in range(st.session_state.num_rows)]
    
    for i, item in enumerate(rev_points):
        st.session_state.route_data[i]["point"] = item["point"]
        if i > 0:
            st.session_state.route_data[i]["zmpu"] = new_zmpu[i-1]
            st.session_state.route_data[i]["distance"] = new_dist[i-1]
    
    st.session_state.calculated = False
    st.rerun()

# Функция сброса
def reset_route():
    st.session_state.speed = 200.0
    st.session_state.wind_dir = 0.0
    st.session_state.wind_speed = 0.0
    st.session_state.num_rows = 10
    st.session_state.route_data = [{"point": "", "zmpu": "", "distance": ""} for _ in range(10)]
    st.session_state.calculated = False
    st.session_state.results = {}
    st.rerun()

# --- ИНТЕРФЕЙС: ВВОД ДАННЫХ ВЕРХНЕЙ ПАНЕЛИ ---
st.title("Калькулятор навигационного расчёта маршрута")

col1, col2, col3 = st.columns(3)
with col1:
    speed = st.number_input("Скорость истинная (км/ч)", value=float(st.session_state.speed), key="speed", step=5.0)
with col2:
    wind_dir = st.number_input("Направление ветра метео (°)", value=float(st.session_state.wind_dir), key="wind_dir", step=5.0)
with col3:
    wind_speed = st.number_input("Скорость ветра (км/ч)", value=float(st.session_state.wind_speed), key="wind_speed", step=2.0)

# --- ИНТЕРФЕЙС: УПРАВЛЕНИЕ ФАЙЛАМИ (ОТКРЫТЬ/СОХРАНИТЬ) ---
st.subheader("Работа с файлами маршрутов")
f_col1, f_col2 = st.columns(2)

with f_col1:
    uploaded_file = st.file_uploader("Открыть маршрут (.json)", type=["json"])
    if uploaded_file is not None:
        try:
            file_data = json.load(uploaded_file)
            st.session_state.speed = float(file_data.get("speed", 200))
            st.session_state.wind_dir = float(file_data.get("wind_dir", 0))
            st.session_state.wind_speed = float(file_data.get("wind_speed", 0))
            rows_data = file_data.get("rows", [])
            st.session_state.num_rows = max(10, len(rows_data))
            st.session_state.route_data = [{"point": "", "zmpu": "", "distance": ""} for _ in range(st.session_state.num_rows)]
            for i, r_data in enumerate(rows_data):
                st.session_state.route_data[i]["point"] = r_data.get("point", "")
                st.session_state.route_data[i]["zmpu"] = r_data.get("zmpu", "")
                st.session_state.route_data[i]["distance"] = r_data.get("distance", "")
            st.session_state.calculated = False
            st.success("Маршрут успешно загружен из файла!")
            st.rerun()
        except Exception as e:
            st.error(f"Ошибка чтения файла: {e}")

with f_col2:
    # Готовим структуру для сохранения текущих введенных данных
    save_data = {
        "speed": st.session_state.speed,
        "wind_dir": st.session_state.wind_dir,
        "wind_speed": st.session_state.wind_speed,
        "rows": []
    }
    for i in range(st.session_state.num_rows):
        save_data["rows"].append({
            "point": st.session_state.get(f"p_{i}", ""),
            "zmpu": st.session_state.get(f"z_{i}", ""),
            "distance": st.session_state.get(f"d_{i}", "")
        })
    json_string = json.dumps(save_data, ensure_ascii=False, indent=4)
    st.download_button(
        label="Сохранить текущий маршрут (.json)",
        data=json_string,
        file_name="route_export.json",
        mime="application/json"
    )

# --- ИНТЕРФЕЙС: ТАБЛИЦА МАРШРУТА ---
st.subheader("Таблица навигационных элементов")

# Заголовки таблицы
t_headers = st.columns([3, 2, 2, 2, 3])
t_headers[0].markdown("**ППМ**")
t_headers[1].markdown("**ЗМПУ (°)**")
t_headers[2].markdown("**Расстояние (км)**")
t_headers[3].markdown("**МК (°)**")
t_headers[4].markdown("**Время (этап / общ.)**")

# Вывод строк для ввода
for i in range(st.session_state.num_rows):
    cols = st.columns([3, 2, 2, 2, 3])
    
    # Подгружаем дефолтные значения из памяти состояния (из сохраненного/открытого файла)
    default_p = st.session_state.route_data[i]["point"] if i < len(st.session_state.route_data) else ""
    default_z = st.session_state.route_data[i]["zmpu"] if i < len(st.session_state.route_data) else ""
    default_d = st.session_state.route_data[i]["distance"] if i < len(st.session_state.route_data) else ""

    p_val = cols[0].text_input(f"ППМ {i+1}", value=default_p, label_visibility="collapsed", key=f"p_{i}")
    
    if i == 0:
        cols[1].markdown("<div style='text-align: center; color: gray;'>—</div>", unsafe_allow_html=True)
        cols[2].markdown("<div style='text-align: center; color: gray;'>—</div>", unsafe_allow_html=True)
    else:
        cols[1].text_input(f"ЗМПУ {i+1}", value=default_z, label_visibility="collapsed", key=f"z_{i}")
        cols[2].text_input(f"Расстояние {i+1}", value=default_d, label_visibility="collapsed", key=f"d_{i}")

    # Динамический вывод результатов расчета, если он был выполнен
    if st.session_state.calculated and st.session_state.results:
        res_row = st.session_state.results["rows"][i]
        cols[3].markdown(f"<div style='text-align: center; font-weight: bold;'>{res_row['mk']}</div>", unsafe_allow_html=True)
        cols[4].markdown(f"<div style='text-align: center; font-weight: bold;'>{res_row['time']}</div>", unsafe_allow_html=True)
    else:
        cols[3].markdown("<div style='text-align: center; color: gray;'>...</div>", unsafe_allow_html=True)
        cols[4].markdown("<div style='text-align: center; color: gray;'>...</div>", unsafe_allow_html=True)

# --- ИНТЕРФЕЙС: УПРАВЛЯЮЩИЕ КНОПКИ ---
st.markdown("---")
b_col1, b_col2, b_col3 = st.columns(3)

with b_col1:
    if st.button("➕ Добавить ППМ", use_container_width=True):
        st.session_state.num_rows += 1
        # Сохраняем текущие введенные данные, чтобы они не стерлись при перерисовке
        for idx in range(st.session_state.num_rows - 1):
            st.session_state.route_data[idx]["point"] = st.session_state.get(f"p_{idx}", "")
            st.session_state.route_data[idx]["zmpu"] = st.session_state.get(f"z_{idx}", "") if idx > 0 else ""
            st.session_state.route_data[idx]["distance"] = st.session_state.get(f"d_{idx}", "") if idx > 0 else ""
        st.session_state.route_data.append({"point": "", "zmpu": "", "distance": ""})
        st.rerun()

with b_col2:
    if st.button("🔄 Реверс маршрута", use_container_width=True):
        reverse_route()

with b_col3:
    if st.button("🗑️ Новый маршрут (Очистить)", use_container_width=True):
        reset_route()

# Крупная кнопка запуска расчета
st.markdown("<br>", unsafe_allow_html=True)
if st.button("🚀 РАСЧЁТ МАРШРУТА", type="primary", use_container_width=True):
    do_calculation()
    st.rerun()

# --- ВЫВОД ИТОГОВЫХ РЕЗУЛЬТАТОВ И ЭКСПОРТ В PDF ---
if st.session_state.calculated and st.session_state.results:
    res = st.session_state.results
    st.info(f"**Общее расстояние:** {res['total_distance']} км  \n**Общее время полета:** {res['total_time']}")

    # --- СБОРКА PDF В ПАМЯТИ ---
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    
    # Стандартные шрифты Helvetica/Times используются для веб-генерации (английский и цифры).
    # Для отображения кириллицы в ReportLab на сервере убедитесь, что файл шрифта доступен, либо используйте базовые стили.
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], alignment=1)
    
    story = [
        Paragraph("БОРТОВОЙ ЖУРНАЛ / НАВИГАЦИОННЫЙ РАСЧЕТ", title_style),
        Spacer(1, 15)
    ]
    
    # Подготовка таблицы для ReportLab PDF
    pdf_table_data = [["ППМ", "Расстояние (км)", "МК (°)", "Время (эт / общ)"]]
    for row in res["rows"]:
        if row["point"]: # Экспортируем только заполненные строки
            pdf_table_data.append([row["point"], row["distance"], row["mk"], row["time"]])
            
    table = Table(pdf_table_data, colWidths=[5*cm, 4*cm, 3*cm, 5*cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    story.append(Spacer(1, 15))
    
    # Блок общей информации
    info_text = (
        f"<b>Параметры полета:</b> Истинная скорость: {speed} км/ч | "
        f"Ветер: {wind_dir}° / {wind_speed} км/ч<br/><br/>"
        f"<b>ИТОГО:</b><br/>"
        f"Общее расстояние: {res['total_distance']} км<br/>"
        f"Общее время: {res['total_time']}"
    )
    story.append(Paragraph(info_text, styles['Normal']))
    
    # Сборка документа
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    
    # Кнопка скачивания готового PDF для iPad
    st.download_button(
        label="📥 СКАЧАТЬ РАСЧЁТ ПОЛЁТА (PDF)",
        data=pdf_bytes,
        file_name="flight_plan.pdf",
        mime="application/pdf",
        use_container_width=True
    )