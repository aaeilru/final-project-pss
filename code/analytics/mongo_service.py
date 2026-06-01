from datetime import datetime
from django.conf import settings
from pymongo import MongoClient


client = MongoClient(settings.MONGO_URI)
db = client[settings.MONGO_DB_NAME]

activity_logs = db["activity_logs"]
learning_analytics = db["learning_analytics"]


def log_activity(user_id, action, course_id=None, course_name=None, metadata=None):
    document = {
        "user_id": user_id,
        "action": action,
        "course_id": course_id,
        "course_name": course_name,
        "timestamp": datetime.utcnow(),
        "metadata": metadata or {},
    }

    return activity_logs.insert_one(document)


def save_learning_analytics(user_id, course_id, progress_percentage, completed=False):
    document = {
        "user_id": user_id,
        "course_id": course_id,
        "progress_percentage": progress_percentage,
        "completed": completed,
        "timestamp": datetime.utcnow(),
    }

    return learning_analytics.insert_one(document)


def report_activity_by_action():
    pipeline = [
        {
            "$group": {
                "_id": "$action",
                "total": {"$sum": 1},
            }
        },
        {
            "$sort": {
                "total": -1
            }
        }
    ]

    return list(activity_logs.aggregate(pipeline))


def report_activity_by_course():
    pipeline = [
        {
            "$match": {
                "course_id": {
                    "$ne": None
                }
            }
        },
        {
            "$group": {
                "_id": "$course_name",
                "total_activity": {"$sum": 1},
            }
        },
        {
            "$sort": {
                "total_activity": -1
            }
        }
    ]

    return list(activity_logs.aggregate(pipeline))