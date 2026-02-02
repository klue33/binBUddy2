import os
import io
import stripe
from functools import wraps
from datetime import datetime, timedelta

from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length

from google.cloud import aiplatform

# --- App Initialization and Configuration ---
app = Flask(__name__)

# Load configuration from environment variables
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-default-unsafe-secret-key-for-local-dev')
app.config['STRIPE_PUBLISHABLE_KEY'] = os.environ.get('STRIPE_PUBLISHABLE_KEY')
app.config['STRIPE_SECRET_KEY'] = os.environ.get('STRIPE_SECRET_KEY')
app.config['STRIPE_WEBHOOK_SECRET'] = os.environ.get('STRIPE_WEBHOOK_SECRET')
app.config['STRIPE_PRICE_ID'] = os.environ.get('STRIPE_PRICE_ID')
app.config['GCP_PROJECT_ID'] = os.environ.get('GCP_PROJECT_ID')
app.config['GCP_REGION'] = os.environ.get('GCP_REGION')
app.config['VERTEX_AI_INDEX_ENDPOINT_ID'] = os.environ.get('VERTEX_AI_INDEX_ENDPOINT_ID')
app.config['VERTEX_AI_DEPLOYED_INDEX_ID'] = os.environ.get('VERTEX_AI_DEPLOYED_INDEX_ID')

# Configure the SQLite database to be in a persistent volume
database_path = os.path.join(os.path.dirname(__file__), 'database')
os.makedirs(database_path, exist_ok=True) # Ensure the directory exists
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(database_path, 'site.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize Stripe
stripe.api_key = app.config['STRIPE_SECRET_KEY']

# --- Extensions Initialization ---
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'


# --- Mock Database (used for retrieving product details) ---
MOCK_PRODUCT_DATABASE = [
    {
        "id": "prod_123", "name": "Sony WH-1000XM4 Wireless Headphones", "brand": "Sony", "category": "Electronics / Audio",
        "description": "Industry-leading noise canceling with Dual Noise Sensor technology.", "comps": { "retail": 449.99, "high": 350.00, "typical": 280.00, "low": 220.00 }
    },
    {
        "id": "prod_456", "name": "Logitech MX Master 3S Mouse", "brand": "Logitech", "category": "Electronics / Computer Accessories",
        "description": "An iconic mouse, remastered. Features an 8K DPI sensor.", "comps": { "retail": 129.99, "high": 100.00, "typical": 85.00, "low": 70.00 }
    },
    {
        "id": "prod_789", "name": "Nintendo Switch - OLED Model", "brand": "Nintendo", "category": "Electronics / Video Games",
        "description": "Features a vibrant 7-inch OLED screen and enhanced audio.", "comps": { "retail": 449.99, "high": 420.00, "typical": 380.00, "low": 350.00 }
    },
    {
        "id": "prod_212", "name": "Apple iPad Air (5th Generation)", "brand": "Apple", "category": "Electronics / Tablets",
        "description": "Serious performance in a thin and light design with the Apple M1 chip.", "comps": { "retail": 799.00, "high": 700.00, "typical": 620.00, "low": 550.00 }
    }
]


# --- Database Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    subscription_status = db.Column(db.String(20), nullable=False, default='none')
    trial_end_date = db.Column(db.DateTime)
    stripe_customer_id = db.Column(db.String(120), unique=True)
    stripe_subscription_id = db.Column(db.String(120), unique=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --- Forms ---
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=25)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


# --- Custom Decorator ---
def subscription_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login', next=request.url))
        is_trial_active = (current_user.subscription_status == 'trial' and datetime.utcnow() < current_user.trial_end_date)
        if current_user.subscription_status == 'active' or is_trial_active:
            return f(*args, **kwargs)
        else:
            flash('Your trial has ended. Please subscribe to continue.', 'warning')
            return redirect(url_for('manage_subscription'))
    return decorated_function


# --- Authentication Routes ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data, email=form.email.data,
            subscription_status='trial', trial_end_date=datetime.utcnow() + timedelta(days=3)
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! Your 3-day trial has begun.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Login Unsuccessful. Please check email and password.', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))


# --- Stripe & Subscription Routes ---
@app.route('/manage-subscription')
@login_required
def manage_subscription():
    return render_template('manage_subscription.html')

@app.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    try:
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(email=current_user.email)
            current_user.stripe_customer_id = customer.id
            db.session.commit()

        checkout_session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            line_items=[{'price': app.config['STRIPE_PRICE_ID'], 'quantity': 1}],
            mode='subscription',
            success_url=url_for('manage_subscription', _external=True) + '?success=true',
            cancel_url=url_for('manage_subscription', _external=True) + '?canceled=true',
        )
        return jsonify({'sessionId': checkout_session.id})
    except Exception as e:
        return jsonify(error=str(e)), 403

@app.route('/create-portal-session', methods=['POST'])
@login_required
def create_portal_session():
    portal_session = stripe.billing_portal.Session.create(
        customer=current_user.stripe_customer_id,
        return_url=url_for('manage_subscription', _external=True),
    )
    return redirect(portal_session.url)

@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    event = None
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, app.config['STRIPE_WEBHOOK_SECRET'])
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        return 'Invalid request', 400

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        customer_id = session.get('customer')
        user = User.query.filter_by(stripe_customer_id=customer_id).first()
        if user:
            user.subscription_status = 'active'
            user.stripe_subscription_id = session.get('subscription')
            db.session.commit()
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        user = User.query.filter_by(stripe_subscription_id=subscription.get('id')).first()
        if user:
            user.subscription_status = 'none'
            db.session.commit()
            
    return 'Success', 200


# --- Core Application Routes ---
@app.route('/')
@subscription_required
def index():
    return render_template('index.html')

def get_products_by_ids(ids):
    return [p for p in MOCK_PRODUCT_DATABASE if p['id'] in ids]

@app.route('/api/identify-item', methods=['POST'])
@subscription_required
def identify_item():
    if 'file' not in request.files: return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({"error": "No selected file"}), 400

    try:
        aiplatform.init(project=app.config['GCP_PROJECT_ID'], location=app.config['GCP_REGION'])
        index_endpoint = aiplatform.MatchingEngineIndexEndpoint(index_endpoint_name=app.config['VERTEX_AI_INDEX_ENDPOINT_ID'])
        model = aiplatform.ImageTextModel.from_pretrained("multimodalembedding@001")
        
        content = file.read()
        embedding_response = model.get_embeddings(image_bytes=content)
        query_embedding = embedding_response.image_embedding

        response = index_endpoint.find_neighbors(
            deployed_index_id=app.config['VERTEX_AI_DEPLOYED_INDEX_ID'],
            queries=[query_embedding], num_neighbors=3
        )
        
        found_ids = [neighbor.id for neighbor in response[0]] if response and response[0] else []
        if not found_ids: return jsonify({"matches": []})
        
        found_products = get_products_by_ids(found_ids)
        sorted_matches = sorted(found_products, key=lambda p: p.get('comps', {}).get('high', 0), reverse=True)
        return jsonify({"matches": sorted_matches})
    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({"error": "Failed to analyze image"}), 500

# Context processor to pass variables to all templates
@app.context_processor
def inject_global_vars():
    from datetime import datetime
    return dict(datetime=datetime)

if __name__ == '__main__':
    # This is for local development only.
    # The production server uses the Gunicorn command in the Dockerfile.
    app.run(debug=True, port=5001)
