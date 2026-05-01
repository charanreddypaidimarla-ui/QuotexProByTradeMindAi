import re
import json
import sys
import asyncio
from pathlib import Path
from pyquotex.http.navigator import Browser


class Login(Browser):
    """Class for Quotex login resource."""

    url = ""
    cookies = None
    ssid = None

    def __init__(self, api, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api = api
        self.html = None
        self.headers = self.get_headers()
        # Use domain from api if available, fallback to qxbroker.com
        self.base_url = getattr(api, 'host', 'qxbroker.com')  # QuotexAPI stores domain as self.host
        self.https_base_url = f'https://{self.base_url}'
        self.full_url = f"{self.https_base_url}/{api.lang}"
        # Telegram credentials for remote OTP
        self.tg_token = getattr(api, 'tg_token', None)
        self.tg_chat_id = getattr(api, 'tg_chat_id', None)

    def get_token(self):
        self.headers["Connection"] = "keep-alive"
        self.headers["Accept-Encoding"] = "gzip, deflate, br"
        self.headers["Accept-Language"] = "pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3"
        self.headers["Accept"] = (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        )
        self.headers["Referer"] = f"{self.full_url}/sign-in"
        self.headers["Upgrade-Insecure-Requests"] = "1"
        self.headers["Sec-Ch-Ua-Mobile"] = "?0"
        self.headers["Sec-Ch-Ua-Platform"] = '"Linux"'
        self.headers["Sec-Fetch-Site"] = "same-origin"
        self.headers["Sec-Fetch-User"] = "?1"
        self.headers["Sec-Fetch-Dest"] = "document"
        self.headers["Sec-Fetch-Mode"] = "navigate"
        self.headers["Dnt"] = "1"
        self.send_request(
            "GET",
            f"{self.full_url}/sign-in/modal/"
        )
        html = self.get_soup()
        match = html.find(
            "input", {"name": "_token"}
        )
        token = None if not match else match.get("value")
        return token

    async def _poll_telegram_for_otp(self, prompt_sent_event):
        """Poll Telegram for a numeric reply from the authorized chat_id."""
        if not self.tg_token or not self.tg_chat_id:
            return None

        import requests
        import time

        bot_token = self.tg_token
        chat_id = self.tg_chat_id
        
        # 1. Send active notification to user
        try:
            alert_msg = (
                f"🔐 *QUOTEX LOGIN — OTP REQUIRED*\n"
                "━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📍 *PROMPT:* `{prompt_sent_event}`\n"
                f"⏰ *TIME:* `{time.strftime('%H:%M:%S')}`\n\n"
                "👉 Please reply with your *6-digit PIN* code."
            )
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": alert_msg, "parse_mode": "Markdown"},
                timeout=10
            )
        except Exception as e:
            print(f"Failed to send Telegram prompt: {e}")

        # 2. Poll for reply
        offset = None
        start_time = time.time()
        timeout = 300  # 5 minutes
        
        while time.time() - start_time < timeout:
            try:
                url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
                params = {"timeout": 20, "offset": offset}
                resp = requests.get(url, params=params, timeout=25).json()
                
                if resp.get("ok"):
                    for update in resp.get("result", []):
                        offset = update["update_id"] + 1
                        message = update.get("message", {})
                        text = message.get("text", "").strip()
                        from_id = str(message.get("from", {}).get("id", ""))
                        
                        msg_date = message.get("date", 0)
                        
                        # Accept if numeric, correct user, and sent AFTER polling started
                        if from_id == str(chat_id) and text.isdigit() and len(text) >= 5:
                            if msg_date >= (start_time - 10):
                                return text
            except Exception:
                pass
            await asyncio.sleep(2)
        return None

    def _poll_terminal_for_otp(self, input_message):
        """Standard blocking terminal input."""
        try:
            code = input(input_message).strip()
            # Return None if empty or non-numeric (happens in non-interactive shells)
            if code and code.isdigit() and len(code) >= 5:
                return code
            return None
        except (EOFError, OSError):
            # Non-interactive terminal — can't read input
            return None
        except Exception:
            return None

    async def awaiting_pin(self, data, input_message):
        self.headers["Content-Type"] = "application/x-www-form-urlencoded"
        self.headers["Referer"] = f"{self.full_url}/sign-in/modal"
        data["keep_code"] = 1
        
        max_retries = 3
        for attempt in range(max_retries):
            print(f"\n[OTP] {input_message}")
            if self.tg_token:
                print(f"[OTP] 📱 Remote fallback ACTIVE: Send PIN to your Telegram bot.")

            # Run both polling mechanisms concurrently
            terminal_task = asyncio.create_task(asyncio.to_thread(self._poll_terminal_for_otp, input_message))
            telegram_task = asyncio.create_task(self._poll_telegram_for_otp(input_message))
            
            try:
                # Wait for either to provide a result
                done, pending = await asyncio.wait(
                    [terminal_task, telegram_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Cancel the pending task
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except (asyncio.CancelledError, Exception):
                        pass
                    
                # Retrieve the winning code
                code = None
                for task in done:
                    result = task.result()
                    if result and result.isdigit() and len(result) >= 5:
                        code = result
                        source = "Terminal" if task == terminal_task else "Telegram"
                        print(f"✅ OTP Received via {source}")
                        break
                
                if code:
                    data["code"] = code
                    break  # Got a valid code, exit retry loop
                else:
                    print(f"⚠️ No valid code received (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        print("   Waiting for Telegram OTP...")
                        # On retry, only wait for Telegram (terminal input failed)
                        telegram_only = asyncio.create_task(self._poll_telegram_for_otp(input_message))
                        try:
                            code = await asyncio.wait_for(telegram_only, timeout=120)
                        except asyncio.TimeoutError:
                            code = None
                        if code and code.isdigit() and len(code) >= 5:
                            print(f"✅ OTP Received via Telegram")
                            data["code"] = code
                            break
                    continue
                    
            except Exception as e:
                print(f"Error during OTP polling (attempt {attempt + 1}): {e}")
                if attempt >= max_retries - 1:
                    print("❌ All OTP attempts exhausted. Exiting.")
                    sys.exit(1)
        
        if "code" not in data:
            print("❌ Failed to receive OTP after all attempts. Exiting.")
            sys.exit(1)

        await asyncio.sleep(1)
        self.send_request(
            method="POST",
            url=f"{self.full_url}/sign-in/modal",
            data=data
        )

    def get_profile(self):
        self.response = self.send_request(
            method="GET",
            url=f"{self.full_url}/trade"
        )
        if self.response:
            script = self.get_soup().find_all(
                "script",
                {"type": "text/javascript"}
            )
            script = script[0].get_text() if script else "{}"
            match = re.sub(
                "window.settings = ",
                "",
                script.strip().replace(";", "")
            )
            self.cookies = self.get_cookies()
            self.ssid = json.loads(match).get("token")
            self.api.session_data["cookies"] = self.cookies
            self.api.session_data["token"] = self.ssid
            self.api.session_data["user_agent"] = self.headers["User-Agent"]
            output_file = Path(f"{self.api.resource_path}/session.json")
            output_file.parent.mkdir(exist_ok=True, parents=True)
            output_file.write_text(
                json.dumps({
                    "cookies": self.cookies,
                    "token": self.ssid,
                    "user_agent": self.headers["User-Agent"]
                }, indent=4)
            )
            return self.response, json.loads(match)

        return None, None

    def _get(self):
        return self.send_request(
            method="GET",
            url=f"{self.full_url}/trade"
        )

    async def _post(self, data):
        """Send get request for Quotex API login http resource.
        :returns: The instance of :class:`requests.Response`.
        """
        self.response = self.send_request(
            method="POST",
            url=f"{self.full_url}/sign-in/",
            data=data
        )
        required_keep_code = self.get_soup().find(
            "input", {"name": "keep_code"}
        )
        if required_keep_code:
            auth_body = self.get_soup().find(
                "main", {"class": "auth__body"}
            )
            input_message = (
                f'{auth_body.find("p").text}: ' if auth_body.find("p")
                else "Insira o código PIN que acabamos "
                     "de enviar para o seu e-mail: "
            )
            await self.awaiting_pin(data, input_message)
        await asyncio.sleep(1)
        success = self.success_login()
        return success

    def success_login(self):
        if "trade" in self.response.url:
            return True, "Login successful."
        html = self.get_soup()
        match = html.find(
            "div", {"class": "hint--danger"}
        ) or html.find(
            "div", {"class": "input-control-cabinet__hint"}
        )
        message_in_match = match.text.strip() if match else ""
        return False, f"Login failed. {message_in_match}"

    async def __call__(self, username, password, user_data_dir=None):
        """Method to get Quotex API login http request.
        :param str username: The username of a Quotex server.
        :param str password: The password of a Quotex server.
        :param str user_data_dir: The optional value for path userdata.
        :returns: The instance of :class:`requests.Response`.
        """
        data = {
            "_token": self.get_token(),
            "email": username,
            "password": password,
            "remember": 1,

        }
        status, msg = await self._post(data)
        if not status:
            print(msg)
            exit(0)

        self.get_profile()

        return status, msg
