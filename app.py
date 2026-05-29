import math
import json
import os
import tempfile
import streamlit as st

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

# --- КОНФИГУРАЦИЯ СТРАНИЦЫ И СТИЛИЗАЦИЯ (CSS) ---
# Настройка страницы Streamlit
st.set_page_config(page_title="Расчёт маршрута", layout="wide", initial_sidebar_state="collapsed")

# Внедрение кастомного CSS для достижения внешнего вида как на картинке
st.markdown("""
<style>
    /* Глобальные настройки темы и отступов */
    .reportview-container .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        padding-left: 2rem;
        padding-right: 2rem;
        background-color: #1a1d21; /* Очень темный фон, как на картинке */
        color: #ffffff;
    }
    .stApp {
        background-color: #1a1d21;
    }
    
    /* Стилизация заголовков */
    h1 {
        margin-top: 0rem !important;
        margin-bottom: 0rem !important;
        font-size: 2.2rem !important;
        color: #3ddc84 !important; /* Насыщенный зеленый для главного заголовка */
    }
    .route-subtitle {
        color: #a0aab4; /* Серый цвет для подзаголовка */
        font-size: 1rem;
        margin-top: -5px;
        margin-bottom: 15px;
    }

    /* Стилизация полей ввода (input) */
    .stTextInput input {
        background-color: #2b3036; /* Темный фон полей */
        color: #ffffff;
        border: 1px solid #3e444b;
        border-radius: 4px;
        padding: 5px;
        height: 38px;
    }
    .stTextInput label {
        color: #ffffff !important; /* Белый цвет лейблов */
        font-size: 0.9rem;
    }
    
    /* Стилизация чекбокса */
    .stCheckbox label span p {
        color: #ffffff !important;
        font-size: 0.9rem;
    }
    .stCheckbox [data-testid="stCheckboxInput"] {
        background-color: #2b3036;
        border: 1px solid #3e444b;
    }

    /* Стилизация таблицы (Columns) */
    [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] {
        gap: 0.5rem; /* Уменьшаем отступы между колонками */
    }
    .table-header {
        font-size: 13px;
        font-weight: bold;
        color: #8fa0ac; /* Серо-голубой цвет заголовков таблицы */
        text-transform: uppercase; /* Все заглавные */
        margin-bottom: 5px;
    }
    
    /* Стилизация расчетных ячеек (МК, Время) */
    .calc-cell {
        padding: 8px 0;
        text-align: center;
        font-size: 14px;
        background: #23272d; /* Чуть светлее фона, чтобы выделить */
        border-radius: 4px;
        border: 1px solid #3e444b;
        color: #a0aab4;
        min-height: 38px;
    }

    /* Стилизация кнопок */
    .stButton>button {
        background-color: #2b3036; /* Темные кнопки */
        color: #ffffff;
        border: 1px solid #3e444b;
        border-radius: 4px;
        font-size: 14px;
        padding: 8px 16px;
        transition: background-color 0.3s;
    }
    .stButton>button:hover {
        background-color: #3e444b;
        border-color: #3e444b;
        color: #ffffff;
    }
    
    /* Стиль для кнопки 'Новый маршрут' (Красная) */
    [data-testid="stHorizontalBlock"] > div:nth-child(4) .stButton>button {
        background-color: #dc3545;
        border-color: #dc3545;
        color: #ffffff;
    }
    [data-testid="stHorizontalBlock"] > div:nth-child(4) .stButton>button:hover {
        background-color: #c82333;
    }

    /* Стилизация кнопки 'РАСЧЁТ' (Зеленая) */
    div.calc-btn-container .stButton>button {
        background-color: #3ddc84; /* Ярко-зеленая */
        color: #1a1d21; /* Темный текст */
        font-weight: bold;
        border: none;
    }
    div.calc-btn-container .stButton>button:hover {
        background-color: #2ebf6f;
        color: #1a1d21;
    }

    /* Итоговая панель (Расстояние/Время) */
    .summary-text {
        font-size: 15px;
        color: #a0aab4;
        margin-top: 10px;
    }
    .summary-text b {
        color: #ffffff;
    }

    /* Футер */
    .footer {
        text-align: center;
        font-size: 12px;
        color: #5c646d;
        margin-top: 30px;
        margin-bottom: 0px;
    }
</style>
""", unsafe_allow_html=True)

# --- ИНИЦИАЛИЗАЦИЯ ШРИФТА ДЛЯ PDF ---
PDF_FONT = "Helvetica"
if os.path.exists("DejaVuSans.ttf"):
    try:
        pdfmetrics.registerFont(TTFont("DejaVu", "DejaVuSans.ttf"))
        PDF_FONT = "DejaVu"
    except Exception:
        pass

# --- МАТЕМАТИЧЕСКИЕ ФУНКЦИИ ---
def calculate_mk(zmpu, wind_dir, wind_speed, speed):
    angle = math.radians(wind_dir + 180 - zmpu)
    correction = ((57.3 * wind_speed) / speed) * math.sin(angle)
    res = round(zmpu - correction)
    return res % 360

def calculate_time(distance, zmpu, wind_dir, wind_speed, speed):
    angle = math.radians(wind_dir + 180 - zmpu)
    ground_speed = speed + wind_speed * math.cos(angle)
    return distance / ground_speed if ground_speed > 0 else 0

# --- ИНИЦИАЛИЗАЦИЯ СОСТОЯНИЯ (SESSION STATE) ---
if "rows_count" not in st.session_state:
    st.session_state.rows_count = 10

if "form_data" not in st.session_state:
    st.session_state.form_data = {}

# --- ФУНКЦИЯ СИНХРОНИЗАЦИИ ВВОДА ---
def sync_inputs():
    """ Сохраняет текущие введенные пользователем данные в сессию """
    st.session_state.form_data["speed"] = st.session_state.get("speed_field", "")
    st.session_state.form_data["same_wind"] = st.session_state.get("same_wind_field", False)
    for idx in range(st.session_state.rows_count):
        st.session_state.form_data[f"p_{idx}"] = st.session_state.get(f"input_p_{idx}", "")
        st.session_state.form_data[f"z_{idx}"] = st.session_state.get(f"input_z_{idx}", "")
        st.session_state.form_data[f"d_{idx}"] = st.session_state.get(f"input_d_{idx}", "")
        st.session_state.form_data[f"wd_{idx}"] = st.session_state.get(f"input_wd_{idx}", "")
        st.session_state.form_data[f"ws_{idx}"] = st.session_state.get(f"input_ws_{idx}", "")

# --- ЗАГОЛОВОК И НАСТРОЙКИ (Как на картинке) ---
header_col1, header_col2 = st.columns([2, 2])

with header_col1:
    st.title("Расчёт маршрута")
    st.markdown("<p class='route-subtitle'>Мин Воды - Экспоград</p>", unsafe_allow_html=True)

with header_col2:
    settings_cols = st.columns([1, 2])
    with settings_cols[0]:
        default_speed = st.session_state.form_data.get("speed", "")
        speed_input = st.text_input("Скорость (км/ч):", value=default_speed, key="speed_field", label_visibility="visible", on_change=sync_inputs)
    with settings_cols[1]:
        # Отступ, чтобы выровнять чекбокс по центру поля ввода
        st.markdown("<div style='margin-top: 35px;'></div>", unsafe_allow_html=True)
        default_same_wind = st.session_state.form_data.get("same_wind", False)
        same_wind_input = st.checkbox("Ветер по всему маршруту одинаковый", value=default_same_wind, key="same_wind_field", on_change=sync_inputs)

# --- ТАБЛИЦА ВВОДА ДАННЫХ (Компактные ячейки, темный стиль) ---
# Пропорции колонок максимально близки к картинке
col_widths = [2.5, 1.3, 1.3, 1.6, 1.6, 1.3, 2.5]

cols = st.columns(col_widths)
cols[0].markdown("<div class='table-header'>ППМ</div>", unsafe_allow_html=True)
cols[1].markdown("<div class='table-header' style='text-align:center;'>ЗМПУ (°)</div>", unsafe_allow_html=True)
cols[2].markdown("<div class='table-header' style='text-align:center;'>Расст. (км)</div>", unsafe_allow_html=True)
cols[3].markdown("<div class='table-header' style='text-align:center;'>Ветер Метео (°)</div>", unsafe_allow_html=True)
cols[4].markdown("<div class='table-header' style='text-align:center;'>Ветер Скор. км/ч</div>", unsafe_allow_html=True)
cols[5].markdown("<div class='table-header' style='text-align:center; color:#3ddc84;'>МК</div>", unsafe_allow_html=True)
cols[6].markdown("<div class='table-header' style='text-align:center; color:#3ddc84;'>Время Ч:ММ / Ч:ММ</div>", unsafe_allow_html=True)

table_rows = []

for i in range(st.session_state.rows_count):
    cols = st.columns(col_widths)
    
    p_val = st.session_state.form_data.get(f"p_{i}", "")
    z_val = st.session_state.form_data.get(f"z_{i}", "")
    d_val = st.session_state.form_data.get(f"d_{i}", "")
    wd_val = st.session_state.form_data.get(f"wd_{i}", "")
    ws_val = st.session_state.form_data.get(f"ws_{i}", "")
    
    # Расчетные значения теперь серые по умолчанию
    mk_val = st.session_state.form_data.get(f"mk_{i}", "—" if i == 0 else "—")
    time_val = st.session_state.form_data.get(f"time_{i}", "—" if i == 0 else "— / —")
    
    is_first = (i == 0)
    
    point = cols[0].text_input(f"ППМ {i}", value=p_val, label_visibility="collapsed", key=f"input_p_{i}", on_change=sync_inputs)
    
    if is_first:
        cols[1].text_input(f"ЗМПУ {i}", value="", disabled=True, label_visibility="collapsed", key=f"input_z_{i}")
        cols[2].text_input(f"Дист {i}", value="", disabled=True, label_visibility="collapsed", key=f"input_d_{i}")
        zmpu = "—"
        distance = "—"
    else:
        zmpu = cols[1].text_input(f"ЗМПУ {i}", value=z_val, label_visibility="collapsed", key=f"input_z_{i}", on_change=sync_inputs)
        distance = cols[2].text_input(f"Дист {i}", value=d_val, label_visibility="collapsed", key=f"input_d_{i}", on_change=sync_inputs)
        
    wind_dir = cols[3].text_input(f"ВетН {i}", value=wd_val, label_visibility="collapsed", key=f"input_wd_{i}", on_change=sync_inputs)
    wind_speed = cols[4].text_input(f"ВетС {i}", value=ws_val, label_visibility="collapsed", key=f"input_ws_{i}", on_change=sync_inputs)
    
    # Визуализация расчетных ячеек
    cols[5].markdown(f"<div class='calc-cell'>{mk_val}</div>", unsafe_allow_html=True)
    cols[6].markdown(f"<div class='calc-cell'>{time_val}</div>", unsafe_allow_html=True)

    table_rows.append({
        "point": point, "zmpu": zmpu, "distance": distance,
        "wind_dir": wind_dir, "wind_speed": wind_speed
    })

# --- ИТОГОВАЯ ПАНЕЛЬ И КНОПКА РАСЧЕТА (В один ряд) ---
st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
calc_summary_cols = st.columns([3, 1])

with calc_summary_cols[0]:
    total_dist_display = st.session_state.form_data.get("total_dist_out", 0)
    total_time_display = st.session_state.form_data.get("total_time_out", "0:00")
    st.markdown(f"<p class='summary-text'>Расстояние: <b>{total_dist_display} км</b> &nbsp;&nbsp;&nbsp; Время: <b>{total_time_display}</b></p>", unsafe_allow_html=True)

with calc_summary_cols[1]:
    # Обертка для стилизации зеленой кнопки
    st.markdown("<div class='calc-btn-container'>", unsafe_allow_html=True)
    calc_pressed = st.button("РАСЧЁТ", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

# --- НИЖНЯЯ ПАНЕЛЬ КНОПОК ДЕЙСТВИЙ (В один ряд) ---
st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
# Создаем 7 колонок для кнопок
action_cols = st.columns(7)

with action_cols[0]:
    if st.button("+ Добавить ППМ", use_container_width=True):
        sync_inputs()
        st.session_state.rows_count += 1
        st.rerun()

with action_cols[1]:
    if st.button("↑↓ Реверс", use_container_width=True):
        # Логика реверса остается прежней...
        sync_inputs()
        active_rows = []
        for idx in range(st.session_state.rows_count):
            p = st.session_state.form_data.get(f"p_{idx}", "").strip()
            if p:
                active_rows.append({
                    "p": p, "z": st.session_state.form_data.get(f"z_{idx}", ""), "d": st.session_state.form_data.get(f"d_{idx}", ""),
                    "wd": st.session_state.form_data.get(f"wd_{idx}", ""), "ws": st.session_state.form_data.get(f"ws_{idx}", "")
                })
        if len(active_rows) >= 2:
            rev_rows = list(reversed(active_rows))
            new_form_data = {"speed": st.session_state.form_data["speed"], "same_wind": st.session_state.form_data["same_wind"]}
            
            for idx, item in enumerate(rev_rows):
                new_form_data[f"p_{idx}"] = item["p"]
                if idx == 0:
                    new_form_data[f"z_{idx}"] = "—"
                    new_form_data[f"d_{idx}"] = "—"
                    new_form_data[f"wd_{idx}"] = item["wd"]
                    new_form_data[f"ws_{idx}"] = item["ws"]
                else:
                    prev_source = active_rows[len(active_rows) - idx]
                    try:
                        reversed_zmpu = str(round((float(prev_source["z"]) + 180) % 360))
                    except:
                        reversed_zmpu = ""
                    new_form_data[f"z_{idx}"] = reversed_zmpu
                    new_form_data[f"d_{idx}"] = prev_source["d"]
                    new_form_data[f"wd_{idx}"] = prev_source["wd"]
                    new_form_data[f"ws_{idx}"] = prev_source["ws"]
            
            st.session_state.rows_count = max(10, len(active_rows))
            st.session_state.form_data = new_form_data
            st.rerun()
        else:
            st.error("Недостаточно ППМ!")

with action_cols[2]:
    if st.button("≈ Убрать ветер", use_container_width=True):
        sync_inputs()
        for idx in range(st.session_state.rows_count):
            st.session_state.form_data[f"wd_{idx}"] = ""
            st.session_state.form_data[f"ws_{idx}"] = ""
            st.session_state.form_data[f"mk_{idx}"] = "—"
            st.session_state.form_data[f"time_{idx}"] = "— / —"
        st.rerun()

with action_cols[3]:
    if st.button("↻ Новый маршрут", use_container_width=True):
        st.session_state.rows_count = 10
        st.session_state.form_data = {}
        st.session_state["file_opener"] = 0 # Сброс загрузчика файлов
        st.rerun()

# 4. Кнопки импорта/экспорта в конце ряда
# Подготовка JSON для экспорта
json_data = {"speed": speed_input, "rows": []}
for idx in range(st.session_state.rows_count):
    p = st.session_state.get(f"input_p_{idx}", "")
    z = st.session_state.get(f"input_z_{idx}", "")
    d = st.session_state.get(f"input_d_{idx}", "")
    wd = st.session_state.get(f"input_wd_{idx}", "")
    ws = st.session_state.get(f"input_ws_{idx}", "")
    if p.strip():
        json_data["rows"].append({"point": p, "zmpu": z, "distance": d, "wind_dir": wd, "wind_speed": ws})
json_data_str = json.dumps(json_data, ensure_ascii=False, indent=4)

with action_cols[4]:
    st.download_button(
        label="💾 Сохранить",
        data=json_data_str,
        file_name="route.json",
        mime="application/json",
        use_container_width=True
    )

with action_cols[5]:
    uploaded_file = st.file_uploader("📂 Открыть", type=["json"], label_visibility="collapsed", key="file_opener")
    # Обработка импорта (логика прежняя, только визуализация другая)
    if uploaded_file is not None:
        try:
            file_content = json.load(uploaded_file)
            # ... (логика загрузки из предыдущей версии) ...
            # [Вставьте здесь логику загрузки из предыдущего исправленного кода app.py]
            
            # --- ЛОГИКА ЗАГРУЗКИ ---
            new_form = {"speed": file_content.get("speed", ""), "same_wind": st.session_state.form_data.get("same_wind", False)}
            r_data = file_content.get("rows", [])
            st.session_state.rows_count = max(10, len(r_data))
            for idx, r in enumerate(r_data):
                new_form[f"p_{idx}"] = r.get("point", "")
                new_form[f"z_{idx}"] = "—" if idx == 0 else r.get("zmpu", "")
                new_form[f"d_{idx}"] = "—" if idx == 0 else r.get("distance", "")
                new_form[f"wd_{idx}"] = r.get("wind_dir", "")
                new_form[f"ws_{idx}"] = r.get("wind_speed", "")
            
            st.session_state.form_data = new_form
            # Сразу маппим в input-ключи
            for idx in range(st.session_state.rows_count):
                st.session_state[f"input_p_{idx}"] = new_form.get(f"p_{idx}", "")
                st.session_state[f"input_z_{idx}"] = new_form.get(f"z_{idx}", "")
                st.session_state[f"input_d_{idx}"] = new_form.get(f"d_{idx}", "")
                st.session_state[f"input_wd_{idx}"] = new_form.get(f"wd_{idx}", "")
                st.session_state[f"input_ws_{idx}"] = new_form.get(f"ws_{idx}", "")
            st.session_state["speed_field"] = new_form["speed"]
            # ---------------------
            
            st.toast("Маршрут успешно загружен!")
            st.rerun()
        except Exception as e:
            st.error("Ошибка чтения JSON")

# --- ЛОГИКА РАСЧЕТА (При нажатии кнопки 'РАСЧЁТ') ---
# Сбор данных для PDF также происходит здесь
calculated_rows_pdf = []

if calc_pressed:
    sync_inputs()
    try:
        speed = float(speed_input)
    except:
        st.error("Проверьте скорость")
        speed = None

    if speed:
        current_rows = []
        for idx in range(st.session_state.rows_count):
            current_rows.append({
                "point": st.session_state.form_data.get(f"p_{idx}", ""),
                "zmpu": st.session_state.form_data.get(f"z_{idx}", ""),
                "distance": st.session_state.form_data.get(f"d_{idx}", ""),
                "wind_dir": st.session_state.form_data.get(f"wd_{idx}", ""),
                "wind_speed": st.session_state.form_data.get(f"ws_{idx}", "")
            })

        # ... (логика авто-распределения ветра остается прежней) ...
        # Логика авто-распределения ветра
        if same_wind_input:
            target_dir, target_speed = "", ""
            for r in current_rows:
                if r["point"].strip():
                    d, s = r["wind_dir"].strip(), r["wind_speed"].strip()
                    if d or s:
                        target_dir, target_speed = d, s
                        break
            if target_dir or target_speed:
                for r in current_rows:
                    if r["point"].strip() and not r["wind_dir"].strip() and not r["wind_speed"].strip():
                        r["wind_dir"], r["wind_speed"] = target_dir, target_speed
        else:
            c_dir, c_speed = "", ""
            for r in current_rows:
                if r["point"].strip():
                    d, s = r["wind_dir"].strip(), r["wind_speed"].strip()
                    if d or s:
                        c_dir, c_speed = d, s
                    else:
                        if c_dir or c_speed:
                            r["wind_dir"], r["wind_speed"] = c_dir, c_speed
        # ------------------------------------------------------

        # Записываем распределенный ветер обратно
        for idx, r in enumerate(current_rows):
            st.session_state.form_data[f"wd_{idx}"] = r["wind_dir"]
            st.session_state.form_data[f"ws_{idx}"] = r["wind_speed"]

        total_min, total_dist = 0, 0
        active_wind_dir, active_wind_speed = None, None
        has_error = False

        for idx, r in enumerate(current_rows):
            p_name = r["point"].strip()
            if not p_name: continue
            if idx == 0:
                try:
                    if r["wind_dir"].strip(): active_wind_dir = float(r["wind_dir"])
                    if r["wind_speed"].strip(): active_wind_speed = float(r["wind_speed"])
                except: pass
                st.session_state.form_data[f"mk_{idx}"] = "—"
                st.session_state.form_data[f"time_{idx}"] = "— / —"
                continue
            try:
                zmpu = float(r["zmpu"])
                dist = float(r["distance"])
            except: continue

            if active_wind_dir is None or active_wind_speed is None:
                st.error(f"Не заданы параметры ветра для участка до '{p_name}'")
                has_error = True; break

            mk = calculate_mk(zmpu, active_wind_dir, active_wind_speed, speed)
            f_time = calculate_time(dist, zmpu, active_wind_dir, active_wind_speed, speed)
            minutes = round(f_time * 60)
            total_min += minutes
            total_dist += dist
            
            time_str = f"{minutes//60}:{minutes%60:02d} / {total_min//60}:{total_min%60:02d}"
            
            st.session_state.form_data[f"mk_{idx}"] = str(mk)
            st.session_state.form_data[f"time_{idx}"] = time_str

        if not has_error:
            st.session_state.form_data["total_dist_out"] = round(total_dist)
            st.session_state.form_data["total_time_out"] = f"{total_min//60}:{total_min%60:02d}"
            st.rerun()

# --- КНОПКА PDF (Последняя в ряду) ---
# Сбор данных для генерации PDF
for idx in range(st.session_state.rows_count):
    p_name = st.session_state.form_data.get(f"p_{idx}", "").strip()
    if p_name:
        calculated_rows_pdf.append({
            "point": p_name,
            "distance": st.session_state.form_data.get(f"d_{idx}", "—"),
            "mk": st.session_state.form_data.get(f"mk_{idx}", ""),
            "time": st.session_state.form_data.get(f"time_{idx}", ""),
            "wd": st.session_state.form_data.get(f"wd_{idx}", ""),
            "ws": st.session_state.form_data.get(f"ws_{idx}", "")
        })

if len(calculated_rows_pdf) > 0:
    temp_pdf = os.path.join(tempfile.gettempdir(), "route_result.pdf")
    doc = SimpleDocTemplate(temp_pdf, pagesize=A4, topMargin=2*cm)
    table_data = [["PPM", "Distantia", "MK", "Time", "Wind"]]
    for idx, r in enumerate(calculated_rows_pdf):
        w_str = f"{r['wd']}° / {r['ws']} km/h" if (r['wd'] or r['ws']) else "—"
        table_data.append([r["point"], r["distance"], r["mk"], r["time"], w_str])
    table = Table(table_data, colWidths=[4.0*cm, 2.3*cm, 1.4*cm, 2.8*cm, 3.5*cm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), PDF_FONT),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    t_d = st.session_state.form_data.get("total_dist_out", 0)
    t_t = st.session_state.form_data.get("total_time_out", "0:00")
    info_data = [[f"Total Distance: {t_d} km"], [f"Total Time: {t_t}"]]
    info_tab = Table(info_data, colWidths=[14.0*cm])
    info_tab.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), PDF_FONT), ("ALIGN", (0, 0), (-1, -1), "LEFT")]))
    doc.build([table, Spacer(1, 10), info_tab])

    with open(temp_pdf, "rb") as f:
        with action_cols[6]:
            st.download_button(
                label="📄 PDF",
                data=f,
                file_name="route_result.pdf",
                mime="application/pdf",
                use_container_width=True
            )

# --- ФУТЕР ---
st.markdown("<p class='footer'>Разработчик Лёвочкин Виктор</p>", unsafe_allow_html=True)