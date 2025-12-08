from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Enum as SQLEnum, Float
from sqlalchemy.orm import relationship
from flask_login import UserMixin
import enum
import datetime
from .db import Base
from werkzeug.security import generate_password_hash, check_password_hash


def utcnow():
    """
    Return current UTC time as a naive datetime object.
    This replaces datetime.utcnow() which is deprecated.
    """
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class QueueStatus(str, enum.Enum):
    scheduled = 'scheduled'  # Waiting for scheduled time
    queued = 'queued'
    running = 'running'
    paused = 'paused'
    completed = 'completed'
    canceled = 'canceled'


class Poll(Base):
    __tablename__ = 'polls'
    id = Column(Integer, primary_key=True, index=True)
    entryname = Column(String(255), nullable=False)
    pollid = Column(String(64), nullable=False)
    answerid = Column(String(64), nullable=False)
    use_tor = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)
    
    # Poll metadata
    status = Column(String(20), default='active')  # 'active' or 'closed'
    poll_title = Column(String(512), nullable=True)
    total_poll_votes = Column(Integer, default=0)  # Total votes across all answers
    
    # Stats fields for target answer
    total_votes = Column(Integer, default=0)  # Votes for our target answer
    current_place = Column(Integer, nullable=True)
    votes_behind_first = Column(Integer, nullable=True)
    last_snapshot_at = Column(DateTime, nullable=True)
    
    # Trend tracking fields
    previous_place = Column(Integer, nullable=True)  # Previous placement for trend calculation
    place_trend = Column(String(10), nullable=True)  # 'up', 'down', 'same', 'new'
    votes_ahead_second = Column(Integer, nullable=True)  # For 1st place: votes ahead of 2nd place


class PollResult(Base):
    __tablename__ = 'poll_results'
    id = Column(Integer, primary_key=True, index=True)
    poll_id = Column(Integer, ForeignKey('polls.id'), nullable=False)
    timestamp = Column(DateTime, default=utcnow)
    answer_text = Column(String(255), nullable=False)
    votes = Column(Integer, default=0)
    percent = Column(String(10), nullable=True)


class PollVote(Base):
    __tablename__ = 'poll_votes'
    id = Column(Integer, primary_key=True, index=True)
    poll_id = Column(Integer, ForeignKey('polls.id'), nullable=True) # Nullable in case poll deleted or not linked
    pollid = Column(String(64), nullable=False) # Store raw pollid too for redundancy/unlinked
    timestamp = Column(DateTime, default=utcnow)
    answerid = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False) # 'success' or 'fail'
    worker_id = Column(Integer, nullable=True)


class PollSnapshot(Base):
    __tablename__ = 'poll_snapshots'
    id = Column(Integer, primary_key=True, index=True)
    poll_id = Column(Integer, ForeignKey('polls.id'), nullable=True)  # Link to poll if exists
    pollid = Column(String(64), nullable=False)  # Store pollid for redundancy
    answerid = Column(String(64), nullable=False)
    answer_text = Column(String(512), nullable=False)
    votes = Column(Integer, default=0)
    place = Column(Integer, nullable=True)  # Ranking position
    percent = Column(String(10), nullable=True)  # Percentage string
    updated_at = Column(DateTime, default=utcnow)


class QueueItem(Base):
    __tablename__ = 'queue_items'
    id = Column(Integer, primary_key=True, index=True)
    poll_id = Column(Integer, ForeignKey('polls.id'), nullable=True)
    queue_name = Column(String(256), nullable=True)
    pollid = Column(String(64), nullable=False)
    answerid = Column(String(64), nullable=False)
    votes = Column(Integer, default=0)
    threads = Column(Integer, default=1)
    per_run = Column(Integer, default=1)
    pause = Column(Integer, default=0)
    use_vpn = Column(Integer, default=1)
    use_tor = Column(Integer, default=0)
    debug = Column(Boolean, default=False)
    status = Column(SQLEnum(QueueStatus), default=QueueStatus.queued)
    # PID of the running worker process (if running)
    pid = Column(Integer, nullable=True)
    # Exit code or result message
    exit_code = Column(Integer, nullable=True)
    # Link to worker metadata (if created)
    worker_id = Column(Integer, ForeignKey('worker_processes.id'), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    scheduled_at = Column(DateTime, nullable=True)  # When to start this job (if scheduled)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    result_msg = Column(Text, nullable=True)
    
    # Progress tracking fields
    votes_cast = Column(Integer, default=0)        # Total votes attempted
    votes_success = Column(Integer, default=0)     # Successful votes
    success_rate = Column(Float, default=0.0)      # Success percentage
    current_status = Column(String(100), nullable=True)  # e.g., "Processing votes", "Pausing (70s)"
    last_update = Column(DateTime, nullable=True)  # Last progress update time

    poll = relationship('Poll')


class WorkerProcess(Base):
    __tablename__ = 'worker_processes'
    id = Column(Integer, primary_key=True, index=True)
    pid = Column(Integer, nullable=True)
    item_id = Column(Integer, nullable=False)
    log_path = Column(String(1024), nullable=True)
    start_time = Column(DateTime, default=utcnow)
    end_time = Column(DateTime, nullable=True)
    exit_code = Column(Integer, nullable=True)
    result_msg = Column(Text, nullable=True)


class User(UserMixin, Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class PollSchedulerConfig(Base):
    __tablename__ = 'poll_scheduler_config'
    id = Column(Integer, primary_key=True, index=True)
    enabled = Column(Integer, default=0)  # 0 = disabled, 1 = enabled
    interval_minutes = Column(Integer, default=15)
    last_run = Column(DateTime, nullable=True)


class SystemSetting(Base):
    __tablename__ = 'system_settings'
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(64), unique=True, nullable=False)
    value = Column(String(256), nullable=True)

