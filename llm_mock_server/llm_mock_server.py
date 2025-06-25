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

# Initialize FastAPI application
app = FastAPI()

class RequestResponsePair(BaseModel):
    """
    Represents a single request-response pair from the Postman collection.
    Each pair contains the original request body and the expected response.
    """
    request: str
    response: Any

class CommunicationItem(BaseModel):
    """
    Represents all communication data for a specific API endpoint.
    Contains multiple request-response pairs, HTTP method, and the full path.
    """
    request_response: List[RequestResponsePair]
    method: str
    full_path: str

# Stores all endpoint configurations indexed by path
communication:Dict[str, CommunicationItem] = {}
# Caches responses by search string for faster lookup
cache_response = {}
# Caches extracted user inputs by hash to avoid re-processing
user_input_cache = {}

def extract_conversation_history_and_last_user_message(input_body: str) -> Optional[str]:
    """
    Extracts conversation history from the input body using regex pattern matching.

    This function looks for a specific pattern in the input that contains conversation history
    between "Conversation History" and a separator "---". It uses caching to avoid
    re-processing the same input multiple times.

    Args:
        input_body (str): The raw input body containing conversation data

    Returns:
        Optional[str]: The extracted conversation history, or None if not found
    """
    # Create a hash of the input for caching purposes
    input_message_hash = hash(input_body)

    # Check if we've already processed this input before
    if input_message_hash in user_input_cache:
        logger.info(f"Return cached output: {user_input_cache[input_message_hash]}")
        return user_input_cache[input_message_hash]

    # Regular expression pattern to match conversation history
    # Looks for text between "Conversation History" and "\n\n---\n\n"
    pattern = r"Conversation History(.*?)\n\n---\n\n"

    # Search for the pattern in the input body with multiline and dotall flags
    match = re.search(pattern, input_body, re.MULTILINE | re.DOTALL)

    if match:
        # Extract the conversation content from the first capture group
        conversation = match.group(1)
        # Cache the result for future use
        user_input_cache[input_message_hash] = conversation
        return conversation
    else:
        # No conversation history found
        return None

# Load the Postman collection
def load_postman_collection(file_path: str) -> Dict[str, Any]:
    """
    Loads and parses a Postman collection JSON file.

    Args:
        file_path (str): Path to the Postman collection JSON file

    Returns:
        Dict[str, Any]: Parsed JSON data from the collection file

    Raises:
        FileNotFoundError: If the collection file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
    """
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
    """
    Generic endpoint handler that processes all API requests.

    This function:
    1. Extracts the request body and parses it as JSON
    2. Extracts user input from the conversation history
    3. Searches for matching request-response pairs
    4. Returns the appropriate cached or stored response

    Args:
        request (Request): The incoming FastAPI request object

    Returns:
        Any: The matching response data

    Raises:
        HTTPException: If no matching response is found (404 error)
    """
    # Read and parse the request body
    body_bytes = await request.body()
    body = orjson.loads(body_bytes)

    # Extract user input from the conversation history in the request
    user_input = extract_conversation_history_and_last_user_message(body['messages'][0]['content'])

    # If no user input was found, return 404
    if not user_input:
        logger.info(f"User input not found in: {user_input}")
        raise HTTPException(status_code=404, detail="Matching response not found")

    # Create a search string by prefixing with "USER: "
    search_string = f"USER: {user_input}"
    logger.info(f"Search string: {search_string}")

    logger.info(f"Caches_response keys: {cache_response.keys()}")

    # Check if we have a cached response for this search string
    if search_string in cache_response:
        return cache_response[search_string]

    # Get the communication item for this endpoint path
    communication_item = communication.get(request.url.path, None)

    # If no communication item found for this path, return 404
    if not communication_item:
        logger.info(f"2 User input not found in: {user_input}")
        raise HTTPException(status_code=404, detail="Matching response not found")

    # Search through all request-response pairs for this endpoint
    for request_response_pair in communication_item.request_response:
        logger.info(f"request_response_pair.request: {request_response_pair.request}")

        # Check if the search string matches any stored request
        if search_string in request_response_pair.request:
            # Cache the response for future requests
            cache_response[search_string] = request_response_pair.response
            return request_response_pair.response

    # No matching request-response pair found
    logger.info(f"3 User input not found in: {user_input}")
    logger.info(f"caches_response keys: {communication.get(request.url.path, None)}")
    logger.info(f"body: {body}")
    raise HTTPException(status_code=404, detail="Matching response not found")

def create_endpoints(collection: Dict[str, Any]):
    """
    Parses the Postman collection and dynamically creates FastAPI endpoints.

    This function:
    1. Iterates through all items in the collection
    2. Extracts request-response data from each item
    3. Groups request-response pairs by endpoint path
    4. Dynamically creates FastAPI route handlers for each endpoint
    5. Creates a root endpoint that returns the entire collection

    Args:
        collection (Dict[str, Any]): The parsed Postman collection data
    """
    for item in collection.get('item', []):
        # Only process items that have request data
        if 'request' in item:
            # Extract HTTP method and convert to lowercase
            method = item['request']['method'].lower()

            # Extract URL path components and join them
            path = item['request']['url']['path']
            full_path = '/' + '/'.join(path)

            # Create a request-response pair from the Postman data
            request_response_pair = RequestResponsePair(
                request=item['request']['body']['raw'],
                response=orjson.loads(item['response'][0]['body'])
            )

            # If we already have data for this path, add to existing list
            if full_path in communication:
                communication[full_path].request_response.append(request_response_pair)
            else:
                # Create new communication item for this path
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
    """
    Parses command line arguments for the application.

    Returns:
        Namespace: Parsed command line arguments containing:
            - collection: Path to the Postman collection file
            - port: Port number to run the server on
    """
    parser = argparse.ArgumentParser(description="FastAPI server for Postman collections")
    parser.add_argument("-c", "--collection", required=True, help="Path to the Postman collection JSON file")
    parser.add_argument("-p", "--port", type=int, default=8000, help="Port number to run the server on (default: 8000)")

    return parser.parse_args()

@app.get("/")
async def root():
    return {"message": "Welcome to the Postman Collection Server"}

def main():
    """
    Main function that orchestrates the application startup:
    1. Parses command line arguments
    2. Loads the Postman collection
    3. Creates dynamic endpoints from the collection
    4. Starts the FastAPI server using uvicorn
    """
    args = parse_args()
    # Load and parse the Postman collection file
    postman_collection = load_postman_collection(args.collection)
    # Create FastAPI endpoints from the collection data
    create_endpoints(postman_collection)

    import uvicorn
    # Start the FastAPI server
    uvicorn.run(app, host="0.0.0.0", port=args.port)

if __name__ == "__main__":
    main()
