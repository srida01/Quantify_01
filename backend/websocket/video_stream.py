from flask_socketio import SocketIO
import threading
import sys
import os

# Add parent directories to path so 'project' module can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from project.backend.strategies.merton_backtest_runner import run_merton_backtest_and_stream

class LiveBacktestStream:
    """Handles the live streaming of backtest video frames."""
    def __init__(self, socketio: SocketIO):
        self.socketio = socketio
 
    def start_streaming(self, start_date, end_date, client_id, results_store):
        print(f"Starting backtest stream for client {client_id}...")
 
        def _run():
            try:
                run_merton_backtest_and_stream(start_date, end_date, self.socketio, client_id, results_store)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.socketio.emit('stream_error', {'error': str(e)}, room=client_id)
            finally:
                print(f"Backtest stream finished for client {client_id}.")
 
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    # def _run_and_stream_backtest(self, start_date: str, end_date: str, client_id: str):
    #     """The target function for the background thread."""
    #     try:
    #         run_merton_backtest_and_stream(
    #             start_date=start_date,
    #             end_date=end_date,
    #             socketio=self.socketio,
    #             client_id=client_id
    #         )
    #     except Exception as e:
    #         print(f"[ERROR] in backtest stream thread: {e}")
    #         import traceback
    #         traceback.print_exc()
    #         self.socketio.emit('stream_error', {
    #             'error': str(e)
    #         }, room=client_id)
    #     finally:
    #         self.is_streaming = False
    #         print(f"Backtest stream finished for client {client_id}.")
