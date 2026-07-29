from redis import Redis
from redis.exceptions import RedisError

from supply_chain_hub.settings.config import get_settings


def redis_is_available() -> bool:
    client = Redis.from_url(
        get_settings().redis_url,
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    try:
        return bool(client.ping())
    except RedisError:
        return False
    finally:
        client.close()
