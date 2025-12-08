import urllib.request
import urllib.error
import json
import uuid
import sys

url = "https://meliora.meliora.fi/mcp/endpoint"
initial_session_id = str(uuid.uuid4())

headers = {
    "Content-Type": "application/json",
    "Accept": "text/event-stream, application/json",
    "key": "salakissakala",
    "mcp-session-id": initial_session_id
}

output_file = "requirement_detail.json"

def parse_sse(body):
    """Extracts JSON data from SSE stream"""
    for line in body.splitlines():
        if line.startswith("data: "):
            try:
                return json.loads(line[6:])
            except:
                pass
    return None

def send_request(method, params=None, request_id=None, extra_headers=None):
    payload = {
        "jsonrpc": "2.0",
        "method": method
    }
    if params is not None:
        payload["params"] = params
    if request_id is not None:
        payload["id"] = request_id
    
    current_headers = headers.copy()
    if extra_headers:
        current_headers.update(extra_headers)

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=current_headers)
    
    with urllib.request.urlopen(req) as response:
        body = response.read().decode('utf-8')
        try:
            return response.headers, json.loads(body)
        except:
            return response.headers, parse_sse(body)

try:
    print("Initializing...")
    init_headers, _ = send_request(
        "initialize", 
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "fetch-req", "version": "1.0"}
        },
        request_id=1
    )
    
    session_header = init_headers.get("Mcp-Session-Id")
    if not session_header:
            for k in init_headers.keys():
                if k.lower() == "mcp-session-id":
                    session_header = init_headers[k]
                    break
    
    if not session_header:
        print("Error: No session ID")
        sys.exit(1)
        
    headers["mcp-session-id"] = session_header
    print(f"Session ID: {session_header}")

    send_request("notifications/initialized")

    print("Fetching requirement REQ-F-UXD-001...")
    _, tool_response = send_request(
        "tools/call", 
        {
            "name": "get_requirement",
            "arguments": {
                "projectKey": "NOP",
                "requirementId": "REQ-F-UXD-001"
            }
        }, 
        request_id=2
    )

    if tool_response and "result" in tool_response and "content" in tool_response["result"]:
        content = tool_response["result"]["content"]
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2)
        print(f"Saved requirement details to {output_file}")
    else:
        print("Error: Failed to fetch requirement content")
        print(json.dumps(tool_response, indent=2))

except Exception as e:
    print(f"Error: {e}")
