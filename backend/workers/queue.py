import os
from rq import Queue
from redis import Redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis = Redis.from_url(REDIS_URL)
q = Queue("runs", connection=redis)