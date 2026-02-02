import json
import os
from google.cloud import aiplatform

# --- CONFIGURATION: CHANGE THESE VALUES ---
PROJECT_ID = "your-gcp-project-id-here"
REGION = "us-central1"
BUCKET_NAME = "your-globally-unique-gcs-bucket-name-here"

# This imports the mock database from your Flask app file
# Ensure this script is in the same directory as app.py
from app import MOCK_PRODUCT_DATABASE

def create_embeddings_and_index():
    """
    A one-time script to:
    1. Generate embeddings for each product in the database.
    2. Save embeddings to a file in Google Cloud Storage.
    3. Create a Vertex AI Matching Engine Index from that file.
    4. Create an Index Endpoint to serve the index.
    5. Deploy the index to the endpoint.
    """
    aiplatform.init(project=PROJECT_ID, location=REGION, staging_bucket=f"gs://{BUCKET_NAME}")

    # --- 1. Generate Embeddings ---
    print("Generating embeddings for product database...")
    model = aiplatform.ImageTextModel.from_pretrained("multimodalembedding@001")
    
    embeddings_list = []
    for product in MOCK_PRODUCT_DATABASE:
        print(f"  - Processing: {product['name']}")
        # In a real app, you would also pass an image URI. Here we use the name.
        embedding = model.get_embeddings(text=product['name'])
        embeddings_list.append({
            "id": product['id'],
            "embedding": embedding.text_embedding
        })

    # --- 2. Save Embeddings to a JSONL file in GCS ---
    print("\nSaving embeddings to Google Cloud Storage...")
    embeddings_file_path = "product_embeddings.jsonl"
    with open(embeddings_file_path, "w") as f:
        for item in embeddings_list:
            f.write(json.dumps(item) + "\n")
    
    blob_path = f"embeddings/{embeddings_file_path}"
    os.system(f"gsutil cp {embeddings_file_path} gs://{BUCKET_NAME}/{blob_path}")

    # --- 3. Create a Matching Engine Index ---
    print("\nCreating a new Matching Engine Index (This may take several minutes)...")
    my_index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
        display_name="quicklist_product_index",
        contents_delta_uri=f"gs://{BUCKET_NAME}/embeddings",
        dimensions=len(embeddings_list[0]['embedding']),
        approximate_neighbors_count=10,
        distance_measure_type="DOT_PRODUCT_DISTANCE"
    )
    print(f"Index created. Resource Name: {my_index.resource_name}")

    # --- 4. Create an Index Endpoint ---
    print("\nCreating an Index Endpoint...")
    my_index_endpoint = aiplatform.MatchingEngineIndexEndpoint.create(
        display_name="quicklist_product_endpoint",
        public_endpoint_enabled=True
    )
    print(f"Endpoint created. Resource Name: {my_index_endpoint.resource_name}")
    print("!!! SAVE THIS ENDPOINT ID (the number at the end) FOR YOUR .env FILE !!!")
    
    # --- 5. Deploy the Index ---
    print("\nDeploying index to the endpoint (This may take up to 30 minutes)...")
    deployed_index_id = "quicklist_deployed_index_v1"
    my_index_endpoint.deploy_index(
        index=my_index,
        deployed_index_id=deployed_index_id
    )
    print(f"Index deployed successfully!")
    print(f"!!! USE THIS DEPLOYED INDEX ID FOR YOUR .env FILE: {deployed_index_id} !!!")


if __name__ == "__main__":
    create_embeddings_and_index()

