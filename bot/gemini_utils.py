# gemini_utils.py

import config
import google.generativeai as genai
import asyncio

# تنظیمات Gemini
genai.configure(api_key=config.gemini_api_key)

GEMINI_COMPLETION_OPTIONS = {
    "temperature": 0.7,
    "max_tokens": 1000,
    "top_p": 1,
}

class GeminiChat:
    def __init__(self, model="gemini-1.5-flash"):
        self.model = model
        self.client = genai.GenerativeModel(model_name=model)

    async def send_message(self, message, dialog_messages=[], chat_mode="assistant"):
        if chat_mode not in config.chat_modes.keys():
            raise ValueError(f"Chat mode {chat_mode} is not supported")

        try:
            # ساخت پرامپت با تاریخچه مکالمه
            messages = self._generate_prompt_messages(message, dialog_messages, chat_mode)
            response = await asyncio.to_thread(self.client.generate_content, messages)
            answer = response.text

            # محاسبه توکن‌ها (Gemini توکن‌ها را مستقیم گزارش نمی‌دهد، این تقریبی است)
            n_input_tokens = len(" ".join([m["content"] for m in messages]).split())
            n_output_tokens = len(answer.split())

            answer = self._postprocess_answer(answer)
            return answer, (n_input_tokens, n_output_tokens), 0

        except Exception as e:
            raise ValueError(f"Error in Gemini API: {str(e)}")

    async def send_message_stream(self, message, dialog_messages=[], chat_mode="assistant"):
        if chat_mode not in config.chat_modes.keys():
            raise ValueError(f"Chat mode {chat_mode} is not supported")

        try:
            messages = self._generate_prompt_messages(message, dialog_messages, chat_mode)
            response = await asyncio.to_thread(self.client.generate_content, messages, stream=True)

            answer = ""
            n_input_tokens = len(" ".join([m["content"] for m in messages]).split())
            async for chunk in response:
                if chunk.text:
                    answer += chunk.text
                    n_output_tokens = len(answer.split())
                    yield "not_finished", answer, (n_input_tokens, n_output_tokens), 0

            answer = self._postprocess_answer(answer)
            yield "finished", answer, (n_input_tokens, n_output_tokens), 0

        except Exception as e:
            raise ValueError(f"Error in Gemini API: {str(e)}")

    def _generate_prompt_messages(self, message, dialog_messages, chat_mode):
        prompt = config.chat_modes[chat_mode]["prompt_start"]
        messages = [{"role": "system", "content": prompt}]

        for dialog_message in dialog_messages:
            messages.append({"role": "user", "content": dialog_message["user"]})
            messages.append({"role": "model", "content": dialog_message["bot"]})
        messages.append({"role": "user", "content": message})

        return messages

    def _postprocess_answer(self, answer):
        return answer.strip()