import asyncio
import json
import logging
import time
import uuid
from typing import Optional, Dict

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
            chat_id: str = "",
            token: str = "",
            timeout: int = 60,
    ):
        """
        :param base_url: Jupyter server URL (e.g., "http://localhost:8888")
        :param code: Code to execute
        :param chat_id: Identifier for the chat session (optional)
        :param token: Jupyter authentication token (optional)
        :param timeout: WebSocket timeout in seconds (default: 60s)
        """
        print(
            f"[CODE-INTERPRETER] Initializing JupyterCodeExecuter for base_url: {base_url}, timeout: {timeout}, chat_id: {chat_id}")
        self.base_url = base_url.rstrip("/")
        self.code = code
        self.chat_id = chat_id
        self.notebook_id = f"notebook-{chat_id}.ipynb" if chat_id else None  # Construct notebook ID string
        print("[CODE-INTERPRETER] self.notebook_id:", self.notebook_id)
        self.token = token
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

        # Don't delete the kernel if it's associated with a notebook - preserve it for future executions
        if self.kernel_id and not self.notebook_id:
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
        else:
            print(f"[CODE-INTERPRETER] Preserving kernel {self.kernel_id} for notebook {self.notebook_id}")

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

            # Check/create notebook
            print("[CODE-INTERPRETER] Starting check_or_create_notebook step.")
            start_time = time.time()
            notebook_path = await self.check_or_create_notebook()
            end_time = time.time()
            print(f"[CODE-INTERPRETER] check_or_create_notebook step finished in {end_time - start_time:.4f} seconds.")

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
        print(
            f"[CODE-INTERPRETER] Final Result - STDOUT: '{self.result.stdout}', STDERR: '{self.result.stderr}', RESULT: '{self.result.result}'")
        return self.result

    async def sign_in(self) -> None:
        print("[CODE-INTERPRETER] Starting sign_in process.")
        start_time = time.time()

        if self.token:
            print(f"[CODE-INTERPRETER] Using token authentication. Token: ******")
            self.params.update({"token": self.token})

        end_time = time.time()
        print(f"[CODE-INTERPRETER] sign_in process finished in {end_time - start_time:.4f} seconds.")

    def init_ws(self) -> tuple[str, dict]:
        print("[CODE-INTERPRETER] Initializing WebSocket connection details.")
        start_time = time.time()
        ws_base = self.base_url.replace("http", "ws")
        ws_params_str = "?" + "&".join([f"{key}={val}" for key, val in self.params.items()])
        websocket_url = f"{ws_base}/api/kernels/{self.kernel_id}/channels{ws_params_str if len(self.params) > 0 else ''}"
        ws_headers = {}

        print("[CODE-INTERPRETER] Using token auth (or no auth) for WebSocket.")

        end_time = time.time()
        print(f"[CODE-INTERPRETER] WebSocket URL: {websocket_url}")
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
                    websocket_url, additional_headers=ws_headers, open_timeout=self.timeout  # Add open_timeout
            ) as ws:
                print("[CODE-INTERPRETER] WebSocket connection established.")
                await self.execute_in_jupyter(ws)
        except websockets.exceptions.InvalidStatusCode as e:
            print(
                f"[CODE-INTERPRETER] WebSocket connection failed with status code: {e.status_code}. Headers: {e.headers}")
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
                "date": "",  # Consider adding datetime.utcnow().isoformat() + "Z"
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
        execution_count = None
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
                    print(
                        f"[CODE-INTERPRETER] Skipping message with mismatched parent_header msg_id: {message_data.get('parent_header', {}).get('msg_id')}")
                    continue

                # check message type
                msg_type = message_data.get("header", {}).get("msg_type")
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
                        content = message_data.get("content", {})
                        data = content.get("data", {})
                        print(f"[CODE-INTERPRETER] Execute result/Display data: {data}")

                        # Get execution count if available
                        if "execution_count" in content and execution_count is None:
                            execution_count = content["execution_count"]
                            print(f"[CODE-INTERPRETER] Execution count: {execution_count}")

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
                    case "execute_input":
                        # Get execution count from input too if not yet set
                        if "execution_count" in message_data.get("content", {}) and execution_count is None:
                            execution_count = message_data["content"]["execution_count"]
                            print(f"[CODE-INTERPRETER] Execution count from input: {execution_count}")
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
                break  # Safer to break on unexpected errors

        self.result.stdout = stdout.strip()
        self.result.stderr = stderr.strip()
        self.result.result = "\n".join(result).strip() if result else ""
        end_time = time.time()
        print(f"[CODE-INTERPRETER] Finished executing code in Jupyter. Duration: {end_time - start_time:.4f} seconds.")
        print(f"[CODE-INTERPRETER] Parsed STDOUT: '{self.result.stdout}'")
        print(f"[CODE-INTERPRETER] Parsed STDERR: '{self.result.stderr}'")
        print(f"[CODE-INTERPRETER] Parsed RESULT: '{self.result.result}'")

        # Append executed code to the notebook
        if self.notebook_id:
            await self.append_to_notebook({
                "code": self.code,
                "stdout": self.result.stdout,
                "stderr": self.result.stderr,
                "result": self.result.result,
                "execution_count": execution_count
            })

    async def append_to_notebook(self, execution_data: Dict) -> bool:
        """
        Append code and its output to the notebook

        Args:
            execution_data: Dict containing code, stdout, stderr, result

        Returns:
            True if successful, False otherwise
        """
        if not self.notebook_id:
            print("[CODE-INTERPRETER] No notebook_id specified, skipping append to notebook.")
            return False

        try:
            # Get current notebook content
            print(f"[CODE-INTERPRETER] Getting current content of notebook '{self.notebook_id}'.")
            async with self.session.get(
                    f"/api/contents/{self.notebook_id}",
                    params=self.params
            ) as response:
                response.raise_for_status()
                notebook_data = await response.json()

            # Prepare cell outputs
            cell_outputs = []

            # Add stdout output
            if execution_data.get("stdout"):
                cell_outputs.append({
                    "output_type": "stream",
                    "name": "stdout",
                    "text": execution_data["stdout"]
                })

            # Add stderr output
            if execution_data.get("stderr"):
                cell_outputs.append({
                    "output_type": "stream",
                    "name": "stderr",
                    "text": execution_data["stderr"]
                })

            # Add result output
            if execution_data.get("result"):
                cell_outputs.append({
                    "output_type": "execute_result",
                    "execution_count": execution_data.get("execution_count", 1),
                    "data": {"text/plain": execution_data["result"]},
                    "metadata": {}
                })

            # Create new cell
            new_cell = {
                "cell_type": "code",
                "execution_count": execution_data.get("execution_count", 1),
                "metadata": {},
                "source": execution_data["code"],
                "outputs": cell_outputs
            }

            # Add cell to notebook
            notebook_data["content"]["cells"].append(new_cell)

            # Save updated notebook
            print(f"[CODE-INTERPRETER] Saving updated notebook '{self.notebook_id}' with new cell.")
            async with self.session.put(
                    f"/api/contents/{self.notebook_id}",
                    json=notebook_data,
                    params=self.params
            ) as response:
                response.raise_for_status()
                print(f"[CODE-INTERPRETER] Notebook '{self.notebook_id}' updated successfully with new cell.")
                return True

        except Exception as e:
            print(f"[CODE-INTERPRETER] Error appending to notebook: {e}")
            return False


async def execute_code_jupyter(
        base_url: str, chat_id: str, code: str, token: str = "", password: str = "", timeout: int = 60
) -> dict:
    print(
        f"[CODE-INTERPRETER] execute_code_jupyter called with base_url='{base_url}', chat_id='{chat_id}', token='{token[:5] if token else ''}...', password={'yes' if password else 'no'}, timeout={timeout}")
    print(f"[CODE-INTERPRETER] Code to execute:\n---\n{code}\n---")
    start_time = time.time()
    async with JupyterCodeExecuter(
            base_url, code, chat_id, token, password, timeout
    ) as executor:
        result = await executor.run()
        final_result = result.model_dump()
    end_time = time.time()
    print(f"[CODE-INTERPRETER] execute_code_jupyter finished in {end_time - start_time:.4f} seconds.")
    print(f"[CODE-INTERPRETER] Returning result: {final_result}")
    return final_result