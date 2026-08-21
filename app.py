

from tracemalloc import start

from flask import Flask, jsonify, request
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime, timedelta, timezone
from flask_cors import CORS, cross_origin
import webbrowser
import os
import requests
from transformers import pipeline

ENDPOINT = "http://127.0.0.1:5000"

app = Flask(__name__)
CORS(app, support_credentials=True)
@cross_origin(supports_credentials=True)

@app.route('/api/hello_api',methods=['GET'])
def hello():
    return jsonify("message=Hello world restapi"),200

# MongoDB connection
client = MongoClient('mongodb+srv://talashdrive:talashdrive@cluster1.7xzdzgk.mongodb.net/', serverSelectionTimeoutMS=1000)
db = client['ample_mflix']
collection = db['playlists']
reviews_collection = db['reviews']


@app.route('/health', methods=['GET'])
def health_check():
    try:
        client.admin.command('ping')
        return jsonify({"status": "MongoDB is connected"}), 200
    except Exception as e:
        return jsonify({"status": "Connection failed", "error": str(e)}), 500

@app.route('/count', methods=['GET'])
def get_count():
    try:
        # Use the faster estimated count for an unfiltered collection query.
        # If it is unavailable or not accurate enough, fallback to count_documents.
        try:
            count = collection.estimated_document_count()
        except Exception:
            count = collection.count_documents({})

        return jsonify({"total_documents": count}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/', methods=['GET'])
@app.route('/api/top_10', methods=['GET'])
def get_top_10():
    try:
        result = collection.find(
        {},                      # no filter (all documents)
        {"_id": 1, "likes": 1,"fileName": 1}   # project only _id and likes
        ).sort("likes", -1).limit(10)

        id_list = []
        likes_list = []
        file_list = []
    
        for doc in result:
            doc_id = str(doc.get('_id', ''))
            likes = doc.get('likes', 0)
            file_name = doc.get('fileName', doc_id)  # fallback to doc_id if fileName is missing

            id_list.append(doc_id)
            likes_list.append(likes)
            file_list.append(file_name)

            print("decending order list :", doc_id, likes)
            
        data = [{"id": t, "likes": c, "fileName": f} for t, c, f in zip(id_list, likes_list, file_list)]

        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def read_labels_from_file(labels):
    try:
        if not os.path.exists('labels.txt'):
            open('labels.txt', 'w', encoding='utf-8').close()

        with open('labels.txt', 'r', encoding='utf-8') as f:
            labels.clear()
            for line in f:
                labels.append(line.strip())
        print("Labels read from file successfully.")
    except Exception as e:
        print(f"Error reading labels from file: {e}")

@app.route('/find_category', methods=['GET','POST'])
def find_category():
    try:
        classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

        labels = []
        read_labels_from_file(labels)

        if not labels:
            return jsonify({"error": "No labels found in labels.txt"}), 400

        processed_count = 0

        for document in reviews_collection.find().sort("captions", -1) :
            if not document:
                continue

            description = document.get("captions", "")
            if description is None:
                continue

            description_clean = str(description).replace("[", " ") \
                .replace("]", " ") \
                .replace("{", " ") \
                .replace("}", " ") \
                .replace("'", " ") \
                .strip()

            if not description_clean:
                continue

            if document.get("category") is not None:
                continue

            result = classifier(description_clean, labels, multi_label=True)
            if not result.get("labels"):
                continue

            category = result["labels"][0]
            processed_count += 1

            print("Text:", description_clean)
            print("Prediction:", category)

            if document.get("category") is None:
                reviews_collection.update_one(
                    {"_id": document["_id"]},
                    {"$set": {"category": category}}
                )

        return jsonify({
            "message": "Category processing completed",
            "processed_count": processed_count
        }), 200
    except Exception as e:
        print("Error occurred:", str(e))
        return jsonify({"error": str(e)}), 400
    
# POST /count/recent is not implemented yet
# @app.route('/count/recent', methods=['POST'])
# def post_sun_to_dbt():
#     pass
@app.route('/count/recent', methods=['GET'])
def get_recent_count():
    try:
        count_type = request.args.get('type')

        #count_type = request.args.get('type', 'hour')  # default = hour

        num_access = []
        time_labels = []

        end = datetime.now(timezone.utc)
        start_time = end;
        print("recent start time :",start_time)

        # ------------------ HOUR BASED ------------------
        if count_type == 'hour':
            
            end = datetime.now(timezone.utc)
            start = end - timedelta(hours=24)

          
         
            print("recent start time :",start_time)

            # ------------------ HOUR BASED ------------------
            if count_type == 'hour':
                
                end = datetime.now(timezone.utc)    
                start = end - timedelta(hours=24)

                query = {
                    "_id": {
                        "$gte": ObjectId.from_datetime(start),
                        "$lt": ObjectId.from_datetime(end)
                    }
                }
                result = collection.find(query)

                # Prepare last 24 hours slots
                hours = []
                counts = []
                end = datetime.now(timezone.utc)   
                
                for i in range(24):
                    start = end - timedelta(hours=i+1)
                    access = 0
                    collection.find()
                    counts.append(access)
                    hours.append(start.strftime("%H:00"))
                    end =start

                

                data = [{"time": t, "count": c} for t, c in zip(hours, counts)]
                
                   


        # ------------------ DAY BASED ------------------
        elif count_type == 'day':
            for i in range(7):  # last 7 days (you can change)
                start = end - timedelta(days=1)

                query = {
                    "_id": {
                        "$gte": ObjectId.from_datetime(start),
                        "$lt": ObjectId.from_datetime(end)
                    }
                }

                count = collection.count_documents(query)

                time_labels.append(start.strftime("%Y-%m-%d"))
                num_access.append(count)

                end = start

        else:
            return jsonify({"error": "Invalid type. Use 'hour' or 'day'"}), 400

        # ------------------ FINAL RESPONSE ------------------
        data = [{"time": t, "count": c} for t, c in zip(time_labels, num_access)]

        print("recent end time :", datetime.now(timezone.utc))
        
        print("recent time :", datetime.now(timezone.utc) - start_time)

        return jsonify({"data": data}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/document/<id>', methods=['GET'])
def get_document(id):
    try:
        document_id = ObjectId(id)
        document = collection.find_one({"_id": document_id})
        if document:
            # Convert ObjectId to string for JSON serialization
            document['_id'] = str(document['_id'])
            return jsonify(document), 200
        else:
            return jsonify({"error": "Document not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/documents', methods=['GET'])
def get_documents():
    try:
        limit = int(request.args.get('limit', 10))
        documents = list(collection.find().limit(limit))
        for doc in documents:
            doc['_id'] = str(doc['_id'])
        return jsonify(documents),200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    
    app.run(debug=True)
    

    
