from ninja import Schema, Field
from datetime import datetime
from typing import Optional, List


class UserOut(Schema):
    id: int
    username: str
    first_name: str
    last_name: str
    email: str


class CourseIn(Schema):
    name: str
    description: str = '-'
    price: int = 10000


class CourseOut(Schema):
    id: int
    name: str
    description: str
    price: int
    image: Optional[str] = ''
    teacher: UserOut
    created_at: datetime
    updated_at: datetime


class CourseMemberOut(Schema):
    id: int
    course_id: CourseOut
    roles: str
    created_at: datetime


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


class CommentIn(Schema):
    comment: str
    content_id: int


class CommentUpdate(Schema):
    comment: str


class UserUpdate(Schema):
    first_name: str
    last_name: str
    email: str


class ProgressIn(Schema):
    content_id: int


class MessageOut(Schema):
    message: str