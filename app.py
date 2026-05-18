import math
import os
import tempfile
from flask import Flask, render_template, request, jsonify, send_file

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

app = Flask(__name__)

# Имя шрифта по умолчанию
PDF_FONT = "Helvetica"

def init_pdf_font():
    global PDF_FONT
    try:
        # Пытаемся загрузить красивый шрифт с поддержкой кириллицы, если он есть рядом
        if os.path.exists("DejaVuSans.ttf"):
            pdfmetrics.registerFont(TTFont("DejaVu", "DejaVuSans.ttf"))
            PDF_FONT = "DejaVu"
    except Exception:
        PDF_FONT = "Helvetica"

init_pdf_font()

def calculate_mk(zmpu, wind_dir, wind_speed, speed):
    angle = math.radians(wind_dir + 180 - zmpu)
    correction = ((57.3 * wind_speed) / speed) * math.sin(angle)
    res = round(zmpu - correction)
    return res % 360

def calculate_time(distance, zmpu, wind_dir, wind_speed, speed):
    angle = math.radians(wind_dir + 180 - zmpu)
    ground_speed = speed + wind_speed * math.cos(angle)
    return distance / ground_speed if ground_speed > 0 else 0

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.json
    try:
        speed = float(data.get('speed', 0))
    except (ValueError, TypeError):
        return jsonify({'error': 'Проверьте параметр скорости'}), 400

    same_wind = data.get('same_wind', False)
    rows = data.get('rows', [])

    # Логика заполнения ветра
    if same_wind:
        target_dir = ""
        target_speed = ""
        for row in rows:
            if row.get('point', '').strip():
                d = row.get('wind_dir', '').strip()
                s = row.get('wind_speed', '').strip()
                if d or s:
                    target_dir = d
                    target_speed = s
                    break
        if target_dir or target_speed:
            for row in rows:
                if row.get('point', '').strip():
                    if not row.get('wind_dir', '').strip() and not row.get('wind_speed', '').strip():
                        row['wind_dir'] = target_dir
                        row['wind_speed'] = target_speed
    else:
        current_dir = ""
        current_speed = ""
        for row in rows:
            if row.get('point', '').strip():
                d = row.get('wind_dir', '').strip()
                s = row.get('wind_speed', '').strip()
                if d or s:
                    current_dir = d
                    current_speed = s
                else:
                    if current_dir or current_speed:
                        row['wind_dir'] = current_dir
                        row['wind_speed'] = current_speed

    total_min = 0
    total_dist = 0
    active_wind_dir = None
    active_wind_speed = None

    for i, row in enumerate(rows):
        if not row.get('point', '').strip():
            continue

        if i == 0:
            try:
                if row.get('wind_dir', '').strip():
                    active_wind_dir = float(row['wind_dir'])
                if row.get('wind_speed', '').strip():
                    active_wind_speed = float(row['wind_speed'])
            except ValueError:
                pass
            row['mk'] = '—'
            row['time'] = '—'
            continue

        try:
            zmpu = float(row.get('zmpu', 0))
            dist = float(row.get('distance', 0))
        except ValueError:
            continue

        if zmpu < 0 or zmpu > 359:
            return jsonify({'error': 'ЗМПУ должен быть в диапазоне 0–359'}), 400

        try:
            w_dir_str = row.get('wind_dir', '').strip()
            w_speed_str = row.get('wind_speed', '').strip()
            if w_dir_str:
                val = float(w_dir_str)
                if val < 0 or val > 359:
                    return jsonify({'error': 'Направление ветра должно быть в диапазоне 0–359 градусов'}), 400
                active_wind_dir = val
            if w_speed_str:
                active_wind_speed = float(w_speed_str)
        except ValueError:
            return jsonify({'error': f"Проверьте корректность данных ветра на ППМ '{row['point']}'"}), 400

        if active_wind_dir is None or active_wind_speed is None:
            return jsonify({'error': f"Не заданы параметры ветра для участка до ППМ '{row['point']}'"}), 400

        mk = calculate_mk(zmpu, active_wind_dir, active_wind_speed, speed)
        f_time = calculate_time(dist, zmpu, active_wind_dir, active_wind_speed, speed)
        minutes = round(f_time * 60)
        total_min += minutes
        total_dist += dist

        row['mk'] = str(mk)
        row['time'] = f"{minutes//60}:{minutes%60:02d} / {total_min//60}:{total_min%60:02d}"

    return jsonify({
        'rows': rows,
        'total_distance': round(total_dist),
        'total_time': f"{total_min//60}:{total_min%60:02d}"
    })

@app.route('/export_pdf', methods=['POST'])
def export_pdf():
    data = request.json
    rows = data.get('rows', [])
    total_distance = data.get('total_distance', 0)
    total_time = data.get('total_time', '0:00')

    temp_pdf = os.path.join(tempfile.gettempdir(), "route_result.pdf")
    doc = SimpleDocTemplate(temp_pdf, pagesize=A4, topMargin=5*cm)
    
    table_data = [["PPM", "Distantia", "MK", "Time", "Wind"]]
    
    for i, row in enumerate(rows):
        p = row.get('point', '').strip()
        if not p: 
            continue
        
        if i > 0:
            d = row.get('distance', '')
            m = row.get('mk', '')
            t = row.get('time', '')
            wd = row.get('wind_dir', '').strip()
            ws = row.get('wind_speed', '').strip()
            w = f"{wd} deg / {ws} km/h" if (wd or ws) else "—"
        else:
            wd = row.get('wind_dir', '').strip()
            ws = row.get('wind_speed', '').strip()
            w = f"{wd} deg / {ws} km/h" if (wd or ws) else "—"
            d, m, t = "—", "—", "—"
            
        table_data.append([p, d, m, t, w])

    table = Table(table_data, colWidths=[4.0*cm, 2.3*cm, 1.4*cm, 2.8*cm, 3.5*cm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), PDF_FONT),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    
    info = [
        [f"Total Distance: {total_distance} km"], 
        [f"Total Time: {total_time}"]
    ]
    info_tab = Table(info, colWidths=[14.0*cm])
    info_tab.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), PDF_FONT), ("ALIGN", (0, 0), (-1, -1), "LEFT")]))

    doc.build([table, Spacer(1, 10), info_tab])
    return send_file(temp_pdf, as_attachment=True, download_name="route_result.pdf")

if __name__ == '__main__':
    app.run(debug=False)
