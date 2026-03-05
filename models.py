from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)

class MenuCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)


class MenuItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    price = db.Column(db.Float)

    category_id = db.Column(db.Integer, db.ForeignKey('menu_category.id'))
    category = db.relationship('MenuCategory', backref='items')  # ADD THIS

    is_available = db.Column(db.Boolean, default=True)
    stock = db.Column(db.Integer, default=0)

class Table(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    table_number = db.Column(db.Integer, unique=True)
    status = db.Column(db.String(20), default="Free")  # Free / Occupied





class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    menu_item_id = db.Column(db.Integer, db.ForeignKey('menu_item.id'))
    quantity = db.Column(db.Integer)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    table_id = db.Column(db.Integer, db.ForeignKey('table.id'))
    table = db.relationship('Table', backref='orders')   # ADD THIS

    waiter_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    waiter = db.relationship('User', backref='orders')   # ADD THIS

    status = db.Column(db.String(20), default="Pending")
    total_amount = db.Column(db.Float, default=0)