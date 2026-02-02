# app.py

import os
import io
import stripe
from functools import wraps
from datetime import datetime, timedelta

from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length
from sqlalchemy.types import JSON

# New imports for AI and Image Processing
from google.cloud import aiplatform, vision
from PIL import Image
import requests
import zipfile

# --- App Initialization and Configuration ---
app = Flask(__name__)

# Load configuration from environment variables
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-default-unsafe-secret-key-for-local-dev')
app.config['STRIPE_PUBLISHABLE_KEY'] = os.environ.get('STRIPE_PUBLISHABLE_KEY')
# ... (all other app.config variables for Stripe and GCP)

# DB Config
database_path = os.path.join(os.path.dirname(__file__), 'database')
os.makedirs(database_path, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(database_path, 'site.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize Extensions
stripe.api_key = app.config['STRIPE_SECRET_KEY']
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- Database Models ---
class User(UserMixin, db.Model):
    # ... (User model definition remains the same)
    pass

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    brand = db.Column(db.String(100))
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    comp_retail = db.Column(db.Float)
    comp_high = db.Column(db.Float)
    comp_typical = db.Column(db.Float)
    attributes = db.Column(JSON)

# --- Forms & User Loader ---
# ... (RegistrationForm, LoginForm, and load_user function remain the same)

# --- Custom Decorator ---
# ... (subscription_required decorator remains the same)

# --- Authentication, Stripe, and other existing routes ---
# ... (All routes like /register, /login, /manage-subscription, etc., remain the same)


# ==============================================================================
# AI ANALYSIS AND CORE API LOGIC
# ==============================================================================

def get_products_by_ids(product_codes):
    """Retrieves product details from the database."""
    if not product_codes: return []
    products = Product.query.filter(Product.product_code.in_(product_codes)).all()
    results = []
    for p in products:
        results.append({
            "id": p.product_code, "name": p.name, "brand": p.brand,
            "description": p.description, "image_url": p.image_url,
            "comps": {"retail": p.comp_retail, "high": p.comp_high, "typical": p.comp_typical},
            "attributes": p.attributes
        })
    return results

def analyze_single_object(image_bytes):
    """Analyzes the entire image for the single best match."""
    aiplatform.init(project=app.config['GCP_PROJECT_ID'], location=app.config['GCP_REGION'])
    index_endpoint = aiplatform.MatchingEngineIndexEndpoint(index_endpoint_name=app.config['VERTEX_AI_INDEX_ENDPOINT_ID'])
    model = aiplatform.ImageTextModel.from_pretrained("multimodalembedding@001")
    embedding_response = model.get_embeddings(image_bytes=image_bytes)
    response = index_endpoint.find_neighbors(
        deployed_index_id=app.config['VERTEX_AI_DEPLOYED_INDEX_ID'],
        queries=[embedding_response.image_embedding], num_neighbors=1
    )
    found_ids = [neighbor.id for neighbor in response[0]] if response and response[0] else []
    return get_products_by_ids(found_ids)

def analyze_multi_object(image_bytes):
    """Detects all objects, crops them, gets an ID for each, and returns a list."""
    vision_client = vision.ImageAnnotatorClient()
    aiplatform.init(project=app.config['GCP_PROJECT_ID'], location=app.config['GCP_REGION'])
    index_endpoint = aiplatform.MatchingEngineIndexEndpoint(index_endpoint_name=app.config['VERTEX_AI_INDEX_ENDPOINT_ID'])
    embedding_model = aiplatform.ImageTextModel.from_pretrained("multimodalembedding@001")

    image = vision.Image(content=image_bytes)
    objects = vision_client.object_localization(image=image).localized_object_annotations
    if not objects: return []

    full_image = Image.open(io.BytesIO(image_bytes))
    img_width, img_height = full_image.size
    all_found_products = []

    for obj in objects:
        vertices = obj.bounding_poly.normalized_vertices
        box = (vertices[0].x * img_width, vertices[0].y * img_height, vertices[2].x * img_width, vertices[2].y * img_height)
        cropped_image = full_image.crop(box)
        
        with io.BytesIO() as output:
            cropped_image.save(output, format="JPEG")
            cropped_image_bytes = output.getvalue()

        embedding_response = embedding_model.get_embeddings(image_bytes=cropped_image_bytes)
        response = index_endpoint.find_neighbors(
            deployed_index_id=app.config['VERTEX_AI_DEPLOYED_INDEX_ID'],
            queries=[embedding_response.image_embedding], num_neighbors=1
        )
        if response and response[0]:
            product_id = response[0][0].id
            product_details = get_products_by_ids([product_id])
            if product_details:
                all_found_products.extend(product_details)
    
    unique_products = {p['id']: p for p in all_found_products}.values()
    return list(unique_products)

@app.route('/api/identify-item', methods=['POST'])
@subscription_required
def identify_item():
    """Main API router for handling both single and multi-object analysis."""
    if 'file' not in request.files: return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    mode = request.form.get('mode', 'single')
    content = file.read()

    try:
        if mode == 'multi':
            found_products = analyze_multi_object(content)
        else:
            found_products = analyze_single_object(content)
        
        sorted_matches = sorted(found_products, key=lambda p: p.get('comps', {}).get('high', 0), reverse=True)
        return jsonify({"matches": sorted_matches})
    except Exception as e:
        print(f"ERROR in identify_item (mode: {mode}): {e}")
        return jsonify({"error": "Failed to analyze image"}), 500

# ... (other routes like the image download route)
