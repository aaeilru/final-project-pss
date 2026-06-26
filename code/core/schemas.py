from ninja import Schema, Field
from datetime import datetime
from typing import Optional, List


class UserOut(Schema):
    id: int
    username: str
    first_name: str
    last_name: str
    email: str


class UserRoleOut(Schema):
    id: int
    username: str
    email: str
    is_superuser: bool
    role: str


class CategoryIn(Schema):
    name: str
    description: str = '-'


class CategoryOut(Schema):
    id: int
    name: str
    slug: str
    description: str


class CourseIn(Schema):
    name: str
    description: str = '-'
    price: int = 10000
    category_id: Optional[int] = None


class CourseOut(Schema):
    id: int
    name: str
    description: str
    price: int
    image: Optional[str] = None
    category: Optional[CategoryOut] = None
    teacher: UserOut
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def resolve_image(obj):
        if obj.image:
            return obj.image.name
        return None


class CourseMemberOut(Schema):
    id: int
    course_id: CourseOut
    roles: str


class ContentTitleOut(Schema):
    id: int
    name: str


class DetailCourseOut(CourseOut):
    contents: List[ContentTitleOut] = Field(
        ..., alias="coursecontent_set"
    )


class CourseContentIn(Schema):
    name: str
    description: str = '-'
    video_url: Optional[str] = None
    course_id: int
    parent_id: Optional[int] = None


class CourseContentOut(Schema):
    id: int
    name: str
    description: str
    video_url: Optional[str] = None
    course_id: int
    parent_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class Register(Schema):
    username: str
    password: str
    email: str
    first_name: str
    last_name: str
    role: str = "student"  # hanya "student" atau "instructor", admin tidak boleh daftar sendiri


class UserUpdate(Schema):
    first_name: str
    last_name: str
    email: str


class RoleUpdate(Schema):
    role: str  # "student" atau "instructor"


class CommentIn(Schema):
    comment: str
    content_id: int


class CommentUpdate(Schema):
    comment: str


class ProgressIn(Schema):
    content_id: int


class ProgressOut(Schema):
    message: str
    progress_percentage: float
    completed: bool


class MessageOut(Schema):
    message: str


class TaskTriggerOut(Schema):
    message: str
    task_id: str


class TaskStatusOut(Schema):
    task_id: str
    status: str
    result: Optional[str] = None


class CertificateOut(Schema):
    id: int
    code: str
    course_id: int
    course_name: str = None
    issued_at: datetime

    @staticmethod
    def resolve_course_name(obj):
        return obj.course.name


class CourseReportOut(Schema):
    course_id: int
    course_name: str
    enrollment_count: int
    completed_count: int
    completion_rate: float
    updated_at: Optional[datetime] = None