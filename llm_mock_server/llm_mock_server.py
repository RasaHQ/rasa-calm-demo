import argparse
import json
import logging
import re
from argparse import Namespace
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import orjson

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    )
logger = logging.getLogger(__name__)

app = FastAPI()

class RequestResponsePair(BaseModel):
    request: str
    response: Any

class CommunicationItem(BaseModel):
    request_response: List[RequestResponsePair]
    method: str
    full_path: str

communication:Dict[str, CommunicationItem] = {}
cache_response = {}
user_input_cache = {}

def extract_conversation_history_and_last_user_message(input_body: str) -> Optional[str]:
    input_message_hash = hash(input_body)

    if input_message_hash in user_input_cache:
        logger.info(f"Return cached output: {user_input_cache[input_message_hash]}")
        return user_input_cache[input_message_hash]

    pattern = r"Conversation History:.*USER: (.*?)\n\n---\n\n"

    # Example usage:
    match = re.search(pattern, input_body, re.MULTILINE | re.DOTALL)

    if match:
        conversation = match.group(1)
        user_input_cache[input_message_hash] = conversation
        return conversation
    else:
        return None

# Load the Postman collection
def load_postman_collection(file_path: str) -> Dict[str, Any]:
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        logger.error(f"Collection file not found: {file_path}")
        raise
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in collection file: {file_path}")
        raise


async def generic_endpoint(request: Request):
    body_bytes = await request.body()
    body = orjson.loads(body_bytes)

    user_input = extract_conversation_history_and_last_user_message(body['messages'][0]['content'])

    if not user_input:
        logger.info(f"User input not found in: {user_input}")
        raise HTTPException(status_code=404, detail="Matching response not found")

    search_string = f"USER: {user_input}"
    logger.info(f"Search string: {search_string}")


    logger.info(f"Caches_response keys: {cache_response.keys()}")

    if search_string in cache_response:
        return cache_response[search_string]

    communication_item = communication.get(request.url.path, None)

    if not communication_item:
        logger.info(f"2 User input not found in: {user_input}")
        raise HTTPException(status_code=404, detail="Matching response not found")

    for request_response_pair in communication_item.request_response:
        logger.info(f"request_response_pair.request: {request_response_pair.request}")
        if search_string in request_response_pair.request:
            # logger.info(f"Found response for {search_string}")
            cache_response[search_string] = request_response_pair.response
            return request_response_pair.response


    logger.info(f"3 User input not found in: {user_input}")
    logger.info(f"caches_response keys: {communication.get(request.url.path, None)}")
    logger.info(f"body: {body}")
    raise HTTPException(status_code=404, detail="Matching response not found")

# Parse the collection and create endpoints
def create_endpoints(collection: Dict[str, Any]):
    for item in collection.get('item', []):
        if 'request' in item:
            method = item['request']['method'].lower()
            path = item['request']['url']['path']
            full_path = '/' + '/'.join(path)

            request_response_pair = RequestResponsePair(
                request=item['request']['body']['raw'],
                response=orjson.loads(item['response'][0]['body'])
            )

            if full_path in communication:
                communication[full_path].request_response.append(request_response_pair)

            else:
                communication_item = CommunicationItem(
                    request_response=[request_response_pair],
                    method=method,
                    full_path=full_path
                )
                communication[full_path] = communication_item

    for communication_item in communication.values():
        method = communication_item.method
        full_path = communication_item.full_path

        logger.info(f"Creating endpoint: {method.upper()} {full_path}")
        getattr(app, method)(full_path)(generic_endpoint)

    async def collection_endpoint(request: Request):
        return orjson.dumps(collection).decode('utf-8')

    app.get("/")(collection_endpoint)

def parse_args() -> Namespace:
    parser = argparse.ArgumentParser(description="FastAPI server for Postman collections")
    parser.add_argument("-c", "--collection", required=True, help="Path to the Postman collection JSON file")
    parser.add_argument("-p", "--port", type=int, default=8000, help="Port number to run the server on (default: 8000)")

    return parser.parse_args()

@app.get("/")
async def root():
    return {"message": "Welcome to the Postman Collection Server"}

def main():
    args = parse_args()
    postman_collection = load_postman_collection(args.collection)
    create_endpoints(postman_collection)

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=args.port)

if __name__ == "__main__":
    main()
