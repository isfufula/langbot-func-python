import os
import json
import openai
import azure.functions as func
import traceback

# Azure OpenAI 設定
openai.api_type = "azure"
openai.api_base = os.getenv("AZURE_OPENAI_ENDPOINT")      # 例：https://your-resource-name.openai.azure.com/
openai.api_version = "2023-05-15"
openai.api_key = os.getenv("AZURE_OPENAI_KEY")

def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        req_body = req.get_json()
        user_input = req_body.get("message")

        if not user_input:
            return func.HttpResponse("No message provided", status_code=400)

        # 使用 Azure OpenAI 呼叫對話
        completion = openai.ChatCompletion.create(
            engine=os.getenv("AZURE_OPENAI_DEPLOYMENT"),  # 注意：這是你部署模型的名稱，不是 gpt-35-turbo 字串
            messages=[
                { "role": "system", "content": "You are a helpful English tutor. Only speak in English." },
                { "role": "user", "content": user_input }
            ]
        )

        reply = completion.choices[0].message["content"]
        return func.HttpResponse(json.dumps({ "response": reply }), mimetype="application/json")

    except Exception as e:
        print("⚠️ Exception:", str(e))
        print(traceback.format_exc())
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)
