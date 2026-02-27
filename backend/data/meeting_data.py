"""
Mock Data for Meeting Booking System
Hardcoded data for rooms, admins, departments, equipment, and catering
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional
import uuid

# ============================================================================
# ADMIN DATA
# ============================================================================

ADMINS = [
    {
        "id": "admin-hn",
        "name": "Nguyễn Văn Trang",
        "email": "nvtrang3@cmcglobal.vn",
        "role": "Admin Văn phòng Hà Nội",
        "department_code": "HN",
        "floor": 6,
    },
    {
        "id": "admin-dn",
        "name": "Trần Thị Hương",
        "email": "thuong5@cmcglobal.vn",
        "role": "Admin Văn phòng Đà Nẵng",
        "department_code": "DN",
        "floor": 3,
    },
    {
        "id": "admin-hcm",
        "name": "Lê Minh Khoa",
        "email": "lmkhoa2@cmcglobal.vn",
        "role": "Admin Văn phòng TP.HCM",
        "department_code": "HCM",
        "floor": 3,
    },
]

# ============================================================================
# DEPARTMENTS
# ============================================================================

DEPARTMENTS = [
    {
        "id": "dept-hno-1",
        "name": "Phòng Kỹ Thuật",
        "code": "HNO",
        "floor": 1,
        "admin_id": "admin-hno",
    },
    {
        "id": "dept-hno-2",
        "name": "Phòng Kinh Doanh",
        "code": "HNO",
        "floor": 1,
        "admin_id": "admin-hno",
    },
    {
        "id": "dept-hno-3",
        "name": "Phòng Marketing",
        "code": "HNO",
        "floor": 1,
        "admin_id": "admin-hno",
    },
    {
        "id": "dept-dno-1",
        "name": "Phòng Marketing",
        "code": "DNO",
        "floor": 2,
        "admin_id": "admin-dno",
    },
    {
        "id": "dept-dno-2",
        "name": "Phòng HR",
        "code": "DNO",
        "floor": 2,
        "admin_id": "admin-dno",
    },
    {
        "id": "dept-dno-3",
        "name": "Phòng Sale",
        "code": "DNO",
        "floor": 2,
        "admin_id": "admin-dno",
    },
    {
        "id": "dept-hcmo-1",
        "name": "Phòng Tài Chính",
        "code": "HCMO",
        "floor": 3,
        "admin_id": "admin-hcmo",
    },
    {
        "id": "dept-hcmo-2",
        "name": "Phòng Pháp lý",
        "code": "HCMO",
        "floor": 3,
        "admin_id": "admin-hcmo",
    },
    {
        "id": "dept-hcmo-3",
        "name": "Phòng Đối ngoại",
        "code": "HCMO",
        "floor": 3,
        "admin_id": "admin-hcmo",
    },
]

# ============================================================================
# MEETING ROOMS
# ============================================================================

MEETING_ROOMS = [
    # ── HCM (4 rooms, ascending capacity) ────────────────────────────────────
    {
        "id": "rose",
        "name": "Rose",
        "code": "HCM",
        "building": "CMC HCM Office",
        "floor": 4,
        "capacity": 8,
        "equipment": ["projector", "whiteboard", "sound"],
        "available": True,
    },
    {
        "id": "daisy",
        "name": "Daisy",
        "code": "HCM",
        "building": "Crescent Office Tower",
        "floor": 2,
        "capacity": 10,
        "equipment": ["tv", "video_conf", "ac"],
        "available": True,
    },
    {
        "id": "blossom",
        "name": "Blossom",
        "code": "HCM",
        "building": "Saigon Trade Center",
        "floor": 5,
        "capacity": 15,
        "equipment": ["projector", "whiteboard", "ac"],
        "available": True,
    },
    {
        "id": "sunflower",
        "name": "Sun Flower",
        "code": "HCM",
        "building": "Vietcombank Tower",
        "floor": 3,
        "capacity": 20,
        "equipment": ["projector", "tv", "video_conf", "phone"],
        "available": True,
    },
    # ── HN (2 rooms, ascending capacity) ─────────────────────────────────────
    {
        "id": "orchid",
        "name": "Orchid",
        "code": "HN",
        "building": "Lotte Center Hanoi",
        "floor": 8,
        "capacity": 18,
        "equipment": ["projector", "tv", "video_conf", "ac"],
        "available": True,
    },
    {
        "id": "lotus",
        "name": "Lotus",
        "code": "HN",
        "building": "CMC Tower Hà Nội",
        "floor": 6,
        "capacity": 25,
        "equipment": ["projector", "tv", "video_conf", "phone", "mic"],
        "available": True,
    },
    # ── DN (2 rooms, ascending capacity) ─────────────────────────────────────
    {
        "id": "jasmine",
        "name": "Jasmine",
        "code": "DN",
        "building": "CMC Global Đà Nẵng",
        "floor": 3,
        "capacity": 12,
        "equipment": ["projector", "tv", "video_conf"],
        "available": True,
    },
    {
        "id": "tulip",
        "name": "Tulip",
        "code": "DN",
        "building": "Blooming Tower",
        "floor": 5,
        "capacity": 16,
        "equipment": ["projector", "whiteboard", "ac", "sound"],
        "available": True,
    },
]

# ============================================================================
# EQUIPMENT OPTIONS
# ============================================================================

EQUIPMENT_OPTIONS = [
    {"id": "projector", "name": "Máy chiếu", "icon": "📽️", "available": True},
    {"id": "whiteboard", "name": "Bảng trắng", "icon": "📋", "available": True},
    {"id": "tv", "name": "TV 55 inch", "icon": "📺", "available": True},
    {"id": "video_conf", "name": "Hội nghị video", "icon": "🎥", "available": True},
    {"id": "phone", "name": "Điện thoại hội nghị", "icon": "📞", "available": True},
    {"id": "ac", "name": "Điều hòa", "icon": "❄️", "available": True},
]

# ============================================================================
# CATERING OPTIONS
# ============================================================================

CATERING_OPTIONS = [
    {
        "id": "tea-coffee",
        "name": "Trà + Cà phê + Bánh",
        "price": 35000,
        "per_person": True,
        "icon": "☕",
    },
    {
        "id": "coffee",
        "name": "Cà phê + Bánh",
        "price": 30000,
        "per_person": True,
        "icon": "🥐",
    },
    {
        "id": "water",
        "name": "Nước suối",
        "price": 10000,
        "per_person": True,
        "icon": "💧",
    },
    {
        "id": "buffet",
        "name": "Buffet Trưa",
        "price": 150000,
        "per_person": True,
        "icon": "🍱",
    },
    {
        "id": "lunch-box",
        "name": "Cơm hộp",
        "price": 50000,
        "per_person": True,
        "icon": "🍚",
    },
    {
        "id": "fruit",
        "name": "Trái cây",
        "price": 25000,
        "per_person": True,
        "icon": "🍎",
    },
]

# ============================================================================
# BOOKING STATUS
# ============================================================================


class BookingStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


STATUS_LABELS = {
    BookingStatus.PENDING: "Chờ duyệt",
    BookingStatus.APPROVED: "Đã duyệt",
    BookingStatus.REJECTED: "Từ chối",
    BookingStatus.COMPLETED: "Hoàn thành",
    BookingStatus.CANCELLED: "Đã hủy",
}