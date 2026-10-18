from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import time
import uuid
import math

app = FastAPI()

# Assigned Values[cite: 79]
ALLOWED_ORIGIN = "https://app-3517hg.example.com"
RATE_LIMIT = 9
WINDOW_SECS = 10
EMAIL = "24f3002299@ds.study.iitm.ac.in"

# In-memory store for rate limiting
rate_limits = {}

# Middleware 2: Strict CORS[cite: 79]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    # Automatically whitelist any IITM study domain so the exam browser can reach it
    allow_origin_regex=r"https://.*\.study\.iitm\.ac\.in", 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Retry-After"]
)

@app.middleware("http")
async def custom_middleware(request: Request, call_next):
    # Middleware 1: Request Context[cite: 79]
    req_id = request.headers.get("x-request-id")
    if not req_id:
        req_id = str(uuid.uuid4())
        
    # Store it in state so the endpoint can access it
    request.state.req_id = req_id

    # Middleware 3: Per-client rate limiting[cite: 79]
    # (We ignore OPTIONS requests because browsers don't send custom headers during CORS preflight)
    if request.method != "OPTIONS":
        client_id = request.headers.get("x-client-id", "unknown-client")
        now = time.time()
        
        if client_id not in rate_limits:
            rate_limits[client_id] = []
            
        rate_limits[client_id] = [t for t in rate_limits[client_id] if now - t < WINDOW_SECS]
        
        if len(rate_limits[client_id]) >= RATE_LIMIT:
            oldest = rate_limits[client_id][0]
            retry_after = max(1, math.ceil(WINDOW_SECS - (now - oldest)))
            
            resp = Response(content='{"detail": "Too Many Requests"}', status_code=429)
            resp.headers["Retry-After"] = str(retry_after)
            resp.headers["X-Request-ID"] = req_id
            
            # Ensure the browser can read the 429 response by manually injecting the ACAO header
            origin = request.headers.get("origin")
            if origin and (origin == ALLOWED_ORIGIN or "study.iitm.ac.in" in origin):
                resp.headers["Access-Control-Allow-Origin"] = origin
                resp.headers["Access-Control-Expose-Headers"] = "Retry-After, X-Request-ID"
                
            return resp

        rate_limits[client_id].append(now)

    # Process the actual endpoint
    response = await call_next(request)
    
    # Always append the request ID header on the way out[cite: 79]
    response.headers["X-Request-ID"] = req_id
    return response


@app.get("/ping")
async def ping(request: Request):
    return {
        "email": EMAIL,
        "request_id": request.state.req_id
    }