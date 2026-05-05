

from tracemalloc import start

from flask import Flask, jsonify, request
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime, timedelta, timezone
from flask_cors import CORS, cross_origin
import webbrowser
import os
import requests

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


@app.route('/count/recent', methods=['GET'])
def get_recent_count():
    try:
        count_type = request.args.get('type')

        #count_type = request.args.get('type', 'hour')  # default = hour

        num_access = []
        time_labels = []

        end = datetime.now(timezone.utc)
        start_time = end;

        print("count_type :",count_type)

        print("recent start time :",start_time)

        # ------------------ HOUR BASED ------------------
        if count_type == 'hour':
            total_start = end - timedelta(hours=24)
    
            # 2. Single query to get all IDs in that range (ordered)
            # We only fetch the '_id' field to keep the payload small
            cursor = collection.find(
                {
                    "_id": {
                        "$gte": ObjectId.from_datetime(total_start),
                        "$lt": ObjectId.from_datetime(end)
                    }
                },
                {"_id": 1}
            ).sort("_id", 1)

            # 3. Pre-calculate your hour boundaries
            # We create a list of timestamps representing each hour mark
            boundaries = [total_start + timedelta(hours=i) for i in range(25)]
            
            # 4. Efficiently bin the results in Python
            # This avoids 24 separate network calls
            id_list = [doc['_id'].generation_time for doc in cursor]
            
            for i in range(24):
                b_start = boundaries[i]
                b_end = boundaries[i+1]
                
                # Count how many timestamps fall within this specific hour
                count = sum(1 for t in id_list if b_start <= t < b_end)
                
                time_labels.append(b_start.strftime("%H:%M"))
                num_access.append(count)

            data = [{"time": t, "count": c} for t, c in zip(time_labels, num_access)]



        # ------------------ DAY BASED ------------------
        elif count_type == 'day':
            # 1. Calculate the full range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)

            # 2. Single query: Get only the _id field for everything in the last 7 days
            # This is much faster than fetching full documents
            cursor = collection.find(
                {"_id": {"$gte": ObjectId.from_datetime(start_date), "$lt": ObjectId.from_datetime(end_date)}},
                {"_id": 1} 
            )

            # 3. Extract dates from ObjectIds and count them in Python
            # ObjectId.generation_time gives us the timestamp without an extra DB field
            day_counts = Counter(doc["_id"].generation_time.strftime("%Y-%m-%d") for doc in cursor)

            # 4. Format for your lists (ensures 0s for missing days)
            time_labels = []
            num_access = []

            for i in range(7):
                day_str = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
                time_labels.append(day_str)
                num_access.append(day_counts.get(day_str, 0))
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
    

    
