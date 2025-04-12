import logging
import azure.functions as func
import os
import json
import asyncio
from azure.cognitiveservices.speech import SpeechConfig, AudioConfig, SpeechRecognizer, SpeechSynthesizer
from azure.core.credentials import AzureKeyCredential
from azure.ai.language.spellcheck import SpellCheckClient

# 從環境變數中讀取 Azure 服務的 Key 和 Endpoint
SPEECH_KEY = os.environ.get("SPEECH_KEY")
SPEECH_REGION = os.environ.get("SPEECH_REGION")
LANGUAGE_KEY = os.environ.get("LANGUAGE_KEY")
LANGUAGE_ENDPOINT = os.environ.get("LANGUAGE_ENDPOINT")

async def speech_to_text(audio_data: bytes):
    """使用 Azure Speech Service 將音訊轉換為文字"""
    speech_config = SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)
    audio_config = AudioConfig(speech_input_stream=audio_data)
    speech_recognizer = SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    future = asyncio.Future()

    def recognized(evt):
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            future.set_result(evt.result.text)
        elif evt.result.reason == speechsdk.ResultReason.NoMatch:
            future.set_result("")
        elif evt.result.reason == speechsdk.ResultReason.Canceled:
            future.set_exception(Exception(f"語音辨識取消: {evt.result.cancellation_details.reason}"))

    speech_recognizer.recognized.connect(recognized)
    speech_recognizer.start_continuous_recognition()
    try:
        result = await future
    finally:
        speech_recognizer.stop_continuous_recognition()
    return result

async def correct_text(user_message: str):
    """使用 Azure Language Service (Text Analytics) 進行拼字檢查"""
    if not LANGUAGE_KEY or not LANGUAGE_ENDPOINT:
        logging.warning("Language Service Key 或 Endpoint 未設定，跳過拼字檢查。")
        return user_message, ""

    credential = AzureKeyCredential(LANGUAGE_KEY)
    client = SpellCheckClient(LANGUAGE_ENDPOINT, credential)

    try:
        response = client.spell_check(text=user_message)
        corrected_text = user_message
        corrections = []
        for misspelled_word in response.errors:
            if misspelled_word.suggestions:
                corrected_text = corrected_text.replace(misspelled_word.token, misspelled_word.suggestions[0].suggestion)
                corrections.append(f"將 '{misspelled_word.token}' 更正為 '{misspelled_word.suggestions[0].suggestion}'")
        correction_message = ", ".join(corrections)
        return corrected_text, correction_message
    except Exception as e:
        logging.error(f"Language Service 拼字檢查錯誤: {e}")
        return user_message, "拼字檢查失敗。"

async def generate_response(corrected_text: str):
    """簡單的規則引擎產生回應"""
    corrected_text_lower = corrected_text.lower()
    if "你好" in corrected_text_lower or "您好" in corrected_text_lower:
        return "您好！有什麼我可以幫您的嗎？"
    elif "謝謝" in corrected_text_lower:
        return "不客氣！"
    elif "再見" in corrected_text_lower:
        return "再見！"
    elif "今天天氣" in corrected_text_lower:
        return "抱歉，我目前無法查詢天氣資訊。"
    else:
        return f"您說了：{corrected_text}。我正在學習更多。"

async def text_to_speech(text: str):
    """使用 Azure Speech Service 將文字轉換為語音"""
    speech_config = SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)
    speech_config.speech_synthesis_voice_name = "zh-TW-HsiaoYu-Neural" # 您可以選擇其他語音

    # 使用記憶體流來處理語音輸出
    audio_config = AudioConfig(use_default_speaker=None)
    speech_synthesizer = SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

    result = await speech_synthesizer.speak_text_async(text)
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        return result.audio_data
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        logging.error(f"語音合成取消: {cancellation_details.reason}")
        if cancellation_details.error_details:
            logging.error(f"錯誤細節: {cancellation_details.error_details}")
        return None

async def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    try:
        audio_data = req.get_body()
        if not audio_data:
            return func.HttpResponse(
                 "請傳送音訊資料",
                 status_code=400
            )

        # 1. 語音轉文字
        user_text = await speech_to_text(audio_data)
        logging.info(f"使用者說: {user_text}")

        if not user_text:
            return func.HttpResponse(
                json.dumps({"reply_text": "聽不清楚，請再說一次。","reply_audio": None, "corrected_text": ""}),
                mimetype="application/json"
            )

        # 2. 文字糾錯
        corrected_text, correction_message = await correct_text(user_text)
        logging.info(f"糾正後的文字: {corrected_text}, 糾錯訊息: {correction_message}")

        # 3. 產生 AI 回覆 (使用簡單規則)
        reply_text = await generate_response(corrected_text)
        logging.info(f"AI 回覆: {reply_text}")

        # 4. 文字轉語音 (AI 的回覆)
        reply_audio_data = await text_to_speech(reply_text)
        reply_audio_base64 = None
        if reply_audio_data:
            import base64
            reply_audio_base64 = base64.b64encode(reply_audio_data).decode('utf-8')

        return func.HttpResponse(
            json.dumps({"reply_text": reply_text, "reply_audio": reply_audio_base64, "corrected_text": correction_message}),
            mimetype="application/json"
        )

    except Exception as e:
        logging.error(f"處理請求時發生錯誤: {e}")
        return func.HttpResponse(
             f"處理請求時發生錯誤: {e}",
             status_code=500
        )

if __name__ == "__main__":
    # 本地測試 (您需要設定環境變數)
    async def mock_request(audio_file_path):
        with open(audio_file_path, "rb") as f:
            audio_data = f.read()
        class MockHttpRequest:
            def get_body(self):
                return audio_data
        return MockHttpRequest()

    async def test_function():
        import azure.cognitiveservices.speech as speechsdk
        # 建立一個假的音訊檔案 (替換為您的音訊檔案路徑)
        mock_req = await mock_request("test_audio.wav")
        response = await main(mock_req)
        if response.status_code == 200:
            print(f"回應內容: {response.get_body()}")
        else:
            print(f"錯誤: {response.status_code} - {response.get_body()}")

    # asyncio.run(test_function())
