from flask import Flask, render_template, redirect, request, url_for
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from models import db, User, Role, MenuCategory, MenuItem, Order, OrderItem, Table
import threading
import webbrowser

app = Flask(__name__)
app.config.from_object(Config)

# ---------------- BACK BUTTON FIX ----------------
@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# ---------------- INIT ----------------
def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------------- DB SETUP ----------------
with app.app_context():
    db.create_all()

    if not Role.query.first():
        admin_role = Role(name="Admin")
        waiter_role = Role(name="Waiter")
        kitchen_role = Role(name="Kitchen")
        cashier_role = Role(name="Cashier")

        db.session.add_all([admin_role, waiter_role, kitchen_role, cashier_role])
        db.session.commit()

        admin_user = User(
            name="Admin",
            email="admin@gmail.com",
            password=generate_password_hash("admin123"),
            role_id=admin_role.id
        )

        waiter_user = User(
            name="Waiter",
            email="waiter@gmail.com",
            password=generate_password_hash("waiter123"),
            role_id=waiter_role.id
        )

        db.session.add_all([admin_user, waiter_user])
        db.session.commit()

    if not Table.query.first():
        for i in range(1, 6):
            db.session.add(Table(table_number=i))
        db.session.commit()

# ---------------- LOGIN ----------------
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)

            if user.role_id == 1:
                return redirect(url_for('admin_dashboard'))
            elif user.role_id == 2:
                return redirect(url_for('waiter_dashboard'))
            elif user.role_id == 3:
                return redirect(url_for('kitchen_dashboard'))
            elif user.role_id == 4:
                return redirect(url_for('cashier_dashboard'))

    return render_template('login.html')

# ---------------- DASHBOARDS ----------------
@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role_id != 1:
        return redirect(url_for('login'))
    return render_template('admin_dashboard.html')

@app.route('/waiter')
@login_required
def waiter_dashboard():
    if current_user.role_id != 2:
        return redirect(url_for('login'))
    return render_template('waiter_dashboard.html')

@app.route('/kitchen')
@login_required
def kitchen_dashboard():
    if current_user.role_id != 3:
        return redirect(url_for('login'))
    return render_template('kitchen_dashboard.html')

@app.route('/cashier')
@login_required
def cashier_dashboard():
    if current_user.role_id not in [1, 4]:
        return redirect(url_for('login'))
    return render_template('cashier_dashboard.html')

# ---------------- CATEGORY ----------------
@app.route('/add-category', methods=['GET', 'POST'])
@login_required
def add_category():
    if current_user.role_id != 1:
        return redirect(url_for('login'))

    if request.method == 'POST':
        db.session.add(MenuCategory(name=request.form['name']))
        db.session.commit()
        return redirect(url_for('admin_dashboard'))

    return render_template('add_category.html')

# ---------------- ITEM ----------------
@app.route('/add-item', methods=['GET', 'POST'])
@login_required
def add_item():
    if current_user.role_id != 1:
        return redirect(url_for('login'))

    categories = MenuCategory.query.all()

    if request.method == 'POST':
        item = MenuItem(
            name=request.form['name'],
            price=float(request.form['price']),
            category_id=request.form['category_id'],
            stock=int(request.form['stock']),
            is_available=True
        )
        db.session.add(item)
        db.session.commit()
        return redirect(url_for('admin_dashboard'))

    return render_template('add_item.html', categories=categories)

@app.route('/view-items')
@login_required
def view_items():
    if current_user.role_id != 1:
        return redirect(url_for('login'))

    items = MenuItem.query.all()
    return render_template('view_items.html', items=items)

# ---------------- ORDERS ----------------
@app.route('/orders')
@login_required
def view_orders():
    if current_user.role_id == 1:
        orders = Order.query.all()
    elif current_user.role_id == 2:
        orders = Order.query.filter_by(waiter_id=current_user.id).all()
    else:
        return redirect(url_for('login'))

    return render_template('orders.html', orders=orders)

@app.route('/create-order', methods=['GET', 'POST'])
@login_required
def create_order():
    if current_user.role_id != 2:
        return redirect(url_for('login'))

    tables = Table.query.filter_by(status="Free").all()
    items = MenuItem.query.filter_by(is_available=True).all()

    if request.method == 'POST':
        order = Order(
            table_id=request.form['table_id'],
            waiter_id=current_user.id
        )
        db.session.add(order)
        db.session.commit()

        total_amount = 0

        for item_id in request.form.getlist('item_ids'):
            quantity = int(request.form.get(f'quantity_{item_id}', 1))
            menu_item = MenuItem.query.get(item_id)

            if menu_item.stock < quantity:
                return f"Not enough stock for {menu_item.name}"

            menu_item.stock -= quantity
            if menu_item.stock == 0:
                menu_item.is_available = False

            db.session.add(OrderItem(order_id=order.id, menu_item_id=item_id, quantity=quantity))
            total_amount += menu_item.price * quantity

        order.total_amount = total_amount
        Table.query.get(order.table_id).status = "Occupied"

        db.session.commit()
        return redirect(url_for('waiter_dashboard'))

    return render_template('create_order.html', tables=tables, items=items)

# ---------------- COMPLETE ORDER (WAITER) ----------------
@app.route('/complete-order/<int:order_id>')
@login_required
def complete_order(order_id):
    if current_user.role_id != 2:
        return redirect(url_for('login'))

    order = Order.query.get_or_404(order_id)

    order.status = "Completed"
    Table.query.get(order.table_id).status = "Free"

    db.session.commit()

    return redirect(url_for('view_orders'))
# ---------------- UPDATE STOCK ----------------
@app.route('/update-stock/<int:item_id>', methods=['POST'])
@login_required
def update_stock(item_id):
    if current_user.role_id != 1:
        return redirect(url_for('login'))

    item = MenuItem.query.get_or_404(item_id)

    added_stock = int(request.form['added_stock'])
    item.stock += added_stock

    if item.stock > 0:
        item.is_available = True

    db.session.commit()

    return redirect(url_for('view_items'))
# ---------------- KITCHEN ----------------
@app.route('/kitchen-orders')
@login_required
def kitchen_orders():
    if current_user.role_id not in [1, 2, 3]:
        return redirect(url_for('login'))

    orders = Order.query.filter(Order.status != "Completed").all()
    return render_template('kitchen_orders.html', orders=orders)

@app.route('/order-ready/<int:order_id>')
@login_required
def order_ready(order_id):
    if current_user.role_id != 3:
        return redirect(url_for('login'))

    order = Order.query.get_or_404(order_id)
    order.status = "Ready"
    db.session.commit()

    return redirect(url_for('kitchen_orders'))

# ---------------- CASHIER ----------------
@app.route('/cashier-orders')
@login_required
def cashier_orders():
    if current_user.role_id not in [1, 4]:
        return redirect(url_for('login'))

    orders = Order.query.filter_by(status="Ready").all()
    return render_template('cashier_orders.html', orders=orders)

@app.route('/complete-payment/<int:order_id>')
@login_required
def complete_payment(order_id):
    if current_user.role_id not in [1, 4]:
        return redirect(url_for('login'))

    order = Order.query.get_or_404(order_id)
    order.status = "Completed"
    Table.query.get(order.table_id).status = "Free"

    db.session.commit()

    return redirect(url_for('cashier_orders'))

# ---------------- LOGOUT ----------------
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ---------------- RUN ----------------
if __name__ == '__main__':
    threading.Timer(1, open_browser).start()
    app.run(debug=True)