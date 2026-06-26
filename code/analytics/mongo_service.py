import logging
from datetime import datetime

from django.conf import settings
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)

# Saat testing (settings_test.py: MONGO_USE_MOCK = True), pakai mongomock --
# simulasi MongoDB in-memory, supaya test bisa jalan tanpa MongoDB asli dan
# tetap bisa menguji aggregation pipeline secara nyata (bukan cuma di-mock
# function call-nya saja).
if getattr(settings, "MONGO_USE_MOCK", False):
    import mongomock
    client = mongomock.MongoClient()
else:
    from pymongo import MongoClient
    # Timeout pendek agar request API tidak ikut macet jika MongoDB lambat/down.
    client = MongoClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=2000,
        connectTimeoutMS=2000,
    )

db = client[settings.MONGO_DB_NAME]

activity_logs = db["activity_logs"]
learning_analytics = db["learning_analytics"]


def log_activity(user_id, action, course_id=None, course_name=None, metadata=None):
    """
    Mencatat aktivitas ke MongoDB. Kegagalan koneksi MongoDB TIDAK boleh
    menggagalkan request utama (PostgreSQL), jadi exception ditangkap
    dan hanya dicatat sebagai warning di log aplikasi.
    """
    document = {
        "user_id": user_id,
        "action": action,
        "course_id": course_id,
        "course_name": course_name,
        "timestamp": datetime.utcnow(),
        "metadata": metadata or {},
    }
    try:
        return activity_logs.insert_one(document)
    except PyMongoError as exc:
        logger.warning("Gagal menulis activity log ke MongoDB: %s", exc)
        return None


def save_learning_analytics(user_id, course_id, progress_percentage, completed=False):
    document = {
        "user_id": user_id,
        "course_id": course_id,
        "progress_percentage": progress_percentage,
        "completed": completed,
        "timestamp": datetime.utcnow(),
    }
    try:
        return learning_analytics.insert_one(document)
    except PyMongoError as exc:
        logger.warning("Gagal menulis learning analytics ke MongoDB: %s", exc)
        return None


# =============================================================================
# Aggregation queries (Lampiran E - Paket 5: Analytics & Activity Tracking)
# =============================================================================

def report_activity_by_action():
    """Ringkasan umum: jumlah aktivitas dikelompokkan per jenis action."""
    pipeline = [
        {"$group": {"_id": "$action", "total": {"$sum": 1}}},
        {"$sort": {"total": -1}},
    ]
    try:
        return list(activity_logs.aggregate(pipeline))
    except PyMongoError as exc:
        logger.warning("Gagal membaca aggregation activity_logs: %s", exc)
        return []


def report_daily_active_users():
    """
    Aggregation: Daily Active Users (DAU).
    Mengelompokkan activity_logs per tanggal, menghitung jumlah USER UNIK
    (bukan jumlah aktivitas) yang aktif pada tanggal tersebut.
    """
    pipeline = [
        {
            "$group": {
                "_id": {
                    "$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}
                },
                "active_users": {"$addToSet": "$user_id"},
            }
        },
        {
            "$project": {
                "_id": 1,
                "total_active_users": {"$size": "$active_users"},
            }
        },
        {"$sort": {"_id": -1}},
    ]
    try:
        return list(activity_logs.aggregate(pipeline))
    except PyMongoError as exc:
        logger.warning("Gagal membaca aggregation daily_active_users: %s", exc)
        return []


def report_course_popularity():
    """
    Aggregation: Course Popularity.
    Mengelompokkan activity_logs per course, menghitung total aktivitas
    sebagai proxy popularitas (semakin sering course "disentuh", makin populer).
    """
    pipeline = [
        {"$match": {"course_id": {"$ne": None}}},
        {
            "$group": {
                "_id": "$course_name",
                "total_activity": {"$sum": 1},
                "unique_users": {"$addToSet": "$user_id"},
            }
        },
        {
            "$project": {
                "_id": 1,
                "total_activity": 1,
                "unique_user_count": {"$size": "$unique_users"},
            }
        },
        {"$sort": {"total_activity": -1}},
    ]
    try:
        return list(activity_logs.aggregate(pipeline))
    except PyMongoError as exc:
        logger.warning("Gagal membaca aggregation course_popularity: %s", exc)
        return []


def report_completion_summary():
    """
    Aggregation: Completion Summary.
    Membaca collection learning_analytics (bukan activity_logs), lalu
    mengelompokkan per course: berapa banyak snapshot progress yang
    completed=True vs total snapshot yang tercatat untuk course tersebut.
    """
    pipeline = [
        {
            "$group": {
                "_id": "$course_id",
                "total_snapshots": {"$sum": 1},
                "completed_snapshots": {
                    "$sum": {"$cond": [{"$eq": ["$completed", True]}, 1, 0]}
                },
            }
        },
        {"$sort": {"_id": 1}},
    ]
    try:
        results = list(learning_analytics.aggregate(pipeline))
    except PyMongoError as exc:
        logger.warning("Gagal membaca aggregation completion_summary: %s", exc)
        return []

    # $round tidak didukung di semua versi/driver MongoDB secara konsisten
    # (dan tidak ada di mongomock), jadi pembulatan dilakukan di Python.
    for item in results:
        total = item["total_snapshots"]
        completed = item["completed_snapshots"]
        item["completion_ratio_percent"] = round((completed / total) * 100, 2) if total else 0.0

    return results