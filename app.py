import math
import json
import os
import tempfile
import streamlit as nn  # Используем нестандартное имя импорта во избежание конфликтов

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

# Настройка страницы (должна быть первой командой Streamlit)
nn.set_page_config(page_title="Расчёт маршрута", layout="wide")

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
if "rows_count" not in nn.session_state:
    nn.session_state.rows_count = 10

if "form_data" not in nn.session_state:
    nn.session_state.form_data = {}

# --- ПАНЕЛЬ РАЗРАБОТЧИКА И ЗАГОЛОВОК ---
col_title, col_dev = nn.columns([3, 1])
with col_title:
    nn.title("Расчёт маршрута")
with col_dev:
    nn.markdown("<p style='text-align: right; font-style: italic; color: gray;'>Разработчик Лёвочкин Виктор</p>", unsafe_allowed_html=True)

# --- ВЕРХНЯЯ ПАНЕЛЬ НАСТРОЕК ---
col_speed, col_cb = nn.columns([1, 2])
with col_speed:
    # Загружаем сохраненное значение скорости, если оно есть
    default_speed = nn.session_state.form_data.get("speed", "")
    speed_input = nn.text_input("Скорость (км/ч)", value=default_speed, key="speed_field")
with col_cb:
    nn.markdown("<br>", unsafe_allowed_html=True)  # Выравнивание по высоте
    default_same_wind = nn.session_state.form_data.get("same_wind", False)
    same_wind_input = nn.checkbox("Ветер по всему маршруту одинаковый", value=default_same_wind, key="same_wind_field")

# --- ТАБЛИЦА ВВОДА ДАННЫХ ---
nn.markdown("### Таблица маршрута")

# Заголовки таблицы
cols = nn.columns([3, 1.5, 1.5, 1.5, 1.5, 1.5, 2])
cols[0].markdown("**ППМ**")
cols[1].markdown("**ЗМПУ (°)**")
cols[2].markdown("**Расстояние (км)**")
cols[3].markdown("**Ветер напр.(°)**")
cols[4].markdown("**Ветер скор.(км/ч)**")
cols[5].markdown("**МК (°)**")
cols[6].markdown("**Время (Участок / Общее)**")

table_rows = []

for i in range(nn.session_state.rows_count):
    cols = nn.columns([3, 1.5, 1.5, 1.5, 1.5, 1.5, 2])
    
    # Ключи для сохранения состояния каждого инпута
    p_key = f"p_{i}"
    z_key = f"z_{i}"
    d_key = f"d_{i}"
    wd_key = f"wd_{i}"
    ws_key = f"ws_{i}"
    
    # Восстановление значений из form_data (например, после загрузки файла или реверса)
    p_val = nn.session_state.form_data.get(p_key, "")
    z_val = nn.session_state.form_data.get(z_key, "")
    d_val = nn.session_state.form_data.get(d_key, "")
    wd_val = nn.session_state.form_data.get(wd_key, "")
    ws_val = nn.session_state.form_data.get(ws_key, "")
    
    # Первая строка — отправная точка (ЗМПУ и Расстояние заблокированы)
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
    
    # Ячейки для результатов вывода (будут заполнены при расчете)
    mk_cell = cols[5].empty()
    time_cell = cols[6].empty()
    
    if is_first:
        mk_cell.markdown("<div style='padding: 8px 0; text-align: center;'>—</div>", unsafe_allowed_html=True)
        time_cell.markdown("<div style='padding: 8px 0; text-align: center;'>—</div>", unsafe_allowed_html=True)

    table_rows.append({
        "point": point, "zmpu": zmpu, "distance": distance,
        "wind_dir": wind_dir, "wind_speed": wind_speed,
        "mk_cell": mk_cell, "time_cell": time_cell
    })

# --- КНОПКИ УПРАВЛЕНИЯ ТАБЛИЦЕЙ ---
nn.markdown("---")
btn_cols1 = nn.columns(4)

if btn_cols1[0].button("Добавить ППМ", use_container_width=True):
    nn.session_state.rows_count += 1
    nn.rerun()

# Функция для синхронизации текущего ввода в session_state перед операциями
def sync_inputs():
    nn.session_state.form_data["speed"] = nn.clear_cache_by_key if "speed_field" not in nn.session_state else nn.session_state.speed_field
    nn.session_state.form_data["same_wind"] = False if "same_wind_field" not in nn.session_state else nn.session_state.same_wind_field
    for idx in range(nn.session_state.rows_count):
        nn.session_state.form_data[f"p_{idx}"] = nn.session_state.get(f"input_p_{idx}", "")
        nn.session_state.form_data[f"z_{idx}"] = nn.session_state.get(f"input_z_{idx}", "")
        nn.session_state.form_data[f"d_{idx}"] = nn.session_state.get(f"input_d_{idx}", "")
        nn.session_state.form_data[f"wd_{idx}"] = nn.session_state.get(f"input_wd_{idx}", "")
        nn.session_state.form_data[f"ws_{idx}"] = nn.session_state.get(f"input_ws_{idx}", "")

if btn_cols1[1].button("Реверс", use_container_width=True):
    sync_inputs()
    active_rows = []
    for idx in range(nn.session_state.rows_count):
        p = nn.session_state.form_data.get(f"p_{idx}", "").strip()
        if p:
            active_rows.append({
                "p": p, "z": nn.session_state.form_data.get(f"z_{idx}", ""), "d": nn.session_state.form_data.get(f"d_{idx}", ""),
                "wd": nn.session_state.form_data.get(f"wd_{idx}", ""), "ws": nn.session_state.form_data.get(f"ws_{idx}", "")
            })
    if len(active_rows) >= 2:
        rev_rows = list(reversed(active_rows))
        new_form_data = {"speed": nn.session_state.form_data["speed"], "same_wind": nn.session_state.form_data["same_wind"]}
        
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
        
        nn.session_state.rows_count = max(10, len(active_rows))
        nn.session_state.form_data = new_form_data
        nn.rerun()
    else:
        nn.error("Недостаточно заполненных ППМ для реверса!")

if btn_cols1[2].button("Убрать ветер", use_container_width=True):
    sync_inputs()
    for idx in range(nn.session_state.rows_count):
        nn.session_state.form_data[f"wd_{idx}"] = ""
        nn.session_state.form_data[f"ws_{idx}"] = ""
    nn.rerun()

if btn_cols1[3].button("Новый маршрут", use_container_width=True):
    nn.session_state.rows_count = 10
    nn.session_state.form_data = {}
    nn.rerun()

# --- КНОПКИ ИМПОРТА/ЭКСПОРТА ---
btn_cols2 = nn.columns(3)

# Сохранение в JSON
json_data = {"speed": speed_input, "rows": []}
for idx in range(nn.session_state.rows_count):
    p = nn.session_state.get(f"input_p_{idx}", "")
    z = nn.session_state.get(f"input_z_{idx}", "")
    d = nn.session_state.get(f"input_d_{idx}", "")
    if p.strip():
        json_data["rows"].append({"point": p, "zmpu": z, "distance": d})

btn_cols2[0].download_button(
    label="Сохранить (JSON)",
    data=json_data_str := json.dumps(json_data, ensure_ascii=False, indent=4),
    file_name="route.json",
    mime="application/json",
    use_container_width=True
)

# Загрузка из JSON
uploaded_file = btn_cols2[1].file_uploader("Открыть маршрут", type=["json"], label_visibility="collapsed")
if uploaded_file is not None:
    try:
        file_content = json.load(uploaded_file)
        new_form = {"speed": file_content.get("speed", ""), "same_wind": same_wind_input}
        r_data = file_content.get("rows", [])
        nn.session_state.rows_count = max(10, len(r_data))
        for idx, r in enumerate(r_data):
            new_form[f"p_{idx}"] = r.get("point", "")
            new_form[f"z_{idx}"] = "—" if idx == 0 else r.get("zmpu", "")
            new_form[f"d_{idx}"] = "—" if idx == 0 else r.get("distance", "")
        nn.session_state.form_data = new_form
        nn.toast("Маршрут успешно загружен!")
        # Сбрасываем загрузчик, чтобы файл можно было загрузить повторно при необходимости
        uploaded_file = None 
    except Exception as e:
        nn.error("Ошибка чтения JSON файла")

# --- КНОПКА РАСЧЁТ И ЛОГИКА ---
nn.markdown("<br>", unsafe_allowed_html=True)
calc_pressed = nn.button("РАСЧЁТ", type="primary", use_container_width=True)

calculated_rows_pdf = []
total_distance_out = 0
total_time_out = "0:00"

if calc_pressed or "calculated_results" in nn.session_state:
    try:
        speed = float(speed_input)
    except:
        nn.error("Проверьте параметр скорости")
        speed = None

    if speed:
        # 1. Сбор данных из полей ввода
        current_rows = []
        for idx in range(nn.session_state.rows_count):
            current_rows.append({
                "point": nn.session_state.get(f"input_p_{idx}", ""),
                "zmpu": nn.session_state.get(f"input_z_{idx}", ""),
                "distance": nn.session_state.get(f"input_d_{idx}", ""),
                "wind_dir": nn.session_state.get(f"input_wd_{idx}", ""),
                "wind_speed": nn.session_state.get(f"input_ws_{idx}", "")
            })

        # 2. Реализация вашей логики заполнения ветра (Чекбокс)
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

        # Отображение обновленного ветра обратно в инпуты визуально
        for idx, r in enumerate(current_rows):
            nn.session_state.form_data[f"wd_{idx}"] = r["wind_dir"]
            nn.session_state.form_data[f"ws_{idx}"] = r["wind_speed"]

        # 3. Расчет маршрута
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
                calculated_rows_pdf.append({"point": p_name, "distance": "—", "mk": "—", "time": "—", "wd": r["wind_dir"], "ws": r["wind_speed"]})
                continue

            try:
                zmpu = float(r["zmpu"])
                dist = float(r["distance"])
            except:
                continue

            if zmpu < 0 or zmpu > 359:
                nn.error("ЗМПУ должен быть в диапазоне 0–359")
                has_error = True; break

            try:
                if r["wind_dir"].strip():
                    val = float(r["wind_dir"])
                    if val < 0 or val > 359:
                        nn.error("Направление ветра должно быть 0–359°")
                        has_error = True; break
                    active_wind_dir = val
                if r["wind_speed"].strip():
                    active_wind_speed = float(r["wind_speed"])
            except:
                nn.error(f"Проверьте корректность данных ветра на ППМ '{p_name}'")
                has_error = True; break

            if active_wind_dir is None or active_wind_speed is None:
                nn.error(f"Не заданы параметры ветра для участка до ППМ '{p_name}'")
                has_error = True; break

            mk = calculate_mk(zmpu, active_wind_dir, active_wind_speed, speed)
            f_time = calculate_time(dist, zmpu, active_wind_dir, active_wind_speed, speed)
            minutes = round(f_time * 60)
            total_min += minutes
            total_dist += dist

            time_str = f"{minutes//60}:{minutes%60:02d} / {total_min//60}:{total_min%60:02d}"
            
            # Вывод на экран в пустые контейнеры (empty)
            table_rows[idx]["mk_cell"].markdown(f"<div style='padding: 8px 0; text-align: center;'>{mk}</div>", unsafe_allowed_html=True)
            table_rows[idx]["time_cell"].markdown(f"<div style='padding: 8px 0; text-align: center;'>{time_str}</div>", unsafe_allowed_html=True)

            calculated_rows_pdf.append({
                "point": p_name, "distance": str(dist), "mk": str(mk), "time": time_str,
                "wd": str(active_wind_dir), "ws": str(active_wind_speed)
            })

        if not has_error:
            total_distance_out = round(total_dist)
            total_time_out = f"{total_min//60}:{total_min%60:02d}"
            
            summary_text = f"**Общее расстояние:** {total_distance_out} км\n\n**Общее время:** {total_time_out}"
            nn.info(summary_text)

# --- ГЕНЕРАЦИЯ И СКАЧИВАНИЕ PDF ---
if len(calculated_rows_pdf) > 0:
    temp_pdf = os.path.join(tempfile.gettempdir(), "route_result.pdf")
    doc = SimpleDocTemplate(temp_pdf, pagesize=A4, topMargin=5*cm)
    
    # Английские/латинские заголовки для избежания проблем, если нет шрифта DejaVuSans
    table_data = [["PPM", "Distantia", "MK", "Time", "Wind"]]
    
    for idx, r in enumerate(calculated_rows_pdf):
        if idx > 0:
            w_str = f"{r['wd']}° / {r['ws']} km/h" if (r['wd'] or r['ws']) else "—"
            table_data.append([r["point"], r["distance"], r["mk"], r["time"], w_str])
        else:
            w_str = f"{r['wd']}° / {r['ws']} km/h" if (r['wd'] or r['ws']) else "—"
            table_data.append([r["point"], "—", "—", "—", w_str])

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