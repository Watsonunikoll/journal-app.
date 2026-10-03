import os
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
    elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+psycopg://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
    
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    engine = create_engine("sqlite:///journal.db", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Таблица связи Учитель <-> Предмет
teacher_subjects = Table(
    'teacher_subjects', Base.metadata,
    Column('teacher_id', Integer, ForeignKey('users.id', ondelete="CASCADE")),
    Column('subject_id', Integer, ForeignKey('subjects.id', ondelete="CASCADE"))
)

# Таблица связи Учитель <-> Курс
teacher_courses = Table(
    'teacher_courses', Base.metadata,
    Column('teacher_id', Integer, ForeignKey('users.id', ondelete="CASCADE")),
    Column('course_id', Integer, ForeignKey('courses.id', ondelete="CASCADE"))
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    role = Column(String, nullable=False)  # 'admin', 'teacher'
    is_kursghek = Column(Integer, default=0)

    subjects = relationship("Subject", secondary=teacher_subjects, back_populates="teachers")
    courses = relationship("Course", secondary=teacher_courses, back_populates="teachers")

class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)

    teachers = relationship("User", secondary=teacher_courses, back_populates="courses")

class Subject(Base):
    __tablename__ = "subjects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)

    teachers = relationship("User", secondary=teacher_subjects, back_populates="subjects")

class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)

class Grade(Base):
    __tablename__ = "grades"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    lesson_number = Column(Integer, nullable=False)
    grade_value = Column(String, nullable=False)
    date = Column(String, nullable=False)
    is_locked = Column(Integer, default=1)

class LessonTopic(Base):
    __tablename__ = "lesson_topics"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    date = Column(String, nullable=False)
    lesson_number = Column(Integer, nullable=False) # 1..8
    topic_text = Column(String, nullable=True)

def init_db():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()
