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

# Настройка страницы Streamlit (должна быть самой первой командой)
st.set_page_config(page_title="Расчёт маршрута", layout="wide")

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
    """ Сохраняет текущие введенные пользователем данные в сессию перед перезагрузкой интерфейса """
    st.session_state.form_data["speed"] = "" if "speed_field" not in st.session_state else st.session_state.speed_field
    st.session_state.form_data["same_wind"] = False if "same_wind_field" not in st.session_state else st.session_state.same_wind_field
    for idx in range(st.session_state.rows_count):
        st.session_state.form_data[f"p_{idx}"] = st.session_state.get(f"input_p_{idx}", "")
        st.session_state.form_data[f"z_{idx}"] = st.session_state.get(f"input_z_{idx}", "")
        st.session_state.form_data[f"d_{idx}"] = st.session_state.get(f"input_d_{idx}", "")
        st.session_state.form_data[f"wd_{idx}"] = st.session_state.get(f"input_wd_{idx}", "")
        st.session_state.form_data[f"ws_{idx}"] = st.session_state.get(f"input_ws_{idx}", "")

# --- ПАНЕЛЬ РАЗРАБОТЧИКА И ЗАГОЛОВОК ---
col_title, col_dev = st.columns([3, 1])
with col_title:
    st.title("Расчёт маршрута")
with col_dev:
    st.markdown("<p style='text-align: right; font-style: italic; color: gray; margin-top: 25px;'>Разработчик Лёвочкин Виктор</p>", unsafe_allow_html=True)

# --- ВЕРХНЯЯ ПАНЕЛЬ НАСТРОЕК ---
col_speed, col_cb = st.columns([1, 2])
with col_speed:
    default_speed = st.session_state.form_data.get("speed", "")
    speed_input = st.text_input("Скорость (км/ч)", value=default_speed, key="speed_field")
with col_cb:
    st.markdown("<br>", unsafe_allow_html=True)
    default_same_wind = st.session_state.form_data.get("same_wind", False)
    same_wind_input = st.checkbox("Ветер по всему маршруту одинаковый", value=default_same_wind, key="same_wind_field")

# --- ТАБЛИЦА ВВОДА ДАННЫХ ---
st.markdown("### Таблица маршрута")

cols = st.columns([3, 1.5, 1.5, 1.5, 1.5, 1.5, 2])
cols[0].markdown("**ППМ**")
cols[1].markdown("**ЗМПУ (°)**")
cols[2].markdown("**Расстояние (км)**")
cols[3].markdown("**Ветер напр.(°)**")
cols[4].markdown("**Ветер скор.(км/ч)**")
cols[5].markdown("**МК (°)**")
cols[6].markdown("**Время (Участок / Общее)**")

table_rows = []

for i in range(st.session_state.rows_count):
    cols = st.columns([3, 1.5, 1.5, 1.5, 1.5, 1.5, 2])
    
    p_val = st.session_state.form_data.get(f"p_{i}", "")
    z_val = st.session_state.form_data.get(f"z_{i}", "")
    d_val = st.session_state.form_data.get(f"d_{i}", "")
    wd_val = st.session_state.form_data.get(f"wd_{i}", "")
    ws_val = st.session_state.form_data.get(f"ws_{i}", "")
    
    # Достаем сохраненные расчетные значения из сессии, чтобы они не исчезали
    mk_val = st.session_state.form_data.get(f"mk_{i}", "—" if i == 0 else "")
    time_val = st.session_state.form_data.get(f"time_{i}", "—" if i == 0 else "")
    
    is_first = (i == 0)
    
    point = cols[0].text_input(f"ППМ {i}", value=p_val, label_visibility="collapsed", key=f"input_p_{i}")
    
    if is_first:
        cols[1].text_input(f"ЗМПУ {i}", value="—", disabled=True, label_visibility="collapsed", key=f"input_z_{i}")
        cols[2].text_input(f"Дист {i}", value="—", disabled=True, label_visibility="collapsed", key=f"input_d_{i}")
        zmpu = "—"
        distance = "—"
    else:
        zmpu = cols[1].text_input(f"ЗМПУ {i}", value=z_val, label_visibility="collapsed", key=f"input_z_{i}")
        distance = cols[2].text_input(f"Дист {i}", value=d_val, label_visibility="collapsed", key=f"input_d_{i}")
        
    wind_dir = cols[3].text_input(f"ВетН {i}", value=wd_val, label_visibility="collapsed", key=f"input_wd_{i}")
    wind_speed = cols[4].text_input(f"ВетС {i}", value=ws_val, label_visibility="collapsed", key=f"input_ws_{i}")
    
    # Выводим расчетные значения (они стабильны, так как привязаны к тексту/сессии)
    cols[5].markdown(f"<div style='padding: 8px 0; text-align: center;'>{mk_val}</div>", unsafe_allow_html=True)
    cols[6].markdown(f"<div style='padding: 8px 0; text-align: center;'>{time_val}</div>", unsafe_allow_html=True)

    table_rows.append({
        "point": point, "zmpu": zmpu, "distance": distance,
        "wind_dir": wind_dir, "wind_speed": wind_speed
    })

# --- КНОПКИ УПРАВЛЕНИЯ ТАБЛИЦЕЙ ---
st.markdown("---")
btn_cols1 = st.columns(4)

if btn_cols1[0].button("Добавить ППМ", use_container_width=True):
    sync_inputs()
    st.session_state.rows_count += 1
    st.rerun()

if btn_cols1[1].button("Реверс", use_container_width=True):
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
        st.error("Недостаточно заполненных ППМ для реверса!")

if btn_cols1[2].button("Убрать ветер", use_container_width=True):
    sync_inputs()
    for idx in range(st.session_state.rows_count):
        st.session_state.form_data[f"wd_{idx}"] = ""
        st.session_state.form_data[f"ws_{idx}"] = ""
        # Сбрасываем старые расчеты, так как ветер изменился
        st.session_state.form_data[f"mk_{idx}"] = "—" if idx == 0 else ""
        st.session_state.form_data[f"time_{idx}"] = "—" if idx == 0 else ""
    st.rerun()

if btn_cols1[3].button("Новый маршрут", use_container_width=True):
    st.session_state.rows_count = 10
    st.session_state.form_data = {}
    st.rerun()

# --- КНОПКИ ИМПОРТА/ЭКСПОРТА ---
btn_cols2 = st.columns(3)

# 1. Экспорт JSON
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

btn_cols2[0].download_button(
    label="Сохранить (JSON)",
    data=json_data_str,
    file_name="route.json",
    mime="application/json",
    use_container_width=True
)

# 2. Импорт JSON (Исправленная стабильная логика)
with btn_cols2[1]:
    uploaded_file = st.file_uploader("Открыть маршрут", type=["json"], label_visibility="collapsed", key="file_opener")
    if uploaded_file is not None:
        try:
            file_content = json.load(uploaded_file)
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
            st.toast("Маршрут успешно загружен!")
            st.rerun()
        except Exception as e:
            st.error("Ошибка чтения файла JSON")

# --- КНОПКА РАСЧЁТ И ВЫЧИСЛЕНИЯ ---
st.markdown("<br>", unsafe_allow_html=True)
calc_pressed = st.button("РАСЧЁТ", type="primary", use_container_width=True)

calculated_rows_pdf = []
total_distance_out = 0
total_time_out = "0:00"

if calc_pressed:
    sync_inputs()  # Сначала жестко фиксируем всё, что ввел пользователь
    try:
        speed = float(speed_input)
    except:
        st.error("Проверьте параметр скорости")
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

        # Переносим распределенный ветер обратно в сессию
        for idx, r in enumerate(current_rows):
            st.session_state.form_data[f"wd_{idx}"] = r["wind_dir"]
            st.session_state.form_data[f"ws_{idx}"] = r["wind_speed"]

        total_min, total_dist = 0, 0
        active_wind_dir, active_wind_speed = None, None
        has_error = False

        for idx, r in enumerate(current_rows):
            p_name = r["point"].strip()
            if not p_name:
                continue

            if idx == 0:
                try:
                    if r["wind_dir"].strip(): active_wind_dir = float(r["wind_dir"])
                    if r["wind_speed"].strip(): active_wind_speed = float(r["wind_speed"])
                except: pass
                st.session_state.form_data[f"mk_{idx}"] = "—"
                st.session_state.form_data[f"time_{idx}"] = "—"
                continue

            try:
                zmpu = float(r["zmpu"])
                dist = float(r["distance"])
            except:
                continue

            if zmpu < 0 or zmpu > 359:
                st.error("ЗМПУ должен быть в диапазоне 0–359")
                has_error = True; break

            try:
                if r["wind_dir"].strip():
                    val = float(r["wind_dir"])
                    if val < 0 or val > 359:
                        st.error("Направление ветра должно быть 0–359°")
                        has_error = True; break
                    active_wind_dir = val
                if r["wind_speed"].strip():
                    active_wind_speed = float(r["wind_speed"])
            except:
                st.error(f"Проверьте корректность данных ветра на ППМ '{p_name}'")
                has_error = True; break

            if active_wind_dir is None or active_wind_speed is None:
                st.error(f"Не заданы параметры ветра для участка до ППМ '{p_name}'")
                has_error = True; break

            mk = calculate_mk(zmpu, active_wind_dir, active_wind_speed, speed)
            f_time = calculate_time(dist, zmpu, active_wind_dir, active_wind_speed, speed)
            minutes = round(f_time * 60)
            total_min += minutes
            total_dist += dist

            time_str = f"{minutes//60}:{minutes%60:02d} / {total_min//60}:{total_min%60:02d}"
            
            # Сохраняем расчеты в сессию, чтобы они "застыли" на экране
            st.session_state.form_data[f"mk_{idx}"] = str(mk)
            st.session_state.form_data[f"time_{idx}"] = time_str

        if not has_error:
            st.session_state.form_data["total_dist_out"] = round(total_dist)
            st.session_state.form_data["total_time_out"] = f"{total_min//60}:{total_min%60:02d}"
            st.rerun()  # Перезагружаем страницу один раз, чтобы отобразить результаты намертво

# --- ВЫВОД ИТОГОВЫХ ДАННЫХ И СКАЧИВАНИЕ PDF ---
if "total_dist_out" in st.session_state.form_data and st.session_state.form_data["total_dist_out"] > 0:
    total_distance_out = st.session_state.form_data["total_dist_out"]
    total_time_out = st.session_state.form_data["total_time_out"]
    
    st.info(f"**Общее расстояние:** {total_distance_out} км  |  **Общее время:** {total_time_out}")

    # Сбор данных для генерации PDF на лету
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
        
        info_data = [
            [f"Total Distance: {total_distance_out} km"], 
            [f"Total Time: {total_time_out}"]
        ]
        info_tab = Table(info_data, colWidths=[14.0*cm])
        info_tab.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), PDF_FONT), ("ALIGN", (0, 0), (-1, -1), "LEFT")]))

        doc.build([table, Spacer(1, 10), info_tab])

        with open(temp_pdf, "rb") as f:
            btn_cols2[2].download_button(
                label="Скачать PDF",
                data=f,
                file_name="route_result.pdf",
                mime="application/pdf",
                use_container_width=True
            )