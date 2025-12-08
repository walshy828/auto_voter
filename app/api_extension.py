
@app.route('/workers/<int:worker_id>/download', methods=['GET'])
@require_auth
def worker_download_log(worker_id):
    db = SessionLocal()
    w = db.query(WorkerProcess).filter(WorkerProcess.id == worker_id).first()
    db.close()
    if not w or not w.log_path or not os.path.exists(w.log_path):
        return abort(404, 'Log file not found')
    
    directory = os.path.dirname(w.log_path)
    filename = os.path.basename(w.log_path)
    
    from flask import send_from_directory
    return send_from_directory(directory, filename, as_attachment=True, download_name=f"worker_{worker_id}_log.txt")
