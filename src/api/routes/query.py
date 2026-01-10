from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from src.core.redis_client import get_redis_client
from src.core.database import get_query_db
import json
from sqlalchemy import text

router = APIRouter(tags=["query"])

async def stream_csv(sql: str, project_id: int):
    db = get_query_db(project_id)
    async def generator():
        yield ",".join([])
        async with db.async_engine.connect() as conn:
            result = await conn.stream(text(sql))
            headers_sent = False
            async for row in result:
                d = dict(row._mapping)
                if not headers_sent:
                    headers_sent = True
                    yield ",".join([str(k) for k in d.keys()]) + "\n"
                vals = []
                for k in d.keys():
                    v = d[k]
                    vals.append(json.dumps(v if v is not None else ""))
                yield ",".join(vals) + "\n"
    return StreamingResponse(generator(), media_type="text/csv")

@router.get("/query/download")
async def download_query(token: str):
    r = get_redis_client()
    data = r.get(token)
    if not data:
        raise HTTPException(status_code=404, detail="invalid token")
    payload = json.loads(data)
    sql = payload.get("sql")
    project_id = payload.get("project_id")
    return await stream_csv(sql, project_id)
