import asyncio
import json
import logging
import time
import uuid
from typing import Optional

import aiohttp
import websockets
from pydantic import BaseModel

from open_webui.env import SRC_LOG_LEVELS

logger = logging.getLogger(__name__)
logger.setLevel(SRC_LOG_LEVELS["MAIN"])


class ResultModel(BaseModel):
    """
    Execute Code Result Model
    """

    stdout: Optional[str] = ""
    stderr: Optional[str] = ""
    result: Optional[str] = ""


class JupyterCodeExecuter:
    """
    Execute code in jupyter notebook
    """

    def __init__(
        self,
        base_url: str,
        code: str,
        token: str = "",
        password: str = "",
        timeout: int = 60,
    ):
        """
        :param base_url: Jupyter server URL (e.g., "http://localhost:8888")
        :param code: Code to execute
        :param token: Jupyter authentication token (optional)
        :param password: Jupyter password (optional)
        :param timeout: WebSocket timeout in seconds (default: 60s)
        """
        print(f"[CODE-INTERPRETER] Initializing JupyterCodeExecuter for base_url: {base_url}, timeout: {timeout}")
        self.base_url = base_url.rstrip("/")
        self.code = code
        self.token = token
        self.password = password
        self.timeout = timeout
        self.kernel_id = ""
        self.session = aiohttp.ClientSession(base_url=self.base_url)
        self.params = {}
        self.result = ResultModel()
        print("[CODE-INTERPRETER] JupyterCodeExecuter initialized.")

    async def __aenter__(self):
        print("[CODE-INTERPRETER] Entering context manager.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        print("[CODE-INTERPRETER] Exiting context manager.")
        start_time = time.time()
        if self.kernel_id:
            try:
                print(f"[CODE-INTERPRETER] Attempting to delete kernel: {self.kernel_id}")
                delete_url = f"/api/kernels/{self.kernel_id}"
                print(f"[CODE-INTERPRETER] Making API call: DELETE {delete_url} with params: {self.params}")
                async with self.session.delete(
                    delete_url, params=self.params
                ) as response:
                    response.raise_for_status()
                    print(f"[CODE-INTERPRETER] Kernel {self.kernel_id} deleted successfully.")
            except Exception as err:
                logger.exception("close kernel failed, %s", err)
                print(f"[CODE-INTERPRETER] Error deleting kernel {self.kernel_id}: {err}")
        await self.session.close()
        end_time = time.time()
        print(f"[CODE-INTERPRETER] Context manager exit took {end_time - start_time:.4f} seconds.")

    async def run(self) -> ResultModel:
        print("[CODE-INTERPRETER] Starting code execution run.")
        total_start_time = time.time()
        try:
            # Sign in
            print("[CODE-INTERPRETER] Starting sign_in step.")
            start_time = time.time()
            await self.sign_in()
            end_time = time.time()
            print(f"[CODE-INTERPRETER] sign_in step finished in {end_time - start_time:.4f} seconds.")

            # Init kernel
            print("[CODE-INTERPRETER] Starting init_kernel step.")
            start_time = time.time()
            await self.init_kernel()
            end_time = time.time()
            print(f"[CODE-INTERPRETER] init_kernel step finished in {end_time - start_time:.4f} seconds.")

            # Execute code
            print("[CODE-INTERPRETER] Starting execute_code step.")
            start_time = time.time()
            await self.execute_code()
            end_time = time.time()
            print(f"[CODE-INTERPRETER] execute_code step finished in {end_time - start_time:.4f} seconds.")

        except Exception as err:
            logger.exception("execute code failed, %s", err)
            print(f"[CODE-INTERPRETER] Error during run: {err}")
            self.result.stderr = f"Error: {err}"
        
        total_end_time = time.time()
        print(f"[CODE-INTERPRETER] Code execution run finished in {total_end_time - total_start_time:.4f} seconds.")
        print(f"[CODE-INTERPRETER] Final Result - STDOUT: '{self.result.stdout}', STDERR: '{self.result.stderr}', RESULT: '{self.result.result}'")
        return self.result

    async def sign_in(self) -> None:
        print("[CODE-INTERPRETER] Starting sign_in process.")
        start_time = time.time()
        # password authentication
        if self.password and not self.token:
            print("[CODE-INTERPRETER] Attempting password authentication.")
            try:
                # Get XSRF token
                print("[CODE-INTERPRETER] Making API call: GET /login")
                async with self.session.get("/login") as response:
                    response.raise_for_status()
                    xsrf_token = response.cookies.get("_xsrf")
                    if not xsrf_token:
                         print("[CODE-INTERPRETER] _xsrf token not found in cookies.")
                         raise ValueError("_xsrf token not found")
                    xsrf_token_value = xsrf_token.value
                    print(f"[CODE-INTERPRETER] Received _xsrf token: {xsrf_token_value}")
                    self.session.cookie_jar.update_cookies(response.cookies)
                    self.session.headers.update({"X-XSRFToken": xsrf_token_value})
                
                # Post login credentials
                login_data = {"_xsrf": xsrf_token_value, "password": self.password}
                print(f"[CODE-INTERPRETER] Making API call: POST /login with data: { {k: (v[:10] + '...' if k == 'password' else v) for k, v in login_data.items()} }") # Avoid logging full password
                async with self.session.post(
                    "/login",
                    data=login_data,
                    allow_redirects=False,
                ) as response:
                    response.raise_for_status()
                    print("[CODE-INTERPRETER] Password authentication successful.")
                    self.session.cookie_jar.update_cookies(response.cookies)
            except Exception as e:
                print(f"[CODE-INTERPRETER] Password authentication failed: {e}")
                raise

        # token authentication
        if self.token:
            print(f"[CODE-INTERPRETER] Using token authentication. Token: {self.token[:5]}...") # Log partial token
            self.params.update({"token": self.token})
        
        end_time = time.time()
        print(f"[CODE-INTERPRETER] sign_in process finished in {end_time - start_time:.4f} seconds.")

    async def init_kernel(self) -> None:
        print("[CODE-INTERPRETER] Initializing kernel.")
        start_time = time.time()
        kernel_url = "/api/kernels"
        try:
            print(f"[CODE-INTERPRETER] Making API call: POST {kernel_url} with params: {self.params}")
            async with self.session.post(
                url=kernel_url, params=self.params
            ) as response:
                response.raise_for_status()
                kernel_data = await response.json()
                self.kernel_id = kernel_data["id"]
                print(f"[CODE-INTERPRETER] Kernel initialized successfully. Kernel ID: {self.kernel_id}")
        except Exception as e:
            print(f"[CODE-INTERPRETER] Kernel initialization failed: {e}")
            raise
        end_time = time.time()
        print(f"[CODE-INTERPRETER] Kernel initialization finished in {end_time - start_time:.4f} seconds.")

    def init_ws(self) -> (str, dict):
        print("[CODE-INTERPRETER] Initializing WebSocket connection details.")
        start_time = time.time()
        ws_base = self.base_url.replace("http", "ws")
        ws_params_str = "?" + "&".join([f"{key}={val}" for key, val in self.params.items()])
        websocket_url = f"{ws_base}/api/kernels/{self.kernel_id}/channels{ws_params_str if len(self.params) > 0 else ''}"
        ws_headers = {}
        if self.password and not self.token:
             # Extract cookies carefully
            cookie_header = "; ".join(
                [f"{cookie.key}={cookie.value}" for cookie in self.session.cookie_jar if cookie.key]
            )
            # Extract relevant headers
            xsrf_header = self.session.headers.get("X-XSRFToken", "")
            ws_headers = {
                "Cookie": cookie_header,
            }
            if xsrf_header:
                 ws_headers["X-XSRFToken"] = xsrf_header
            print(f"[CODE-INTERPRETER] Using password auth headers for WebSocket: { {k: (v[:10] + '...' if k == 'Cookie' else v) for k, v in ws_headers.items()} }") # Avoid logging full cookie
        else:
            print("[CODE-INTERPRETER] Using token auth (or no auth) for WebSocket.")

        end_time = time.time()
        print(f"[CODE-INTERPRETER] WebSocket URL: {websocket_url}")
        print(f"[CODE-INTERPRETER] WebSocket Headers: {ws_headers}")
        print(f"[CODE-INTERPRETER] WebSocket initialization details prepared in {end_time - start_time:.4f} seconds.")
        return websocket_url, ws_headers

    async def execute_code(self) -> None:
        print("[CODE-INTERPRETER] Preparing to execute code via WebSocket.")
        start_time = time.time()
        # initialize ws
        websocket_url, ws_headers = self.init_ws()
        print(f"[CODE-INTERPRETER] Attempting to connect to WebSocket: {websocket_url}")
        # execute
        try:
            async with websockets.connect(
                websocket_url, additional_headers=ws_headers, open_timeout=self.timeout # Add open_timeout
            ) as ws:
                print("[CODE-INTERPRETER] WebSocket connection established.")
                await self.execute_in_jupyter(ws)
        except websockets.exceptions.InvalidStatusCode as e:
             print(f"[CODE-INTERPRETER] WebSocket connection failed with status code: {e.status_code}. Headers: {e.headers}")
             raise Exception(f"WebSocket connection failed: Status {e.status_code}") from e
        except Exception as e:
            print(f"[CODE-INTERPRETER] WebSocket connection or execution failed: {e}")
            raise
        end_time = time.time()
        print(f"[CODE-INTERPRETER] Code execution via WebSocket finished in {end_time - start_time:.4f} seconds.")

    async def execute_in_jupyter(self, ws) -> None:
        print("[CODE-INTERPRETER] Executing code within Jupyter via WebSocket.")
        start_time = time.time()
        # send message
        msg_id = uuid.uuid4().hex
        exec_request = {
            "header": {
                "msg_id": msg_id,
                "msg_type": "execute_request",
                "username": "user",
                "session": uuid.uuid4().hex,
                "date": "", # Consider adding datetime.utcnow().isoformat() + "Z"
                "version": "5.3",
            },
            "parent_header": {},
            "metadata": {},
            "content": {
                "code": self.code,
                "silent": False,
                "store_history": True,
                "user_expressions": {},
                "allow_stdin": False,
                "stop_on_error": True,
            },
            "channel": "shell",
        }
        print(f"[CODE-INTERPRETER] Sending execute_request (msg_id: {msg_id}): {json.dumps(exec_request, indent=2)}")
        await ws.send(json.dumps(exec_request))
        
        # parse message
        stdout, stderr, result = "", "", []
        print("[CODE-INTERPRETER] Waiting for messages from kernel...")
        while True:
            try:
                # wait for message
                print(f"[CODE-INTERPRETER] Waiting for next message (timeout: {self.timeout}s)...")
                message = await asyncio.wait_for(ws.recv(), self.timeout)
                message_data = json.loads(message)
                print(f"[CODE-INTERPRETER] Received message: {json.dumps(message_data, indent=2)}")

                # msg id not match, skip
                if message_data.get("parent_header", {}).get("msg_id") != msg_id:
                    print(f"[CODE-INTERPRETER] Skipping message with mismatched parent_header msg_id: {message_data.get('parent_header', {}).get('msg_id')}")
                    continue
                
                # check message type
                msg_type = message_data.get("msg_type")
                print(f"[CODE-INTERPRETER] Processing message of type: {msg_type}")
                match msg_type:
                    case "stream":
                        stream_name = message_data["content"]["name"]
                        stream_text = message_data["content"]["text"]
                        print(f"[CODE-INTERPRETER] Stream message ({stream_name}): {stream_text.strip()}")
                        if stream_name == "stdout":
                            stdout += stream_text
                        elif stream_name == "stderr":
                            stderr += stream_text
                    case "execute_result" | "display_data":
                        data = message_data["content"]["data"]
                        print(f"[CODE-INTERPRETER] Execute result/Display data: {data}")
                        if "image/png" in data:
                            img_data = f"data:image/png;base64,{data['image/png']}"
                            print(f"[CODE-INTERPRETER] Appending image data (first 20 chars): {img_data[:20]}...")
                            result.append(img_data)
                        elif "text/plain" in data:
                            text_data = data["text/plain"]
                            print(f"[CODE-INTERPRETER] Appending text data: {text_data.strip()}")
                            result.append(text_data)
                    case "error":
                        error_traceback = "\n".join(message_data["content"]["traceback"])
                        print(f"[CODE-INTERPRETER] Error message received: {error_traceback}")
                        stderr += error_traceback
                    case "status":
                        execution_state = message_data["content"]["execution_state"]
                        print(f"[CODE-INTERPRETER] Status message: execution_state = {execution_state}")
                        if execution_state == "idle":
                            print("[CODE-INTERPRETER] Kernel is idle, execution likely complete.")
                            break
                    case _:
                         print(f"[CODE-INTERPRETER] Unhandled message type: {msg_type}")

            except asyncio.TimeoutError:
                print(f"[CODE-INTERPRETER] Timeout waiting for message after {self.timeout} seconds.")
                stderr += "\nExecution timed out."
                break
            except websockets.exceptions.ConnectionClosedOK:
                 print("[CODE-INTERPRETER] WebSocket connection closed normally.")
                 break
            except websockets.exceptions.ConnectionClosedError as e:
                 print(f"[CODE-INTERPRETER] WebSocket connection closed with error: Code={e.code}, Reason='{e.reason}'")
                 stderr += f"\nWebSocket connection closed unexpectedly (Code: {e.code})."
                 break
            except Exception as e:
                 print(f"[CODE-INTERPRETER] Error processing message: {e}")
                 stderr += f"\nError processing kernel message: {e}"
                 # Decide whether to break or continue based on the error type
                 break # Safer to break on unexpected errors

        self.result.stdout = stdout.strip()
        self.result.stderr = stderr.strip()
        self.result.result = "\n".join(result).strip() if result else ""
        end_time = time.time()
        print(f"[CODE-INTERPRETER] Finished executing code in Jupyter. Duration: {end_time - start_time:.4f} seconds.")
        print(f"[CODE-INTERPRETER] Parsed STDOUT: '{self.result.stdout}'")
        print(f"[CODE-INTERPRETER] Parsed STDERR: '{self.result.stderr}'")
        print(f"[CODE-INTERPRETER] Parsed RESULT: '{self.result.result}'")


async def execute_code_jupyter(
    base_url: str, code: str, token: str = "", password: str = "", timeout: int = 60
) -> dict:
    print(f"[CODE-INTERPRETER] execute_code_jupyter called with base_url='{base_url}', token='{token[:5]}...', password={'yes' if password else 'no'}, timeout={timeout}")
    print(f"[CODE-INTERPRETER] Code to execute:\n---\n{code}\n---")
    start_time = time.time()
    async with JupyterCodeExecuter(
        base_url, code, token, password, timeout
    ) as executor:
        result = await executor.run()
        final_result = result.model_dump()
    end_time = time.time()
    print(f"[CODE-INTERPRETER] execute_code_jupyter finished in {end_time - start_time:.4f} seconds.")
    print(f"[CODE-INTERPRETER] Returning result: {final_result}")
    return final_result
