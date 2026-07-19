from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, IntegerField, SubmitField
from wtforms.validators import DataRequired, Email, Length, NumberRange
import json
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ecommerce.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    cart_items = db.relationship('CartItem', backref='user', lazy=True, cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='user', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    stock = db.Column(db.Integer, nullable=False)
    
    def __repr__(self):
        return f'<Product {self.name}>'

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    product = db.relationship('Product')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='pending')
    shipping_address = db.Column(db.String(500))
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    product = db.relationship('Product')

# Forms
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    submit = SubmitField('Register')

class AddToCartForm(FlaskForm):
    quantity = IntegerField('Quantity', validators=[DataRequired(), NumberRange(min=1, max=99)], default=1)
    submit = SubmitField('Add to Cart')

class CheckoutForm(FlaskForm):
    shipping_address = StringField('Shipping Address', validators=[DataRequired(), Length(min=5, max=500)])
    submit = SubmitField('Place Order')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Chatbot functions
def get_products_context():
    """Get product data for context"""
    products = Product.query.all()
    context = "Available products:\n"
    for p in products:
        context += f"- {p.name}: ${p.price:.2f} ({p.category}) - {p.description} (Stock: {p.stock})\n"
    return context

def get_chatbot_response(message):
    """Get response from rule-based chatbot (no AI for simplicity)"""
    message_lower = message.lower()
    products = Product.query.all()
    
    # Greetings
    if any(word in message_lower for word in ['hello', 'hi', 'hey', 'greetings']):
        return "Hello! Welcome to our E-commerce store. I'm here to help you find products, check prices, and assist with your shopping. What are you looking for today?"
    
    # Product search
    for product in products:
        if product.name.lower() in message_lower:
            return f"We have {product.name} available for ${product.price:.2f}. {product.description} Stock: {product.stock} units in stock."
    
    # Category queries
    if 'electronics' in message_lower:
        elec_products = [p for p in products if p.category.lower() == 'electronics']
        if elec_products:
            return f"We have these electronics: {', '.join([p.name for p in elec_products])}. Would you like details about any specific product?"
    
    if 'food' in message_lower or 'coffee' in message_lower:
        food_products = [p for p in products if 'food' in p.category.lower() or 'coffee' in p.name.lower()]
        if food_products:
            return f"We have: {', '.join([p.name for p in food_products])}. All our food items are premium quality!"
    
    if 'sports' in message_lower or 'yoga' in message_lower:
        sports_products = [p for p in products if 'sports' in p.category.lower() or 'yoga' in p.name.lower()]
        if sports_products:
            return f"We have sports equipment including: {', '.join([p.name for p in sports_products])}."
    
    # Price queries
    if 'price' in message_lower or 'cost' in message_lower or 'how much' in message_lower:
        return "We have products at various price points. Our range starts from $24.99 for Organic Coffee Beans and goes up to $1299.99 for Laptop Pro X. Which product are you interested in?"
    
    # Stock availability
    if 'stock' in message_lower or 'available' in message_lower or 'in stock' in message_lower:
        return f"We have a total of {sum(p.stock for p in products)} items in stock across {len(products)} different products. What specific product are you looking for?"
    
    # Cart and ordering
    if 'cart' in message_lower:
        if current_user.is_authenticated:
            cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
            if cart_items:
                return f"You have {len(cart_items)} items in your cart. You can view your cart and proceed to checkout."
            else:
                return "Your cart is currently empty. Browse our products and add items you like!"
        else:
            return "Please log in to view your cart."
    
    if 'order' in message_lower or 'buy' in message_lower or 'purchase' in message_lower:
        return "To place an order: 1) Browse our products, 2) Add items to your cart, 3) View your cart, 4) Proceed to checkout. Would you like help with any of these steps?"
    
    if 'help' in message_lower:
        return "I can help you with:\n• Finding products (e.g., 'show me electronics')\n• Price information (e.g., 'how much is the laptop?')\n• Stock availability (e.g., 'is the yoga mat in stock?')\n• Ordering (e.g., 'how to place an order?')\n• Product recommendations"
    
    # Default response
    return "Thank you for your question. I can help you find products, check prices, and assist with orders. Could you please be more specific about what you're looking for? You can ask about: products, prices, stock availability, or ordering."

# Routes
@app.route('/')
def index():
    products = Product.query.all()
    return render_template('index.html', products=products)

@app.route('/product/<int:product_id>', methods=['GET', 'POST'])
@login_required
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    form = AddToCartForm()
    
    if form.validate_on_submit():
        quantity = form.quantity.data
        if product.stock >= quantity:
            cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
            if cart_item:
                cart_item.quantity += quantity
            else:
                cart_item = CartItem(user_id=current_user.id, product_id=product_id, quantity=quantity)
                db.session.add(cart_item)
            db.session.commit()
            flash(f'Added {quantity} x {product.name} to your cart!', 'success')
            return redirect(url_for('view_cart'))
        else:
            flash('Not enough stock available!', 'danger')
    
    return render_template('product_detail.html', product=product, form=form)

@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    response = None
    user_message = None
    
    if request.method == 'POST':
        user_message = request.form.get('message', '').strip()
        if user_message:
            response = get_chatbot_response(user_message)
    
    # Get chat history from session
    chat_history = session.get('chat_history', [])
    
    if user_message and response:
        chat_history.append({'user': user_message, 'bot': response})
        session['chat_history'] = chat_history[-10:]  # Keep last 10 messages
    
    return render_template('chat.html', chat_history=chat_history)

@app.route('/clear_chat', methods=['POST'])
@login_required
def clear_chat():
    session.pop('chat_history', None)
    flash('Chat history cleared.', 'info')
    return redirect(url_for('chat'))

@app.route('/cart')
@login_required
def view_cart():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(item.product.price * item.quantity for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/cart/update/<int:item_id>', methods=['POST'])
@login_required
def update_cart(item_id):
    cart_item = CartItem.query.get_or_404(item_id)
    if cart_item.user_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('view_cart'))
    
    action = request.form.get('action')
    if action == 'increase' and cart_item.product.stock > cart_item.quantity:
        cart_item.quantity += 1
        db.session.commit()
        flash('Cart updated!', 'success')
    elif action == 'decrease' and cart_item.quantity > 1:
        cart_item.quantity -= 1
        db.session.commit()
        flash('Cart updated!', 'success')
    elif action == 'remove':
        db.session.delete(cart_item)
        db.session.commit()
        flash('Item removed from cart.', 'success')
    else:
        flash('Cannot update cart.', 'warning')
    
    return redirect(url_for('view_cart'))

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not cart_items:
        flash('Your cart is empty!', 'warning')
        return redirect(url_for('index'))
    
    total = sum(item.product.price * item.quantity for item in cart_items)
    form = CheckoutForm()
    
    if form.validate_on_submit():
        # Create order
        order = Order(
            user_id=current_user.id,
            total_amount=total,
            status='confirmed',
            shipping_address=form.shipping_address.data
        )
        db.session.add(order)
        db.session.flush()
        
        # Create order items
        for cart_item in cart_items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=cart_item.product_id,
                quantity=cart_item.quantity,
                price=cart_item.product.price
            )
            db.session.add(order_item)
            
            # Update stock
            product = Product.query.get(cart_item.product_id)
            product.stock -= cart_item.quantity
        
        # Clear cart
        CartItem.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        
        flash(f'Order placed successfully! Order #{order.id}', 'success')
        return redirect(url_for('order_confirmation', order_id=order.id))
    
    return render_template('checkout.html', cart_items=cart_items, total=total, form=form)

@app.route('/order/<int:order_id>')
@login_required
def order_confirmation(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))
    return render_template('order_confirmation.html', order=order)

@app.route('/orders')
@login_required
def orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.order_date.desc()).all()
    return render_template('orders.html', orders=orders)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.password == form.password.data:  # In production, use proper password hashing
            login_user(user)
            flash('Logged in successfully!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists', 'danger')
        elif User.query.filter_by(email=form.email.data).first():
            flash('Email already registered', 'danger')
        else:
            user = User(
                username=form.username.data,
                email=form.email.data,
                password=form.password.data  # In production, hash the password!
            )
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Registration successful!', 'success')
            return redirect(url_for('index'))
    
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('index'))

# Initialize database and seed products
def init_db():
    with app.app_context():
        db.create_all()
        
        # Seed products if empty
        if Product.query.count() == 0:
            products_data = [
                {
                    "name": "Laptop Pro X",
                    "price": 1299.99,
                    "category": "Electronics",
                    "description": "High-performance laptop with 16GB RAM, 512GB SSD, and Intel i7 processor",
                    "stock": 25
                },
                {
                    "name": "Wireless Headphones",
                    "price": 149.99,
                    "category": "Electronics",
                    "description": "Noise-cancelling wireless headphones with 40-hour battery life",
                    "stock": 50
                },
                {
                    "name": "Smart Watch",
                    "price": 299.99,
                    "category": "Electronics",
                    "description": "Fitness tracking smartwatch with GPS and heart rate monitor",
                    "stock": 30
                },
                {
                    "name": "Organic Coffee Beans",
                    "price": 24.99,
                    "category": "Food",
                    "description": "Premium organic coffee beans, medium roast, 1lb bag",
                    "stock": 100
                },
                {
                    "name": "Yoga Mat",
                    "price": 39.99,
                    "category": "Sports",
                    "description": "Eco-friendly non-slip yoga mat, 6mm thickness",
                    "stock": 75
                },
                {
                    "name": "Bluetooth Speaker",
                    "price": 89.99,
                    "category": "Electronics",
                    "description": "Portable waterproof Bluetooth speaker with 20W output",
                    "stock": 40
                }
            ]
            
            for product_data in products_data:
                product = Product(**product_data)
                db.session.add(product)
            db.session.commit()
            print("Database initialized with sample products!")

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)