from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import datetime, timedelta
import calendar

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta'  # Substitua por uma chave segura

DATABASE = 'petshop.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # Tabela de agendamentos
    conn.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            service_type TEXT NOT NULL,
            appointment_datetime TEXT NOT NULL
        )
    ''')
    # Tabela de produtos
    conn.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode TEXT UNIQUE,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL
        )
    ''')
    # Tabela de vendas
    conn.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_date TEXT NOT NULL,
            total REAL NOT NULL
        )
    ''')
    # Tabela de itens de venda
    conn.execute('''
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER,
            product_id INTEGER,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY(sale_id) REFERENCES sales(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Injetar a data atual em todos os templates
@app.context_processor
def inject_now():
    return {'now': datetime.now()}

# --- Calendário ---
@app.route('/calendar/<int:year>/<int:month>')
def calendar_view(year, month):
    first_weekday, num_days = calendar.monthrange(year, month)
    # Ajusta para que a semana comece no domingo (calendar.monthrange retorna 0 para segunda)
    blank_count = (first_weekday + 1) % 7

    # Cria lista com todos os dias do mês
    days = []
    for day in range(1, num_days + 1):
        date_str = f"{year}-{month:02d}-{day:02d}"
        conn = get_db_connection()
        appointments = conn.execute(
            "SELECT * FROM appointments WHERE appointment_datetime LIKE ?",
            (date_str + "T%",)
        ).fetchall()
        conn.close()
        appointments = sorted(appointments, key=lambda a: a['appointment_datetime'])
        days.append({"date": date_str, "appointments": appointments})

    # Agrupa os dias em semanas (cada semana: lista com 7 elementos)
    weeks = []
    week = []
    for i in range(blank_count):
        week.append(None)
    for day in days:
        week.append(day)
        if len(week) == 7:
            weeks.append(week)
            week = []
    if week:
        while len(week) < 7:
            week.append(None)
        weeks.append(week)

    # Calcula mês anterior e próximo para navegação
    current = datetime(year, month, 1)
    prev_date = current.replace(day=1) - timedelta(days=1)
    next_date = current.replace(day=28) + timedelta(days=4)
    return render_template('calendar.html',
                           weeks=weeks,
                           month=month,  # Variável passada para o template
                           month_name=calendar.month_name[month],
                           year=year,
                           prev_year=prev_date.year,
                           prev_month=prev_date.month,
                           next_year=next_date.year,
                           next_month=next_date.month)

# Rota detalhada para visualizar os agendamentos de um dia específico
@app.route('/day/<int:year>/<int:month>/<int:day>')
def day_view(year, month, day):
    date_str = f"{year}-{month:02d}-{day:02d}"
    conn = get_db_connection()
    appointments = conn.execute(
        "SELECT * FROM appointments WHERE appointment_datetime LIKE ?",
        (date_str + "T%",)
    ).fetchall()
    conn.close()
    appointments = sorted(appointments, key=lambda a: a['appointment_datetime'])
    return render_template("day_view.html", date=date_str, appointments=appointments)

# Rota raiz: redireciona para o calendário do mês atual
@app.route('/')
def index():
    today = datetime.today()
    return redirect(url_for('calendar_view', year=today.year, month=today.month))

# --- Agendamento ---
@app.route('/schedule', methods=['GET', 'POST'])
def schedule():
    if request.method == 'POST':
        customer_name = request.form['customer_name']
        service_type = request.form['service_type']
        # Se for agendamento recorrente (pacote)
        if 'is_package' in request.form:
            recurrence_days = request.form.getlist('recurrence_days')
            recurrence_time = request.form['recurrence_time']
            duration_weeks = int(request.form['duration_weeks'])
            # Lógica simplificada: insere o mesmo horário para cada dia selecionado
            for week in range(duration_weeks):
                for day in recurrence_days:
                    appointment_datetime = request.form['appointment_datetime']
                    conn = get_db_connection()
                    conn.execute(
                        "INSERT INTO appointments (customer_name, service_type, appointment_datetime) VALUES (?, ?, ?)",
                        (customer_name, service_type, appointment_datetime)
                    )
                    conn.commit()
                    conn.close()
        else:
            appointment_datetime = request.form['appointment_datetime']
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO appointments (customer_name, service_type, appointment_datetime) VALUES (?, ?, ?)",
                (customer_name, service_type, appointment_datetime)
            )
            conn.commit()
            conn.close()
        flash("Agendamento realizado com sucesso!")
        return redirect(url_for('calendar_view', year=datetime.now().year, month=datetime.now().month))
    return render_template('schedule.html')

# --- Editar Agendamento ---
@app.route('/edit_appointment/<int:appointment_id>', methods=['GET', 'POST'])
def edit_appointment(appointment_id):
    conn = get_db_connection()
    appointment = conn.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
    if not appointment:
        conn.close()
        flash("Agendamento não encontrado!")
        return redirect(url_for('calendar_view', year=datetime.now().year, month=datetime.now().month))
    if request.method == 'POST':
        customer_name = request.form['customer_name']
        service_type = request.form['service_type']
        appointment_datetime = request.form['appointment_datetime']
        conn.execute(
            "UPDATE appointments SET customer_name = ?, service_type = ?, appointment_datetime = ? WHERE id = ?",
            (customer_name, service_type, appointment_datetime, appointment_id)
        )
        conn.commit()
        conn.close()
        flash("Agendamento atualizado com sucesso!")
        return redirect(url_for('calendar_view', year=datetime.now().year, month=datetime.now().month))
    conn.close()
    return render_template('edit_appointment.html', appointment=appointment)

# --- Excluir Agendamento ---
@app.route('/delete_appointment/<int:appointment_id>', methods=['POST'])
def delete_appointment(appointment_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM appointments WHERE id = ?", (appointment_id,))
    conn.commit()
    conn.close()
    flash("Agendamento excluído com sucesso!")
    return redirect(url_for('calendar_view', year=datetime.now().year, month=datetime.now().month))

# --- Produtos ---
@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        barcode = request.form['barcode']
        name = request.form['name']
        price = float(request.form['price'])
        stock = int(request.form['stock'])
        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO products (barcode, name, price, stock) VALUES (?, ?, ?, ?)",
                (barcode, name, price, stock)
            )
            conn.commit()
            flash("Produto adicionado com sucesso!")
        except sqlite3.IntegrityError:
            flash("Erro: Código de barras já existe!")
        conn.close()
        return redirect(url_for('add_product'))
    return render_template('product_add.html')

# Rota para exibir o estoque (lista de produtos)
@app.route('/stock')
def stock():
    conn = get_db_connection()
    products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return render_template('stock.html', products=products)

# Rota para editar um produto
@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    conn = get_db_connection()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        conn.close()
        flash("Produto não encontrado!")
        return redirect(url_for('stock'))
    
    if request.method == 'POST':
        barcode = request.form['barcode']
        name = request.form['name']
        price = float(request.form['price'])
        stock_val = int(request.form['stock'])
        conn.execute(
            "UPDATE products SET barcode = ?, name = ?, price = ?, stock = ? WHERE id = ?",
            (barcode, name, price, stock_val, product_id)
        )
        conn.commit()
        conn.close()
        flash("Produto atualizado com sucesso!")
        return redirect(url_for('stock'))
    conn.close()
    return render_template('edit_product.html', product=product)

# Rota para excluir um produto
@app.route('/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    flash("Produto excluído com sucesso!")
    return redirect(url_for('stock'))

# Rota para incrementar/atualizar a quantidade de um produto (opcional)
@app.route('/update_stock/<int:product_id>', methods=['POST'])
def update_stock(product_id):
    # Exemplo: Incrementa o estoque. Você pode implementar uma lógica mais completa.
    additional = int(request.form.get('additional', 0))
    conn = get_db_connection()
    conn.execute(
        "UPDATE products SET stock = stock + ? WHERE id = ?",
        (additional, product_id)
    )
    conn.commit()
    conn.close()
    flash("Estoque atualizado!")
    return redirect(url_for('stock'))


# --- Vendas ---
@app.route('/new_sale', methods=['GET', 'POST'])
def new_sale():
    if request.method == 'POST':
        barcode = request.form['barcode']
        quantity = int(request.form['quantity'])
        conn = get_db_connection()
        product = conn.execute("SELECT * FROM products WHERE barcode = ?", (barcode,)).fetchone()
        if product:
            total = product['price'] * quantity
            cursor = conn.execute(
                "INSERT INTO sales (sale_date, total) VALUES (?, ?)",
                (datetime.now().isoformat(), total)
            )
            sale_id = cursor.lastrowid
            conn.execute(
                "INSERT INTO sale_items (sale_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                (sale_id, product['id'], quantity, product['price'])
            )
            conn.commit()
            flash("Venda registrada com sucesso!")
        else:
            flash("Produto não encontrado!")
        conn.close()
        return redirect(url_for('new_sale'))
    return render_template('sale_new.html')

if __name__ == '__main__':
    app.run(debug=True)
