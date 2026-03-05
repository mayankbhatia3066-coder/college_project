from flask import Flask, render_template, redirect, request, url_for
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from models import db, User, Role,MenuCategory, MenuItem, Order,OrderItem,Table
import threading
import webbrowser
app = Flask(__name__)
app.config.from_object(Config)


def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ===============================
# Create DB and Default Users
# ===============================

#@app.before_first_request
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
# ===============================
# Category Route
# ===============================
@app.route('/add-category', methods=['GET', 'POST'])
@login_required
def add_category():
    if request.method == 'POST':
        name = request.form['name']
        category = MenuCategory(name=name)
        db.session.add(category)
        db.session.commit()
        return redirect(url_for('admin_dashboard'))

    return render_template('add_category.html')
# ===============================
# Item Route
# ===============================
@app.route('/add-item', methods=['GET', 'POST'])
@login_required
def add_item():
    categories = MenuCategory.query.all()

    if request.method == 'POST':
        name = request.form['name']
        price = float(request.form['price'])
        category_id = request.form['category_id']
        stock = int(request.form['stock'])

        item = MenuItem(
            name=name,
            price=price,
            category_id=category_id,
            stock=stock,
            is_available=True if stock > 0 else False
        )

        db.session.add(item)
        db.session.commit()

        return redirect(url_for('admin_dashboard'))

    return render_template('add_item.html', categories=categories)
# ===============================
# Routes
# ===============================

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
#==================
#item route 
#==================
@app.route('/view-items')
@login_required
def view_items():
    items = MenuItem.query.all()
    return render_template('view_items.html', items=items)

#======================
#toggle route
#======================
@app.route('/toggle-item/<int:item_id>')
@login_required
def toggle_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    item.is_available = not item.is_available
    db.session.commit()
    return redirect(url_for('view_items'))
#=======================
#Order Route
#=======================
@app.route('/create-order', methods=['GET', 'POST'])
@login_required
def create_order():
    tables = Table.query.filter_by(status="Free").all()
    items = MenuItem.query.filter_by(is_available=True).all()

    if request.method == 'POST':
        table_id = request.form['table_id']
        selected_items = request.form.getlist('item_ids')

        if not selected_items:
            return "Please select at least one item"

        order = Order(
            table_id=table_id,
            waiter_id=current_user.id
        )
        db.session.add(order)
        db.session.commit()

        total_amount = 0

        for item_id in selected_items:
          quantity = int(request.form.get(f'quantity_{item_id}', 1))
          menu_item = MenuItem.query.get(item_id)

          if menu_item.stock < quantity:
           return f"Not enough stock for {menu_item.name}"

         # Decrease stock
          menu_item.stock -= quantity

         # Auto disable if stock becomes 0
          if menu_item.stock == 0:
            menu_item.is_available = False

          order_item = OrderItem(
          order_id=order.id,
          menu_item_id=item_id,
          quantity=quantity
    )

          db.session.add(order_item)

          total_amount += menu_item.price * quantity

        order.total_amount = total_amount

        table = Table.query.get(table_id)
        table.status = "Occupied"

        db.session.commit()

        return redirect(url_for('waiter_dashboard'))

    return render_template('create_order.html', tables=tables, items=items)
#=======================
#Manual Stock Update
#=======================
@app.route('/update-stock/<int:item_id>', methods=['POST'])
@login_required
def update_stock(item_id):
    item = MenuItem.query.get_or_404(item_id)

    added_stock = int(request.form['added_stock'])
    item.stock += added_stock

    if item.stock > 0:
        item.is_available = True

    db.session.commit()

    return redirect(url_for('view_items'))
#=========================
#Complete Order & Free Table
#=========================
@app.route('/complete-order/<int:order_id>')
@login_required
def complete_order(order_id):
    order = Order.query.get_or_404(order_id)

    order.status = "Completed"

    table = Table.query.get(order.table_id)
    table.status = "Free"

    db.session.commit()

    return redirect(url_for('waiter_dashboard'))
# ========================
# Kitchen Orders
# ========================

@app.route('/kitchen-orders')
@login_required
def kitchen_orders():
    orders = Order.query.filter(Order.status != "Completed").all()
    return render_template('kitchen_orders.html', orders=orders)
@app.route('/start-cooking/<int:order_id>')
#Kitchen Start Cooking Route
@login_required
def start_cooking(order_id):
    order = Order.query.get_or_404(order_id)
    order.status = "Preparing"
    db.session.commit()

    return redirect(url_for('kitchen_orders'))
#Mark Order Ready
@app.route('/order-ready/<int:order_id>')
@login_required
def order_ready(order_id):
    order = Order.query.get_or_404(order_id)
    order.status = "Ready"
    db.session.commit()

    return redirect(url_for('kitchen_orders'))
# ========================
# Cashier Orders
# ========================

@app.route('/cashier-orders')
@login_required
def cashier_orders():
    orders = Order.query.filter_by(status="Ready").all()
    return render_template('cashier_orders.html', orders=orders)
#Payment Route
@app.route('/complete-payment/<int:order_id>')
@login_required
def complete_payment(order_id):

    order = Order.query.get_or_404(order_id)

    order.status = "Completed"

    table = Table.query.get(order.table_id)
    table.status = "Free"

    db.session.commit()

    return redirect(url_for('cashier_orders'))
#==========================
#ADD ORDER LIST PAGE
#==========================

@app.route('/orders')
@login_required
def view_orders():
    orders = Order.query.all()
    return render_template('orders.html', orders=orders)
#==========================
@app.route('/admin')
@login_required
def admin_dashboard():
    return render_template('admin_dashboard.html')


@app.route('/waiter')
@login_required
def waiter_dashboard():
    return render_template('waiter_dashboard.html')


@app.route('/kitchen')
@login_required
def kitchen_dashboard():
    return render_template('kitchen_dashboard.html')


@app.route('/cashier')
@login_required
def cashier_dashboard():
    return render_template('cashier_dashboard.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


if __name__ == '__main__':
      threading.Timer(1, open_browser).start()
      app.run(debug=True)