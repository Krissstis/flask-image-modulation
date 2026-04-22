import os
import io
import base64
import random
from datetime import datetime

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from flask import Flask, render_template, request, session, flash, redirect, url_for
from werkzeug.utils import secure_filename
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Инициализация
app = Flask(__name__)
app.secret_key = 'super-secret-key-2026'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_captcha():
    num1 = random.randint(1, 10)
    num2 = random.randint(1, 10)
    operation = random.choice(['+', '-'])
    if operation == '+':
        result = num1 + num2
        question = f"{num1} + {num2} = ?"
    else:
        if num1 < num2:
            num1, num2 = num2, num1
        result = num1 - num2
        question = f"{num1} - {num2} = ?"
    session['captcha_result'] = result
    return question

def apply_modulation(image_array, axis, func_type, period):
    """Применяет sin/cos модуляцию"""
    h, w, _ = image_array.shape
    result = np.zeros_like(image_array, dtype=np.float32)
    image_norm = image_array.astype(np.float32) / 255.0

    for y in range(h):
        for x in range(w):
            coord = x if axis == 'x' else y
            radians = (coord / period) * 2 * np.pi
            if func_type == 'sin':
                factor = (np.sin(radians) + 1) / 2
            else:
                factor = (np.cos(radians) + 1) / 2
            result[y, x] = image_norm[y, x] * factor

    return (result * 255).astype(np.uint8)

def add_timestamp_to_image(image_array):
    print("=== ФУНКЦИЯ ВЫЗВАНА ===")

    pil_img = Image.fromarray(image_array)
    draw = ImageDraw.Draw(pil_img)

    # Текущее время
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = f"Created: {timestamp}"
    print(f"=== ТЕКСТ ДЛЯ ДОБАВЛЕНИЯ: {text} ===")

    # Шрифт
    try:
        font = ImageFont.truetype("arial.ttf", 160)
        print("=== ШРИФТ Arial ЗАГРУЖЕН ===")
    except:
        font = ImageFont.load_default()
        print("=== ШРИФТ ПО УМОЛЧАНИЮ ===")

    # Размер текста
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    print(f"=== РАЗМЕР ТЕКСТА: {text_width} x {text_height} ===")

    # Позиция
    width, height = pil_img.size
    x = width - text_width - 20
    y = height - text_height - 20
    print(f"=== ПОЗИЦИЯ: x={x}, y={y}, картинка {width}x{height} ===")

    # Рисуем
    draw.rectangle([x-5, y-5, x+text_width+5, y+text_height+5], fill=(0, 0, 0))
    draw.text((x, y), text, fill=(255, 255, 255), font=font)

    # Сохраняем для проверки
    pil_img.save('debug_check.png')
    print("=== СОХРАНЕНО debug_check.png ===")

    return np.array(pil_img)

def create_histogram(original, modulated):
    """Гистограммы яркости"""
    orig_gray = np.dot(original[..., :3], [0.299, 0.587, 0.114])
    mod_gray = np.dot(modulated[..., :3], [0.299, 0.587, 0.114])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
    ax1.hist(orig_gray.ravel(), bins=256, range=(0,255), color='blue', alpha=0.7, density=True)
    ax1.set_title('Исходное')
    ax1.set_xlabel('Яркость')
    ax2.hist(mod_gray.ravel(), bins=256, range=(0,255), color='red', alpha=0.7, density=True)
    ax2.set_title('После модуляции')
    ax2.set_xlabel('Яркость')

    img_bytes = io.BytesIO()
    plt.tight_layout()
    plt.savefig(img_bytes, format='png')
    img_bytes.seek(0)
    plot_url = base64.b64encode(img_bytes.getvalue()).decode()
    plt.close()
    return plot_url

@app.route('/')
def index():
    question = generate_captcha()
    return render_template('index.html', captcha_question=question)

@app.route('/process', methods=['POST'])
def process():
    # 1. Проверка капчи
    try:
        user_answer = int(request.form.get('captcha', ''))
    except:
        flash('Неверный ответ капчи', 'error')
        return redirect(url_for('index'))

    if user_answer != session.get('captcha_result'):
        flash('Неверный ответ капчи', 'error')
        return redirect(url_for('index'))

    # 2. Проверка файла
    if 'image' not in request.files:
        flash('Файл не загружен', 'error')
        return redirect(url_for('index'))

    file = request.files['image']
    if file.filename == '':
        flash('Файл не выбран', 'error')
        return redirect(url_for('index'))

    if not allowed_file(file.filename):
        flash('Неподдерживаемый формат', 'error')
        return redirect(url_for('index'))

    try:
        # 3. Получение параметров
        axis = request.form.get('axis', 'x')
        func_type = request.form.get('function', 'sin')
        period = int(request.form.get('period', 80))
        # НОВИНКА: читаем чекбокс
        add_time = request.form.get('add_timestamp') == 'on'
        print(f"=== ЧЕКБОКС ОТМЕЧЕН: {add_time} ===")

        if period < 2:
            flash('Период >= 2', 'error')
            return redirect(url_for('index'))

        # 4. Загрузка и модуляция
        img = Image.open(file).convert('RGB')
        img_array = np.array(img)
        modulated_array = apply_modulation(img_array, axis, func_type, period)

        # 5. НОВИНКА: если чекбокс отмечен — добавляем время
        if add_time:
            modulated_array = add_timestamp_to_image(modulated_array)

        # 6. Сохраняем
        original_path = os.path.join(app.config['UPLOAD_FOLDER'], 'original.png')
        modulated_path = os.path.join(app.config['UPLOAD_FOLDER'], 'modulated.png')
        Image.fromarray(img_array).save(original_path)
        Image.fromarray(modulated_array).save(modulated_path)

        # 7. Гистограмма
        histogram = create_histogram(img_array, modulated_array)

        return render_template('result.html',
                             original='static/uploads/original.png',
                             modulated='static/uploads/modulated.png',
                             histogram=histogram,
                             axis=axis,
                             func=func_type,
                             period=period,
                             timestamp_added=add_time)  # передаем флаг в шаблон
    except Exception as e:
        flash(f'Ошибка: {str(e)}', 'error')
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
