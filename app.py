import os
import numpy as np
from PIL import Image
import io
import base64
from flask import Flask, render_template, request, session, flash, redirect, url_for
from werkzeug.utils import secure_filename
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import timedelta
import random

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

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
    else:
        if num1 < num2:
            num1, num2 = num2, num1
        result = num1 - num2
    
    question = f"{num1} {operation} {num2} = ?"
    
    session['captcha_result'] = result
    session['captcha_question'] = question
    
    return question

def apply_modulation(image_array, axis, func_type, period):
    h, w, _ = image_array.shape
    result = np.zeros_like(image_array, dtype=np.float32)
    
    image_norm = image_array.astype(np.float32) / 255.0
    
    for y in range(h):
        for x in range(w):
            if axis == 'x':
                coord = x
            else:
                coord = y
            
            radians = (coord / period) * 2 * np.pi
            
            if func_type == 'sin':
                factor = (np.sin(radians) + 1) / 2
            else:
                factor = (np.cos(radians) + 1) / 2
            
            result[y, x] = image_norm[y, x] * factor
    
    return (result * 255).astype(np.uint8)

def create_histogram(original, modulated):
    orig_gray = np.dot(original[...,:3], [0.299, 0.587, 0.114])
    mod_gray = np.dot(modulated[...,:3], [0.299, 0.587, 0.114])
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
    
    ax1.hist(orig_gray.ravel(), bins=256, range=(0, 255), 
             color='blue', alpha=0.7, density=True)
    ax1.set_title('Распределение яркости (исходное)')
    ax1.set_xlabel('Яркость')
    ax1.set_ylabel('Частота')
    ax1.grid(True, alpha=0.3)
    
    ax2.hist(mod_gray.ravel(), bins=256, range=(0, 255), 
             color='red', alpha=0.7, density=True)
    ax2.set_title('Распределение яркости (новое)')
    ax2.set_xlabel('Яркость')
    ax2.set_ylabel('Частота')
    ax2.grid(True, alpha=0.3)
    
    img_bytes = io.BytesIO()
    plt.tight_layout()
    plt.savefig(img_bytes, format='png', dpi=100)
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
    user_answer = request.form.get('captcha', '')
    try:
        user_answer = int(user_answer)
    except ValueError:
        flash('Неверный ответ капчи', 'error')
        return redirect(url_for('index'))
    
    if user_answer != session.get('captcha_result'):
        flash('Неверный ответ капчи', 'error')
        return redirect(url_for('index'))
    
    if 'image' not in request.files:
        flash('Файл не загружен', 'error')
        return redirect(url_for('index'))
    
    file = request.files['image']
    
    if file.filename == '':
        flash('Файл не выбран', 'error')
        return redirect(url_for('index'))
    
    if not allowed_file(file.filename):
        flash('Неподдерживаемый формат файла', 'error')
        return redirect(url_for('index'))
    
    try:
        axis = request.form.get('axis', 'x')
        func_type = request.form.get('function', 'sin')
        period = int(request.form.get('period', 80))
        
        if period < 2:
            flash('Период должен быть не меньше 2 пикселей', 'error')
            return redirect(url_for('index'))
        
        img = Image.open(file).convert('RGB')
        
        original_path = os.path.join(app.config['UPLOAD_FOLDER'], 'original.png')
        img.save(original_path)
        
        img_array = np.array(img)
        modulated_array = apply_modulation(img_array, axis, func_type, period)
        
        modulated_img = Image.fromarray(modulated_array)
        modulated_path = os.path.join(app.config['UPLOAD_FOLDER'], 'modulated.png')
        modulated_img.save(modulated_path)
        
        histogram = create_histogram(img_array, modulated_array)
        
        return render_template('result.html', 
                             original='static/uploads/original.png',
                             modulated='static/uploads/modulated.png',
                             histogram=histogram,
                             axis=axis,
                             func=func_type,
                             period=period)
    
    except Exception as e:
        flash(f'Ошибка обработки: {str(e)}', 'error')
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
