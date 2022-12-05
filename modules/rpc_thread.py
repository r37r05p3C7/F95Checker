import socketserver
import http.server
import contextlib
import threading
import asyncio
import json

from modules.structs import MsgBox
from modules import globals, async_thread, callbacks, error, msgbox, utils

server: socketserver.TCPServer = None
thread: threading.Thread = None


@contextlib.contextmanager
def setup():
    if globals.settings.rpc_enabled:
        start()
    try:
        yield
    finally:
        stop()


def start():
    global thread

    def run_loop():
        global server

        class RPCHandler(http.server.SimpleHTTPRequestHandler):
            def json_response(self, code: int, data: list | dict):
                self.send_response(code)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())

            def do_GET(self):
                match self.path:
                    case "/games":
                        self.json_response(200, list(globals.games))
                        return
                    case _:
                        self.json_response(404, {"success": False})
                        return
                self.json_response(200, {"success": True})

            def do_POST(self):
                match self.path:
                    case "/window/show":
                        globals.gui.show()
                    case "/window/hide":
                        globals.gui.hide()
                    case "/games/add":
                        urls = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                        if matches := utils.extract_thread_matches("\n".join(urls)):
                            globals.gui.show()
                            async def _add_game():
                                await asyncio.sleep(0.1)
                                await callbacks.add_games(*matches)
                            async_thread.run(_add_game())
                    case _:
                        self.json_response(404, {"success": False})
                        return
                self.json_response(200, {"success": True})

        try:
            server = socketserver.TCPServer(("localhost", globals.rpc_port), RPCHandler)
        except Exception:
            raise msgbox.Exc("RPC server error", f"Failed to start RPC server on localhost port {globals.rpc_port}:\n{error.text()}\n\nThis means that the web browser extension will not work, while F95Checker\nitself should be unaffected. Some common causes are:\n - Hyper-V\n - Docker\n - Antivirus or firewall", MsgBox.warn, more=error.traceback())

        server.serve_forever()

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()


def stop():
    global server, thread
    if thread is not None and thread.is_alive() and server is not None:
        server.shutdown()
        thread.join()
    server = None
    thread = None
