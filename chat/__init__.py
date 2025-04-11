import openai
import os
import azure.functions as func
import json

def main(req: func.HttpRequest) -> func.HttpResponse:
    openai.api_key = os.getenv("OPENAI_API_KEY")
    try:
        req_body = req.get_json()
        user_input = req_body.get("message")
        if not user_input:
            return func.HttpResponse("No message provided", status_code=400)
        
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                { "role": "system", "content": "You are a helpful English tutor. Only speak in English." },
                { "role": "user", "content": user_input }
            ]
        )
        reply = completion.choices[0].message["content"]
        return func.HttpResponse(json.dumps({ "response": reply }), mimetype="application/json")
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)
