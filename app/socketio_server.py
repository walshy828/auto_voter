from flask import copy_current_request_context, request
from flask_socketio import emit, join_room, leave_room
from app.worker import tail_log_for_client
from app.db import SessionLocal
from app.models import WorkerProcess


def register_socketio_handlers(socketio, app):
    @socketio.on('connect')
    def _connect():
        # connection established; client should emit subscribe_log with worker_id
        print(f"[Socket.IO] Client connected: {request.sid}")
        emit('connected', {'msg': 'connected'})

    @socketio.on('subscribe_log')
    def _subscribe(data):
        worker_id = data.get('worker_id')
        sid = request.sid
        
        print(f"[Socket.IO] subscribe_log received: worker_id={worker_id}, sid={sid}")

        if not worker_id:
            print(f"[Socket.IO] ERROR: worker_id required")
            emit('error', {'msg': 'worker_id required'})
            return

        # Verify worker exists in DB
        db = SessionLocal()
        try:
            wp = db.query(WorkerProcess).filter(WorkerProcess.id == worker_id).first()
            if not wp:
                print(f"[Socket.IO] ERROR: Worker {worker_id} not found in DB")
                emit('error', {'msg': f'Worker {worker_id} not found'})
                return
            
            print(f"[Socket.IO] Found worker: id={wp.id}, pid={wp.pid}, log_path={wp.log_path}")
            emit('log_line', {'line': f'[Connected to worker {worker_id}]'})
        finally:
            db.close()

        # start a background task to tail the log and emit 'log_line' events to this sid
        print(f"[Socket.IO] Starting background tail task for worker {worker_id}")
        socketio.start_background_task(tail_log_for_client, socketio, sid, worker_id)

    @socketio.on('unsubscribe_log')
    def _unsubscribe(data):
        # client will disconnect or we will simply stop sending when the background thread exits
        print(f"[Socket.IO] unsubscribe_log received")
        pass

